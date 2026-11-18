"""Run the normalized-data EV charging experiment."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

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

    metrics = pd.concat(all_metrics, ignore_index=True)
    modes = pd.concat(all_modes, ignore_index=True) if all_modes else pd.DataFrame()
    metrics.to_csv(output / "strategy_metrics_all_scenarios.csv", index=False)
    modes.to_csv(output / "information_mode_metrics_all_scenarios.csv", index=False)
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
    figure, axes = plt.subplots(1, 2, figsize=(12, 4))
    summary.plot.bar(x="strategy", y="charging_cost_mean", ax=axes[0], legend=False)
    axes[0].set_ylabel("Mean incremental charging cost")
    summary.plot.bar(x="strategy", y="peak_grid_import_kw_mean", ax=axes[1], legend=False)
    axes[1].set_ylabel("Mean peak grid import (kW)")
    figure.tight_layout()
    figure.savefig(output / "strategy_summary.png", dpi=150)
    plt.close(figure)
    return summary


if __name__ == "__main__":
    result = run_real_experiment()
    print(result.to_string(index=False))
