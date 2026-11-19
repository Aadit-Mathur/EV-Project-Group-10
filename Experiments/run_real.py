"""Run the normalized-data EV charging experiment."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from Helpers.contracts import Scenario
from Helpers.data_pipeline import load_normalized_scenarios
from Helpers.evaluator import evaluate_schedule, evaluate_strategies
from Helpers.forecasting import forecast_target, save_forecast_artifacts
from LP_Optimizer import LPConfig
from LP_Optimizer.strategy import run_lp_strategy
from TOU.scheduler import run_tou
from Uncontrolled.scheduler import run_uncontrolled


@dataclass(frozen=True)
class ExperimentResult:
    schedules: Mapping[str, pd.DataFrame]
    metrics: pd.DataFrame
    information_mode_metrics: pd.DataFrame


def run_experiment(
    scenario: Scenario,
    forecast_inputs: Mapping[str, Sequence[float]] | None = None,
    config: LPConfig | None = None,
    sensitivity: bool = False,
) -> ExperimentResult:
    """Run all strategies and compare LP information modes on actual inputs."""

    schedules = {
        "uncontrolled": run_uncontrolled(scenario),
        "tou": run_tou(scenario),
        "lp_perfect_foresight": run_lp_strategy(scenario, config=config),
    }
    if forecast_inputs is not None:
        schedules["lp_forecast"] = run_lp_strategy(
            scenario,
            forecast_inputs=forecast_inputs,
            config=config,
        )

    metrics = evaluate_strategies(schedules, scenario)
    mode_rows = []
    for mode in ("lp_forecast", "lp_perfect_foresight"):
        if mode in schedules:
            mode_rows.append(
                {
                    "information_mode": mode,
                    **evaluate_schedule(schedules[mode], scenario),
                }
            )
    mode_metrics = pd.DataFrame(mode_rows)

    if sensitivity:
        sensitivity_schedule = run_lp_strategy(
            scenario,
            config=LPConfig(
                slot_hours=scenario.slot_hours,
                cost_weight=1.0,
                peak_weight=1.0,
                solar_weight=1.0,
            ),
        )
        metrics = pd.concat(
            [
                metrics,
                pd.DataFrame(
                    [
                        {
                            "strategy": "lp_equal_weights_sensitivity",
                            **evaluate_schedule(sensitivity_schedule, scenario),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return ExperimentResult(
        schedules=schedules,
        metrics=metrics,
        information_mode_metrics=mode_metrics,
    )


def save_experiment(result: ExperimentResult, output_dir: str | Path) -> None:
    """Persist schedules and metrics as auditable CSV artifacts."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.metrics.to_csv(output / "strategy_metrics.csv", index=False)
    result.information_mode_metrics.to_csv(
        output / "information_mode_metrics.csv",
        index=False,
    )
    for name, schedule in result.schedules.items():
        schedule.to_csv(output / f"{name}_schedule.csv", index=False)


def _aggregate_profile(schedule: pd.DataFrame, timestamps: Sequence[pd.Timestamp]) -> np.ndarray:
    frame = schedule.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    index = pd.DatetimeIndex(timestamps)
    return (
        frame.groupby("timestamp")["charging_power_kw"]
        .sum()
        .reindex(index, fill_value=0.0)
        .to_numpy(dtype=float)
    )


def save_rebound_artifacts(
    rebound_rows: list[dict],
    profile_rows: list[dict],
    output_dir: str | Path,
) -> pd.DataFrame:
    """Save real-data TOU rebound diagnostics and profiles."""

    output = Path(output_dir)
    rows = pd.DataFrame(rebound_rows)
    rows.to_csv(output / "tou_rebound_peak.csv", index=False, float_format="%.6f")

    tou_higher = int((rows["tou_peak_grid_kw"] > rows["uncontrolled_peak_grid_kw"] + 1e-9).sum())
    tou_lower = int((rows["tou_peak_grid_kw"] < rows["uncontrolled_peak_grid_kw"] - 1e-9).sum())
    tou_equal = int(len(rows) - tou_higher - tou_lower)
    summary = pd.DataFrame(
        [
            {
                "metric": "scenarios",
                "value": len(rows),
            },
            {
                "metric": "tou_peak_grid_higher_count",
                "value": tou_higher,
            },
            {
                "metric": "tou_peak_grid_lower_count",
                "value": tou_lower,
            },
            {
                "metric": "tou_peak_grid_equal_count",
                "value": tou_equal,
            },
            {
                "metric": "mean_peak_grid_change_pct",
                "value": float(
                    (
                        (rows["tou_peak_grid_kw"] - rows["uncontrolled_peak_grid_kw"])
                        / rows["uncontrolled_peak_grid_kw"].clip(lower=1e-12)
                        * 100.0
                    ).mean()
                ),
            },
            {
                "metric": "mean_tou_peak_ev_kw",
                "value": float(rows["tou_peak_ev_kw"].mean()),
            },
            {
                "metric": "mean_uncontrolled_peak_ev_kw",
                "value": float(rows["uncontrolled_peak_ev_kw"].mean()),
            },
        ]
    )
    summary.to_csv(output / "tou_rebound_summary.csv", index=False, float_format="%.6f")

    profiles = pd.DataFrame(profile_rows)
    mean_profile = profiles.groupby("local_hour", as_index=False)[
        ["uncontrolled_ev_kw", "tou_ev_kw", "uncontrolled_grid_kw", "tou_grid_kw"]
    ].mean()
    mean_profile.to_csv(output / "tou_rebound_mean_profile.csv", index=False, float_format="%.6f")

    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharex=True)
    axes[0].plot(mean_profile["local_hour"], mean_profile["uncontrolled_ev_kw"], marker="o", label="Uncontrolled")
    axes[0].plot(mean_profile["local_hour"], mean_profile["tou_ev_kw"], marker="o", label="TOU")
    axes[0].set_title("Mean EV charging load")
    axes[0].set_xlabel("Pasadena local hour")
    axes[0].set_ylabel("Aggregate EV power (kW)")
    axes[0].legend()

    axes[1].plot(mean_profile["local_hour"], mean_profile["uncontrolled_grid_kw"], marker="o", label="Uncontrolled")
    axes[1].plot(mean_profile["local_hour"], mean_profile["tou_grid_kw"], marker="o", label="TOU")
    axes[1].set_title("Mean site grid import")
    axes[1].set_xlabel("Pasadena local hour")
    axes[1].set_ylabel("Grid import (kW)")
    axes[1].legend()

    for axis in axes:
        axis.set_xticks(range(0, 24, 3))
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("Real-Data TOU Rebound Diagnostic", fontsize=14, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    figure.savefig(output / "tou_rebound_profile.png", dpi=220, bbox_inches="tight")
    plt.close(figure)
    return summary


def _forecast_inputs(package: Path, output: Path) -> tuple[dict[pd.Timestamp, float], pd.Timestamp]:
    baseline = pd.read_csv(package / "common_hourly_baseline.csv")
    frame = baseline.rename(
        columns={"timestamp_utc": "timestamp", "pv_generation_kw": "solar_kw"}
    )[["timestamp", "solar_kw"]]
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    forecast = forecast_target(frame, "solar_kw")
    save_forecast_artifacts(forecast, output / "forecasts")
    predictions = forecast.predictions.copy()
    predictions["timestamp"] = pd.to_datetime(predictions["timestamp"], utc=True)
    return dict(zip(predictions["timestamp"], predictions["predicted"])), predictions["timestamp"].min()


def run_real_experiment(
    package: str | Path = "Data/normalised/ev_common_base",
    output_dir: str | Path = "Results/real_data",
) -> pd.DataFrame:
    """Run all normalized scenarios and save auditable result artifacts."""

    package = Path(package)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    scenarios = load_normalized_scenarios(package)
    prediction_map, test_start = _forecast_inputs(package, output)
    all_metrics: list[pd.DataFrame] = []
    all_modes: list[pd.DataFrame] = []
    rebound_rows: list[dict] = []
    profile_rows: list[dict] = []
    for scenario in scenarios:
        scenario_output = output / "scenarios" / scenario.scenario_id
        forecast_values = [
            prediction_map.get(pd.Timestamp(timestamp).tz_convert("UTC"))
            for timestamp in scenario.timestamps
        ]
        use_forecast = (
            pd.Timestamp(scenario.timestamps[0]).tz_convert("UTC") >= test_start
            and all(value is not None for value in forecast_values)
        )
        result = run_experiment(
            scenario,
            forecast_inputs={"solar_kw": forecast_values} if use_forecast else None,
            sensitivity=True,
        )
        save_experiment(result, scenario_output)
        metrics = result.metrics.copy()
        metrics.insert(0, "scenario_id", scenario.scenario_id)
        all_metrics.append(metrics)
        modes = result.information_mode_metrics.copy()
        if not modes.empty:
            modes.insert(0, "scenario_id", scenario.scenario_id)
            modes.insert(1, "forecast_used", use_forecast)
            all_modes.append(modes)

        uncontrolled_ev = _aggregate_profile(
            result.schedules["uncontrolled"], scenario.timestamps
        )
        tou_ev = _aggregate_profile(result.schedules["tou"], scenario.timestamps)
        base = np.asarray(scenario.base_load_kw, dtype=float)
        solar = np.asarray(scenario.solar_kw, dtype=float)
        uncontrolled_grid = np.maximum(0.0, base + uncontrolled_ev - solar)
        tou_grid = np.maximum(0.0, base + tou_ev - solar)
        uncon_peak_slot = int(np.argmax(uncontrolled_grid))
        tou_peak_slot = int(np.argmax(tou_grid))
        timestamps = pd.DatetimeIndex(scenario.timestamps)
        rebound_rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "uncontrolled_peak_ev_kw": float(uncontrolled_ev.max()),
                "tou_peak_ev_kw": float(tou_ev.max()),
                "uncontrolled_peak_grid_kw": float(uncontrolled_grid.max()),
                "tou_peak_grid_kw": float(tou_grid.max()),
                "uncontrolled_peak_grid_slot": uncon_peak_slot,
                "tou_peak_grid_slot": tou_peak_slot,
                "uncontrolled_peak_local_hour": int(
                    timestamps[uncon_peak_slot].tz_convert("America/Los_Angeles").hour
                ),
                "tou_peak_local_hour": int(
                    timestamps[tou_peak_slot].tz_convert("America/Los_Angeles").hour
                ),
            }
        )
        for slot, timestamp in enumerate(timestamps[:24]):
            local_hour = int(timestamp.tz_convert("America/Los_Angeles").hour)
            profile_rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "local_hour": local_hour,
                    "uncontrolled_ev_kw": float(uncontrolled_ev[slot]),
                    "tou_ev_kw": float(tou_ev[slot]),
                    "uncontrolled_grid_kw": float(uncontrolled_grid[slot]),
                    "tou_grid_kw": float(tou_grid[slot]),
                }
            )

    metrics = pd.concat(all_metrics, ignore_index=True)
    modes = pd.concat(all_modes, ignore_index=True) if all_modes else pd.DataFrame()
    metrics.to_csv(output / "strategy_metrics_all_scenarios.csv", index=False)
    modes.to_csv(output / "information_mode_metrics_all_scenarios.csv", index=False)
    rebound_summary = save_rebound_artifacts(
        rebound_rows,
        profile_rows,
        output,
    )
    (output / "run_metadata.json").write_text(
        json.dumps(
            {
                "scenario_count": len(scenarios),
                "session_count": sum(len(item.sessions) for item in scenarios),
                "forecast_test_start_utc": test_start.isoformat(),
                "forecast_scenario_count": int(metrics.loc[metrics["strategy"].eq("lp_forecast"), "scenario_id"].nunique()),
                "emissions_factor_kg_co2_per_kwh": 0.225209,
                "pv_capacity_kwp": 100.0,
                "pv_performance_ratio": 0.8,
                "base_load_kw": 41.66666666666666,
                "primary_lp_weights": {
                    "cost": 1,
                    "peak": 5,
                    "solar": 2,
                    "description": "Chosen priorities; objectives are normalized before weighting",
                },
                "sensitivity_lp_weights": {
                    "cost": 1,
                    "peak": 1,
                    "solar": 1,
                    "description": "Equal-weight sensitivity only",
                },
                "notes": [
                    "Forecast LP results are restricted to scenarios fully covered by the chronological test-tail predictions.",
                    "All metrics are evaluated against actual scenario inputs.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary = (
        metrics.groupby("strategy", as_index=False)
        .agg(
            scenarios=("scenario_id", "nunique"),
            feasible=("feasible", "all"),
            charging_cost_mean=("charging_cost", "mean"),
            peak_grid_import_kw_mean=("peak_grid_import_kw", "mean"),
            solar_energy_to_ev_kwh_mean=("solar_energy_to_ev_kwh", "mean"),
            grid_energy_imported_kwh_mean=("grid_energy_imported_kwh", "mean"),
            co2_kg_mean=("co2_kg", "mean"),
        )
    )
    summary.to_csv(output / "strategy_summary.csv", index=False)
    label_map = {
        "lp_equal_weights_sensitivity": "1:1:1 sensitivity",
        "lp_forecast": "Forecast LP",
        "lp_perfect_foresight": "Perfect-foresight LP",
        "tou": "TOU",
        "uncontrolled": "Uncontrolled",
    }
    plot_summary = summary.copy()
    plot_summary["label"] = plot_summary["strategy"].map(label_map)
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(11.5, 4.8),
        sharex=False,
        gridspec_kw={"wspace": 0.32},
    )
    left = plot_summary.plot.bar(
        x="label",
        y="charging_cost_mean",
        ax=axes[0],
        legend=False,
        color="#4C78A8",
    )
    left.set_ylabel("Mean charging cost")
    left.set_xlabel("")
    left.set_title("Mean Charging Cost")
    left.tick_params(axis="x", labelrotation=35)
    for tick in left.get_xticklabels():
        tick.set_horizontalalignment("right")
    left.margins(x=0.08)
    left.bar_label(left.containers[0], fmt="%.3f", padding=3, fontsize=8)

    right = plot_summary.plot.bar(
        x="label",
        y="peak_grid_import_kw_mean",
        ax=axes[1],
        legend=False,
        color="#F58518",
    )
    right.set_ylabel("Mean peak grid import (kW)")
    right.set_xlabel("")
    right.set_title("Mean Peak Grid Import")
    right.tick_params(axis="x", labelrotation=35)
    for tick in right.get_xticklabels():
        tick.set_horizontalalignment("right")
    right.margins(x=0.08)
    right.bar_label(right.containers[0], fmt="%.1f", padding=3, fontsize=8)

    figure.suptitle("Charging Strategy Comparison", fontsize=14, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    figure.savefig(output / "strategy_summary.png", dpi=220, bbox_inches="tight")
    plt.close(figure)
    return summary


if __name__ == "__main__":
    result = run_real_experiment()
    print(result.to_string(index=False))
