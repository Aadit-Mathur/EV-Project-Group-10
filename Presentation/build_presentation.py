"""Build presentation tables, charts, and the locally ignored PowerPoint deck."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / "Presentation"
TABLES = PRESENTATION / "tables"
ASSETS = PRESENTATION / "assets"
DECK_PATH = PRESENTATION / "EV_Smart_Charging_Presentation.pptx"

SOURCE_RESULTS = ROOT / "Results" / "real_data"
SOURCE_PACKAGE = ROOT / "Data" / "normalised" / "ev_common_base"
SCENARIO_ID = "2018-06-11"
CORE_ORDER = ["uncontrolled", "tou", "lp_perfect_foresight"]
CORE_LABELS = {
    "uncontrolled": "Uncontrolled",
    "tou": "TOU",
    "lp_perfect_foresight": "LP smart charging",
}
COLORS = {
    "navy": "#10263A",
    "navy_light": "#1A3A54",
    "cyan": "#19A7B8",
    "teal": "#087E8B",
    "lime": "#A7C957",
    "gold": "#F2B84B",
    "coral": "#E4775C",
    "blue": "#4C78A8",
    "ink": "#193247",
    "muted": "#627789",
    "paper": "#F3F7FA",
    "white": "#FFFFFF",
    "line": "#DCE5EC",
    "soft_cyan": "#E7F5F6",
    "soft_gold": "#FFF4DD",
    "soft_lime": "#EFF5E2",
    "soft_coral": "#FCECE7",
}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "text.color": COLORS["ink"],
        "axes.labelcolor": COLORS["muted"],
        "xtick.color": COLORS["muted"],
        "ytick.color": COLORS["muted"],
        "axes.edgecolor": COLORS["line"],
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": COLORS["white"],
        "axes.facecolor": COLORS["white"],
        "savefig.facecolor": COLORS["white"],
    }
)


def _read_sources() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    summary = pd.read_csv(SOURCE_RESULTS / "strategy_summary.csv")
    all_metrics = pd.read_csv(SOURCE_RESULTS / "strategy_metrics_all_scenarios.csv")
    information_modes = pd.read_csv(
        SOURCE_RESULTS / "information_mode_metrics_all_scenarios.csv"
    )
    forecast_metrics = json.loads(
        (SOURCE_RESULTS / "forecasts" / "solar_kw_forecast_metrics.json").read_text(
            encoding="utf-8"
        )
    )
    return summary, all_metrics, {
        "information_modes": information_modes,
        "forecast_metrics": forecast_metrics,
    }


def _write_tables(
    summary: pd.DataFrame,
    all_metrics: pd.DataFrame,
    extra: dict,
) -> dict[str, pd.DataFrame]:
    TABLES.mkdir(parents=True, exist_ok=True)
    modes = extra["information_modes"]
    forecast_metrics = extra["forecast_metrics"]["metrics"]

    core = summary[summary["strategy"].isin(CORE_ORDER)].copy()
    core["strategy"] = pd.Categorical(core["strategy"], CORE_ORDER, ordered=True)
    core = core.sort_values("strategy")
    core_rows = all_metrics[all_metrics["strategy"].isin(CORE_ORDER)]
    scenario_counts = core_rows.groupby("strategy")["scenario_id"].nunique()
    if len(scenario_counts) != len(CORE_ORDER) or not scenario_counts.eq(45).all():
        raise ValueError("Core strategies must each cover the same 45 scenarios")
    if not core_rows["feasible"].astype(bool).all():
        raise ValueError("Core strategy results include an infeasible schedule")
    core_table = pd.DataFrame(
        {
            "strategy": core["strategy"].astype(str).map(CORE_LABELS),
            "scenarios": core["scenarios"].astype(int),
            "feasible": core["feasible"].astype(bool),
            "mean_incremental_charging_cost_usd_per_scenario": core["charging_cost_mean"],
            "mean_peak_grid_import_kw": core["peak_grid_import_kw_mean"],
            "mean_solar_to_ev_kwh_per_scenario": core["solar_energy_to_ev_kwh_mean"],
            "mean_grid_energy_imported_kwh_per_scenario": core[
                "grid_energy_imported_kwh_mean"
            ],
            "mean_co2_kg_per_scenario": core["co2_kg_mean"],
        }
    )
    core_table.to_csv(TABLES / "core_strategy_results.csv", index=False, float_format="%.6f")

    sensitivity = summary[
        summary["strategy"].isin(["lp_perfect_foresight", "lp_equal_weights_sensitivity"])
    ].copy()
    sensitivity["label"] = sensitivity["strategy"].map(
        {
            "lp_perfect_foresight": "Primary LP (1:5:2)",
            "lp_equal_weights_sensitivity": "Sensitivity (1:1:1)",
        }
    )
    sensitivity_table = pd.DataFrame(
        {
            "run": sensitivity["label"],
            "scenarios": sensitivity["scenarios"].astype(int),
            "mean_incremental_charging_cost_usd_per_scenario": sensitivity["charging_cost_mean"],
            "mean_peak_grid_import_kw": sensitivity["peak_grid_import_kw_mean"],
            "mean_solar_to_ev_kwh_per_scenario": sensitivity[
                "solar_energy_to_ev_kwh_mean"
            ],
        }
    )
    sensitivity_table.to_csv(
        TABLES / "weight_sensitivity.csv", index=False, float_format="%.6f"
    )

    forecast_subset = modes[modes["forecast_used"].astype(bool)].copy()
    forecast_group = (
        forecast_subset.groupby("information_mode", as_index=False)
        .agg(
            scenarios=("scenario_id", "nunique"),
            feasible=("feasible", "all"),
            mean_incremental_charging_cost_usd_per_scenario=("charging_cost", "mean"),
            mean_peak_grid_import_kw=("peak_grid_import_kw", "mean"),
            mean_solar_to_ev_kwh_per_scenario=("solar_energy_to_ev_kwh", "mean"),
            mean_grid_energy_imported_kwh_per_scenario=("grid_energy_imported_kwh", "mean"),
            mean_co2_kg_per_scenario=("co2_kg", "mean"),
        )
    )
    mode_labels = {
        "lp_forecast": "Forecast-based LP",
        "lp_perfect_foresight": "Perfect-foresight LP",
    }
    forecast_table = forecast_group.copy()
    forecast_table["information_mode"] = forecast_table["information_mode"].map(mode_labels)
    forecast_table.to_csv(
        TABLES / "forecast_lp_comparison.csv", index=False, float_format="%.6f"
    )

    forecast_table_metrics = pd.DataFrame(
        [
            {
                "model": "Random Forest",
                "test_mae_kw": forecast_metrics["model_mae"],
                "test_rmse_kw": forecast_metrics["model_rmse"],
                "validation_mae_kw": forecast_metrics["validation_model_mae"],
                "validation_rmse_kw": forecast_metrics["validation_model_rmse"],
            },
            {
                "model": "Persistence (same-hour historical)",
                "test_mae_kw": forecast_metrics["persistence_mae"],
                "test_rmse_kw": forecast_metrics["persistence_rmse"],
                "validation_mae_kw": None,
                "validation_rmse_kw": None,
            },
        ]
    )
    forecast_table_metrics.to_csv(
        TABLES / "solar_forecast_metrics.csv", index=False, float_format="%.6f"
    )

    scenario_dir = SOURCE_RESULTS / "scenarios" / SCENARIO_ID
    scenario_metrics = pd.read_csv(scenario_dir / "strategy_metrics.csv")
    scenario_metrics = scenario_metrics[scenario_metrics["strategy"].isin(CORE_ORDER)].copy()
    scenario_metrics["strategy"] = pd.Categorical(
        scenario_metrics["strategy"], CORE_ORDER, ordered=True
    )
    scenario_metrics = scenario_metrics.sort_values("strategy")
    representative = pd.DataFrame(
        {
            "scenario_id": SCENARIO_ID,
            "strategy": scenario_metrics["strategy"].astype(str).map(CORE_LABELS),
            "feasible": scenario_metrics["feasible"].astype(bool),
            "incremental_charging_cost_usd": scenario_metrics["charging_cost"],
            "peak_grid_import_kw": scenario_metrics["peak_grid_import_kw"],
            "solar_to_ev_kwh": scenario_metrics["solar_energy_to_ev_kwh"],
        }
    )
    representative.to_csv(
        TABLES / "representative_scenario_results.csv",
        index=False,
        float_format="%.6f",
    )

    assumptions = pd.DataFrame(
        [
            ("Study scope", "100 ACN sessions across 45 local arrival-date scenarios"),
            ("EV session fields", "Telemetry timestamps and cumulative energy are proxies"),
            ("EV power limit", "7.2 kW per EV; modeling assumption"),
            ("Time step", "Hourly slots; scenario windows shared by all strategies"),
            ("Solar", "Open-Meteo ERA5 Pasadena GHI; 100 kWp × 0.80 PR PV model"),
            ("Non-EV base load", "Constant 41.6667 kW; modeled assumption"),
            ("Tariff", "SCE TOU-EV-4; later TOU period definitions mapped approximately"),
            ("Emissions", "0.225209 kg CO₂/kWh, EPA eGRID2018 CAMX average factor"),
            ("System boundary", "Composite Pasadena-area simulation, not one measured facility"),
        ],
        columns=["item", "presentation_note"],
    )
    assumptions.to_csv(TABLES / "assumptions_and_provenance.csv", index=False)

    return {
        "core": core_table,
        "sensitivity": sensitivity_table,
        "forecast_modes": forecast_table,
        "forecast_metrics": forecast_table_metrics,
        "representative": representative,
        "assumptions": assumptions,
    }


def _save_core_chart(core: pd.DataFrame) -> Path:
    ASSETS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), constrained_layout=True)
    labels = core["strategy"].tolist()
    colors = [COLORS["blue"], COLORS["gold"], COLORS["cyan"]]
    metrics = [
        (
            "mean_incremental_charging_cost_usd_per_scenario",
            "Incremental EV-related cost",
            "USD / scenario",
            2,
        ),
        (
            "mean_solar_to_ev_kwh_per_scenario",
            "Solar used by EVs",
            "kWh / scenario",
            2,
        ),
        ("mean_peak_grid_import_kw", "Peak grid import", "kW", 1),
    ]
    for ax, (column, title, ylabel, precision) in zip(axes, metrics):
        values = core[column].to_numpy(dtype=float)
        bars = ax.bar(range(len(labels)), values, color=colors, width=0.62, zorder=3)
        ax.set_title(title, loc="left", fontweight="bold", color=COLORS["ink"], pad=12)
        ax.set_ylabel(ylabel)
        ax.set_xticks(range(len(labels)), labels, rotation=18, ha="right")
        ax.grid(axis="y", color=COLORS["line"], linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.bar_label(
            bars,
            labels=[f"{v:.{precision}f}" for v in values],
            padding=4,
            fontsize=9,
            color=COLORS["ink"],
        )
        ax.set_ylim(0, max(values) * 1.24 if max(values) else 1)
    fig.suptitle(
        "Core strategies · same 45 scenarios",
        x=0.02,
        y=1.05,
        ha="left",
        fontsize=16,
        fontweight="bold",
        color=COLORS["navy"],
    )
    path = ASSETS / "core_strategy_comparison.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def _save_schedule_chart() -> Path:
    scenario_dir = SOURCE_RESULTS / "scenarios" / SCENARIO_ID
    baseline = pd.read_csv(SOURCE_PACKAGE / "common_hourly_baseline.csv")
    baseline["timestamp_utc"] = pd.to_datetime(baseline["timestamp_utc"], utc=True)
    baseline["timestamp_local"] = baseline["timestamp_utc"].dt.tz_convert(
        "America/Los_Angeles"
    )
    baseline = baseline[
        baseline["timestamp_local"].dt.strftime("%Y-%m-%d").eq(SCENARIO_ID)
    ].copy()
    if baseline.empty:
        raise ValueError(f"No baseline inputs found for representative scenario {SCENARIO_ID}")

    fig, ax = plt.subplots(figsize=(11.6, 4.3), constrained_layout=True)
    line_colors = {
        "uncontrolled": COLORS["blue"],
        "tou": COLORS["gold"],
        "lp_perfect_foresight": COLORS["cyan"],
    }
    for strategy in CORE_ORDER:
        schedule_path = scenario_dir / f"{strategy}_schedule.csv"
        schedule = pd.read_csv(schedule_path)
        schedule["timestamp"] = pd.to_datetime(schedule["timestamp"], utc=True)
        aggregate = schedule.groupby("timestamp")["charging_power_kw"].sum()
        values = baseline["timestamp_utc"].map(aggregate).fillna(0.0)
        ax.step(
            baseline["timestamp_local"],
            values,
            where="post",
            linewidth=2.2,
            color=line_colors[strategy],
            label=CORE_LABELS[strategy],
        )
    ax.plot(
        baseline["timestamp_local"],
        baseline["pv_generation_kw"],
        color=COLORS["lime"],
        linewidth=2,
        linestyle=(0, (4, 3)),
        label="Modeled solar generation",
    )
    ax.set_title(
        f"One illustrative day · {SCENARIO_ID}",
        loc="left",
        fontweight="bold",
        color=COLORS["ink"],
        pad=12,
    )
    ax.set_ylabel("Power (kW)")
    ax.set_xlabel("Local time · America/Los_Angeles")
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(0, 24, 4), tz=baseline["timestamp_local"].dt.tz))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=baseline["timestamp_local"].dt.tz))
    ax.grid(axis="y", color=COLORS["line"], linewidth=0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    path = ASSETS / "representative_schedule_profiles.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def _save_forecast_chart(forecast_metrics: pd.DataFrame) -> Path:
    predictions = pd.read_csv(SOURCE_RESULTS / "forecasts" / "solar_kw_forecast.csv")
    predictions["timestamp"] = pd.to_datetime(predictions["timestamp"], utc=True).dt.tz_convert(
        "America/Los_Angeles"
    )
    metrics = forecast_metrics.set_index("model")
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(12.4, 4.3), gridspec_kw={"width_ratios": [1.75, 1]}
    )
    ax.plot(
        predictions["timestamp"],
        predictions["actual"],
        color=COLORS["navy"],
        linewidth=2.1,
        label="Actual solar",
    )
    ax.plot(
        predictions["timestamp"],
        predictions["predicted"],
        color=COLORS["cyan"],
        linewidth=1.8,
        label="Random Forest",
    )
    ax.plot(
        predictions["timestamp"],
        predictions["persistence"],
        color=COLORS["gold"],
        linewidth=1.4,
        linestyle="--",
        label="Persistence",
    )
    ax.set_title("Held-out solar test window", loc="left", fontweight="bold")
    ax.set_ylabel("Solar power (kW)")
    ax.set_xlabel("Local time · America/Los_Angeles")
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d", tz=predictions["timestamp"].dt.tz))
    ax.grid(axis="y", color=COLORS["line"], linewidth=0.8)
    ax.legend(frameon=False, ncol=1, loc="upper left")

    model_names = ["Random Forest", "Persistence (same-hour historical)"]
    mae = [metrics.loc[name, "test_mae_kw"] for name in model_names]
    rmse = [metrics.loc[name, "test_rmse_kw"] for name in model_names]
    positions = [0, 1]
    bars = bx.bar(
        positions,
        mae,
        color=[COLORS["cyan"], COLORS["gold"]],
        width=0.58,
        zorder=3,
    )
    bx.set_xticks(positions, ["Random\nForest", "Persistence"])
    bx.set_ylabel("MAE (kW) · lower is better")
    bx.set_title("Test forecast error", loc="left", fontweight="bold")
    bx.set_ylim(0, max(mae) * 1.5)
    bx.grid(axis="y", color=COLORS["line"], linewidth=0.8, zorder=0)
    bx.set_axisbelow(True)
    bx.spines["left"].set_visible(False)
    bx.tick_params(axis="y", length=0)
    bx.bar_label(bars, labels=[f"{value:.2f}" for value in mae], padding=4, fontsize=9)
    for pos, value in zip(positions, rmse):
        bx.text(
            pos,
            mae[pos] + max(mae) * 0.14,
            f"RMSE {value:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color=COLORS["muted"],
        )
    fig.suptitle(
        "Random Forest did not beat the persistence baseline",
        x=0.02,
        ha="left",
        fontsize=15,
        fontweight="bold",
        color=COLORS["navy"],
    )
    path = ASSETS / "solar_forecast_evaluation.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def _rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value.lstrip("#"))


def _add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    color: str | None = None,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    font: str = "Aptos",
    margin: float = 0,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color or COLORS["ink"])
    return box


def _add_shape(
    slide,
    kind,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    line: str | None = None,
):
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    if line:
        shape.line.color.rgb = _rgb(line)
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    return shape


def _add_card(slide, x, y, w, h, fill=COLORS["white"], line=COLORS["line"]):
    return _add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, line)


def _add_pill(slide, text, x, y, w, fill, text_color=COLORS["navy"]):
    _add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.32, fill)
    _add_text(
        slide,
        text.upper(),
        x + 0.06,
        y + 0.055,
        w - 0.12,
        0.2,
        size=8,
        color=text_color,
        bold=True,
        align=PP_ALIGN.CENTER,
    )


def _add_header(slide, section, title, speaker, timing, slide_number):
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, 7.5, COLORS["paper"])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, 0.1, COLORS["cyan"])
    _add_text(slide, section.upper(), 0.62, 0.32, 6.7, 0.24, size=9, color=COLORS["teal"], bold=True)
    _add_text(slide, title, 0.62, 0.67, 11.6, 0.58, size=25, color=COLORS["navy"], bold=True)
    _add_pill(slide, f"{speaker} · {timing}", 10.55, 0.31, 2.15, COLORS["soft_cyan"], COLORS["teal"])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0.62, 7.12, 12.1, 0.012, COLORS["line"])
    _add_text(slide, "EV SMART CHARGING  ·  GROUP 10", 0.64, 7.2, 5.2, 0.18, size=8, color=COLORS["muted"])
    _add_text(slide, f"{slide_number:02d}", 12.1, 7.19, 0.55, 0.2, size=9, color=COLORS["muted"], align=PP_ALIGN.RIGHT)


def _add_image_fit(slide, path: Path, x: float, y: float, w: float, h: float):
    from PIL import Image

    with Image.open(path) as image:
        ratio = image.width / image.height
    target_ratio = w / h
    if ratio > target_ratio:
        width = w
        height = w / ratio
        top = y + (h - height) / 2
        left = x
    else:
        height = h
        width = h * ratio
        left = x + (w - width) / 2
        top = y
    slide.shapes.add_picture(str(path), Inches(left), Inches(top), width=Inches(width), height=Inches(height))


def _add_stat(slide, x, y, w, label, value, note, accent):
    _add_card(slide, x, y, w, 1.14)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, x, y, 0.07, 1.14, accent)
    _add_text(slide, label.upper(), x + 0.22, y + 0.14, w - 0.4, 0.2, size=8, color=COLORS["muted"], bold=True)
    _add_text(slide, value, x + 0.22, y + 0.38, w - 0.4, 0.4, size=23, color=COLORS["navy"], bold=True)
    _add_text(slide, note, x + 0.22, y + 0.83, w - 0.4, 0.2, size=8, color=COLORS["muted"])


def _build_deck(tables: dict[str, pd.DataFrame], chart_paths: dict[str, Path]) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    core = tables["core"].set_index("strategy")
    representative = tables["representative"].set_index("strategy")
    forecast = tables["forecast_modes"].set_index("information_mode")
    forecast_metrics = tables["forecast_metrics"].set_index("model")
    scenarios = int(tables["core"]["scenarios"].iloc[0])

    # 1. Cover
    slide = prs.slides.add_slide(blank)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, 7.5, COLORS["navy"])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 0.15, 7.5, COLORS["cyan"])
    _add_pill(slide, "GROUP 10  ·  ACADEMIC PRESENTATION", 0.82, 0.68, 3.55, COLORS["navy_light"], COLORS["white"])
    _add_text(slide, "EV smart\ncharging", 0.82, 1.55, 6.0, 1.8, size=42, color=COLORS["white"], bold=True)
    _add_text(
        slide,
        "A fair comparison of immediate, tariff-aware,\nand LP-based charging",
        0.88,
        3.7,
        5.8,
        0.8,
        size=19,
        color="#D8E5ED",
    )
    _add_text(
        slide,
        "Balancing charging cost, peak grid import, and solar use",
        0.88,
        5.38,
        5.9,
        0.42,
        size=13,
        color="#AFC6D4",
    )
    _add_pill(slide, "PRESENTER 1  ·  0:30", 0.88, 6.45, 2.0, COLORS["cyan"], COLORS["white"])
    for x, label, color in [(8.0, "COST", COLORS["gold"]), (9.55, "PEAK", COLORS["coral"]), (11.1, "SOLAR", COLORS["lime"])]:
        _add_shape(slide, MSO_SHAPE.OVAL, x, 2.45, 1.28, 1.28, color)
        _add_text(slide, label, x + 0.08, 2.91, 1.12, 0.28, size=12, color=COLORS["navy"], bold=True, align=PP_ALIGN.CENTER)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 9.24, 3.05, 0.3, 0.04, "#7892A2")
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 10.78, 3.05, 0.3, 0.04, "#7892A2")
    _add_text(slide, "Same EV needs. Different schedules. Measured trade-offs.", 7.5, 4.45, 5.0, 0.65, size=15, color=COLORS["white"], bold=True, align=PP_ALIGN.CENTER)

    # 2. Research question and fair comparison
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "01 · Research question", "What should smart charging optimize?", "Presenter 1", "0:45", 2)
    card_data = [
        ("LOWER COST", "Shift charging toward\nlower-price hours.", COLORS["soft_gold"], COLORS["gold"]),
        ("MANAGE PEAK", "Avoid unnecessary\ncoincident grid demand.", COLORS["soft_coral"], COLORS["coral"]),
        ("USE SOLAR", "Charge from solar surplus\nafter base load is served.", COLORS["soft_lime"], COLORS["lime"]),
    ]
    for i, (head, body, fill, accent) in enumerate(card_data):
        x = 0.68 + i * 4.1
        _add_card(slide, x, 1.75, 3.72, 2.05, fill, fill)
        _add_shape(slide, MSO_SHAPE.OVAL, x + 0.26, 2.02, 0.48, 0.48, accent)
        _add_text(slide, str(i + 1), x + 0.26, 2.13, 0.48, 0.16, size=10, color=COLORS["navy"], bold=True, align=PP_ALIGN.CENTER)
        _add_text(slide, head, x + 0.9, 2.06, 2.55, 0.26, size=12, color=COLORS["navy"], bold=True)
        _add_text(slide, body, x + 0.28, 2.72, 3.1, 0.62, size=16, color=COLORS["ink"], bold=True)
    _add_card(slide, 0.68, 4.28, 11.92, 1.2, COLORS["navy"], COLORS["navy"])
    _add_text(slide, "FAIR COMPARISON", 1.02, 4.56, 2.0, 0.25, size=10, color="#8FE1E7", bold=True)
    _add_text(
        slide,
        "Same EV sessions · same scenario windows · same evaluator",
        3.15,
        4.48,
        8.8,
        0.42,
        size=20,
        color=COLORS["white"],
        bold=True,
    )
    _add_text(slide, "Success means meeting feasible EV energy needs while comparing cost, grid import, solar use, and emissions consistently.", 0.8, 5.95, 11.6, 0.42, size=13, color=COLORS["muted"])

    # 3. Scenario and assumptions
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "02 · Data and scenario", "A composite Pasadena-area experiment", "Presenter 2", "1:15", 3)
    _add_stat(slide, 0.72, 1.62, 2.5, "EV sessions", "100", "ACN-Data sessions", COLORS["cyan"])
    _add_stat(slide, 3.38, 1.62, 2.5, "Scenarios", "45", "Arrival-date windows", COLORS["gold"])
    _add_stat(slide, 6.04, 1.62, 2.5, "Time step", "1 hour", "Shared across strategies", COLORS["lime"])
    _add_stat(slide, 8.70, 1.62, 3.85, "PV model", "100 kWp", "GHI-based · 0.80 performance ratio", COLORS["coral"])
    _add_card(slide, 0.72, 3.08, 7.05, 2.18)
    _add_text(slide, "INPUTS ALIGNED TO A COMMON TIMELINE", 1.0, 3.33, 6.4, 0.22, size=9, color=COLORS["teal"], bold=True)
    inputs = [
        ("EV sessions", "arrival/departure + energy proxy"),
        ("Solar", "ERA5 Pasadena irradiance → modeled PV"),
        ("Tariff", "SCE TOU-EV-4 energy rate"),
        ("Site load", "constant 41.6667 kW assumption"),
    ]
    for i, (label, detail) in enumerate(inputs):
        yy = 3.72 + i * 0.34
        _add_text(slide, label, 1.0, yy, 1.45, 0.2, size=11, color=COLORS["navy"], bold=True)
        _add_text(slide, detail, 2.62, yy, 4.75, 0.2, size=10, color=COLORS["muted"])
    _add_card(slide, 8.02, 3.08, 4.53, 2.18, COLORS["soft_gold"], COLORS["soft_gold"])
    _add_text(slide, "READ THE RESULTS AS A SIMULATION", 8.34, 3.42, 3.8, 0.3, size=10, color="#956B19", bold=True)
    _add_text(slide, "Session timestamps and energy are proxies. PV is modeled, the base load is assumed, and tariff-period mapping is approximate.", 8.34, 3.92, 3.6, 0.92, size=15, color=COLORS["ink"], bold=True)
    _add_text(slide, "This is not one complete measured charging-site record.", 0.82, 5.78, 11.5, 0.35, size=16, color=COLORS["navy"], bold=True)

    # 4. Three strategy cards
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "03 · Strategy comparison", "Three strategies, three scheduling logics", "Presenter 2", "1:00", 4)
    strategies = [
        ("01", "UNCONTROLLED", "Charge as soon as the EV is available.", "Immediate baseline", COLORS["blue"], COLORS["soft_cyan"]),
        ("02", "TOU", "Favor cheaper eligible tariff slots.", "Price-aware only", COLORS["gold"], COLORS["soft_gold"]),
        ("03", "LP SMART", "Coordinate cost, peak, and solar objectives.", "Continuous LP", COLORS["cyan"], COLORS["soft_lime"]),
    ]
    for i, (number, name, description, mode, accent, tint) in enumerate(strategies):
        x = 0.7 + i * 4.14
        _add_card(slide, x, 1.78, 3.8, 3.2, COLORS["white"])
        _add_shape(slide, MSO_SHAPE.RECTANGLE, x, 1.78, 3.8, 0.1, accent)
        _add_text(slide, number, x + 0.28, 2.15, 0.58, 0.48, size=25, color=accent, bold=True)
        _add_text(slide, name, x + 0.28, 2.85, 3.15, 0.3, size=15, color=COLORS["navy"], bold=True)
        _add_text(slide, description, x + 0.28, 3.38, 3.18, 0.82, size=17, color=COLORS["ink"])
        _add_pill(slide, mode, x + 0.28, 4.42, 2.2, tint, COLORS["navy"])
    _add_text(slide, "All strategies obey EV availability, power limits, and the same feasible energy target.", 0.85, 5.65, 11.7, 0.4, size=15, color=COLORS["muted"], bold=True, align=PP_ALIGN.CENTER)

    # 5. A schedule is a time series, not a spreadsheet screenshot
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "04 · Schedule artifact", "What the schedule actually tells us", "Presenter 3", "1:00", 5)
    _add_card(slide, 0.62, 1.55, 8.45, 4.92)
    _add_image_fit(slide, chart_paths["schedule"], 0.84, 1.78, 8.02, 4.42)
    _add_card(slide, 9.35, 1.55, 3.22, 4.92)
    _add_text(slide, "ONE EXAMPLE DAY", 9.65, 1.9, 2.6, 0.25, size=9, color=COLORS["teal"], bold=True)
    _add_text(slide, SCENARIO_ID, 9.65, 2.24, 2.6, 0.34, size=19, color=COLORS["navy"], bold=True)
    for idx, strategy in enumerate(CORE_ORDER):
        item = representative.loc[CORE_LABELS[strategy]]
        yy = 2.95 + idx * 0.74
        _add_text(slide, CORE_LABELS[strategy], 9.65, yy, 2.55, 0.22, size=10, color=COLORS["muted"], bold=True)
        _add_text(
            slide,
            f"${item['incremental_charging_cost_usd']:.2f} incremental  ·  {item['solar_to_ev_kwh']:.1f} kWh solar",
            9.65,
            yy + 0.27,
            2.55,
            0.28,
            size=11,
            color=COLORS["ink"],
            bold=True,
        )
    _add_text(slide, "Schedule CSV fields: scenario_id · timestamp · ev_id · charging_power_kw", 0.9, 6.62, 11.5, 0.25, size=10, color=COLORS["muted"])

    # 6. LP formulation
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "05 · Smart scheduling", "The LP coordinates three normalized goals", "You", "2:00", 6)
    _add_card(slide, 0.72, 1.55, 11.88, 1.24, COLORS["navy"], COLORS["navy"])
    _add_text(slide, "MINIMIZE", 1.02, 1.83, 1.35, 0.22, size=10, color="#8FE1E7", bold=True)
    _add_text(
        slide,
        "J = (C_EV / C_ref)  +  5(P_peak / P_ref)  −  2(S_EV_solar / E_EV_grid)",
        2.28,
        1.79,
        9.8,
        0.38,
        size=20,
        color=COLORS["white"],
        bold=True,
    )
    _add_text(slide, "Primary weights 1:5:2 · each term is normalized before weighting · selected project priorities", 1.02, 2.36, 10.8, 0.18, size=9, color="#C6D9E4")
    constraints = [
        ("EV energy", "Meet each feasible session's required energy exactly."),
        ("Availability", "Zero power outside connection windows; obey each EV's power cap."),
        ("Grid import", "Nonnegative import; no export. Peak covers every time slot."),
        ("Solar credit", "Base load first; credit EVs only for surplus solar."),
    ]
    for i, (head, detail) in enumerate(constraints):
        x = 0.72 + (i % 2) * 6.12
        y = 3.12 + (i // 2) * 1.38
        _add_card(slide, x, y, 5.76, 1.08)
        _add_shape(slide, MSO_SHAPE.OVAL, x + 0.22, y + 0.25, 0.5, 0.5, [COLORS["cyan"], COLORS["gold"], COLORS["coral"], COLORS["lime"]][i])
        _add_text(slide, str(i + 1), x + 0.22, y + 0.41, 0.5, 0.15, size=10, color=COLORS["navy"], bold=True, align=PP_ALIGN.CENTER)
        _add_text(slide, head, x + 0.92, y + 0.2, 4.35, 0.25, size=12, color=COLORS["navy"], bold=True)
        _add_text(slide, detail, x + 0.92, y + 0.52, 4.48, 0.36, size=11, color=COLORS["muted"])
    _add_text(slide, "Cost is incremental to the base-only grid profile · continuous LP, not MILP · emissions are evaluated, not optimized", 0.85, 6.25, 11.6, 0.3, size=11, color=COLORS["teal"], bold=True, align=PP_ALIGN.CENTER)

    # 7. Main results on equal scenario coverage
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "06 · Results", "LP lowers cost and uses more solar in this simulation", "You", "1:30", 7)
    _add_card(slide, 0.62, 1.53, 8.63, 4.95)
    _add_image_fit(slide, chart_paths["core"], 0.82, 1.77, 8.25, 4.45)
    _add_card(slide, 9.52, 1.53, 3.05, 4.95, COLORS["navy"], COLORS["navy"])
    lp = core.loc["LP smart charging"]
    uncontrolled = core.loc["Uncontrolled"]
    tou = core.loc["TOU"]
    _add_text(slide, f"{scenarios} SCENARIOS", 9.82, 1.9, 2.4, 0.25, size=10, color="#8FE1E7", bold=True)
    _add_text(slide, "Incremental cost", 9.82, 2.52, 1.8, 0.25, size=11, color="#C6D9E4")
    _add_text(slide, f"${lp['mean_incremental_charging_cost_usd_per_scenario']:.2f}", 9.82, 2.82, 2.25, 0.48, size=25, color=COLORS["white"], bold=True)
    _add_text(slide, f"vs ${tou['mean_incremental_charging_cost_usd_per_scenario']:.2f} TOU · ${uncontrolled['mean_incremental_charging_cost_usd_per_scenario']:.2f} uncontrolled", 9.82, 3.34, 2.35, 0.5, size=9, color="#C6D9E4")
    _add_text(slide, "Solar to EVs", 9.82, 4.07, 1.8, 0.25, size=11, color="#C6D9E4")
    _add_text(slide, f"{lp['mean_solar_to_ev_kwh_per_scenario']:.2f} kWh", 9.82, 4.38, 2.4, 0.45, size=22, color=COLORS["lime"], bold=True)
    _add_text(slide, f"about 2× the baseline mean", 9.82, 4.88, 2.3, 0.25, size=10, color="#C6D9E4")
    _add_text(slide, "Trade-off: mean peak was ~42.9 kW for both LP and uncontrolled; TOU was higher.", 9.82, 5.45, 2.3, 0.68, size=10, color=COLORS["white"], bold=True)

    # 8. Forecast and benchmark caveat
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "07 · Forecasting", "Forecast accuracy matters—and the baseline won", "Presenter 3", "1:00", 8)
    _add_card(slide, 0.62, 1.53, 8.25, 4.95)
    _add_image_fit(slide, chart_paths["forecast"], 0.82, 1.82, 7.85, 4.35)
    _add_card(slide, 9.12, 1.53, 3.45, 4.95)
    rf = forecast_metrics.loc["Random Forest"]
    persistence = forecast_metrics.loc["Persistence (same-hour historical)"]
    _add_text(slide, "SOLAR TEST FORECAST", 9.43, 1.9, 2.78, 0.24, size=9, color=COLORS["teal"], bold=True)
    _add_text(slide, "MAE (kW)", 9.43, 2.42, 1.7, 0.22, size=10, color=COLORS["muted"])
    _add_text(slide, f"RF  {rf['test_mae_kw']:.3f}", 9.43, 2.74, 2.55, 0.32, size=17, color=COLORS["cyan"], bold=True)
    _add_text(slide, f"Persistence  {persistence['test_mae_kw']:.3f}", 9.43, 3.12, 2.7, 0.3, size=13, color=COLORS["ink"], bold=True)
    frow = forecast.loc["Forecast-based LP"]
    prow = forecast.loc["Perfect-foresight LP"]
    _add_text(slide, "LP information comparison", 9.43, 3.78, 2.7, 0.24, size=10, color=COLORS["muted"], bold=True)
    _add_text(slide, f"{int(frow['scenarios'])} held-out scenarios", 9.43, 4.12, 2.7, 0.3, size=16, color=COLORS["navy"], bold=True)
    _add_text(
        slide,
        f"Forecast LP cost ${frow['mean_incremental_charging_cost_usd_per_scenario']:.3f}; perfect foresight ${prow['mean_incremental_charging_cost_usd_per_scenario']:.3f}.",
        9.43,
        4.62,
        2.7,
        0.7,
        size=11,
        color=COLORS["ink"],
    )
    _add_text(slide, "Perfect foresight is an ideal-information benchmark—not an operational forecast.", 9.43, 5.55, 2.7, 0.6, size=10, color=COLORS["teal"], bold=True)

    # 9. Conclusion and limitations
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "08 · Takeaways", "A useful shift in charging—under explicit assumptions", "You", "1:00", 9)
    takeaways = [
        ("01", "LP combines tariff, grid, and solar signals.", COLORS["cyan"]),
        ("02", "The strongest measured gains are lower cost and higher solar-to-EV use.", COLORS["lime"]),
        ("03", "Peak and CO₂ gains are modest in this dataset; don’t overclaim them.", COLORS["gold"]),
    ]
    for i, (number, text, accent) in enumerate(takeaways):
        yy = 1.72 + i * 1.05
        _add_shape(slide, MSO_SHAPE.OVAL, 0.9, yy + 0.04, 0.56, 0.56, accent)
        _add_text(slide, number, 0.9, yy + 0.22, 0.56, 0.15, size=9, color=COLORS["navy"], bold=True, align=PP_ALIGN.CENTER)
        _add_text(slide, text, 1.72, yy, 10.2, 0.62, size=19, color=COLORS["navy"], bold=True)
    _add_card(slide, 0.82, 5.12, 11.65, 1.05, COLORS["soft_gold"], COLORS["soft_gold"])
    _add_text(slide, "LIMITATION TO SAY OUT LOUD", 1.15, 5.37, 2.45, 0.22, size=9, color="#956B19", bold=True)
    _add_text(slide, "Composite Pasadena-area simulation—not a guarantee of savings at a real site.", 3.62, 5.3, 8.28, 0.43, size=16, color=COLORS["ink"], bold=True)
    _add_text(slide, "Questions?", 0.9, 6.45, 2.5, 0.42, size=24, color=COLORS["teal"], bold=True)

    # 10. Sources and reproducibility (appendix)
    slide = prs.slides.add_slide(blank)
    _add_header(slide, "APPENDIX · Evidence", "Sources, assumptions, and reproducibility", "Appendix", "—", 10)
    source_rows = [
        ("EV sessions", "ACN-Data · California Garage (Caltech); 100 normalized sessions"),
        ("Solar", "Open-Meteo ERA5 Pasadena irradiance; PV derived from GHI"),
        ("Tariff", "SCE TOU-EV-4 2018 rates; approximate time-period mapping documented"),
        ("Emissions", "EPA eGRID2018 CAMX average · 0.225209 kg CO₂/kWh"),
        ("Site assumptions", "PV 100 kWp / PR 0.80 · base load 41.6667 kW · EV power cap 7.2 kW"),
    ]
    for i, (label, detail) in enumerate(source_rows):
        yy = 1.6 + i * 0.66
        _add_text(slide, label.upper(), 0.9, yy, 2.05, 0.23, size=9, color=COLORS["teal"], bold=True)
        _add_text(slide, detail, 3.1, yy - 0.02, 9.0, 0.38, size=12, color=COLORS["ink"])
    _add_card(slide, 0.82, 5.25, 11.7, 1.05, COLORS["navy"], COLORS["navy"])
    _add_text(slide, "REPRODUCE", 1.12, 5.47, 1.35, 0.2, size=9, color="#8FE1E7", bold=True)
    _add_text(slide, "python -m pytest -q   ·   python -m Experiments.run_real", 2.65, 5.43, 8.9, 0.29, size=14, color=COLORS["white"], bold=True)
    _add_text(slide, "Presentation tables and charts are derived from saved CSV/JSON outputs; the deck is generated by Presentation/build_presentation.py.", 0.9, 6.56, 11.4, 0.25, size=9, color=COLORS["muted"])

    prs.core_properties.title = "EV Smart Charging — Group 10"
    prs.core_properties.subject = "Academic presentation: uncontrolled, TOU, LP smart charging, and solar forecasting"
    prs.core_properties.author = "Group 10"
    prs.save(DECK_PATH)


def build() -> None:
    summary, all_metrics, extra = _read_sources()
    tables = _write_tables(summary, all_metrics, extra)
    chart_paths = {
        "core": _save_core_chart(tables["core"]),
        "schedule": _save_schedule_chart(),
        "forecast": _save_forecast_chart(tables["forecast_metrics"]),
    }
    _build_deck(tables, chart_paths)
    print(f"PowerPoint: {DECK_PATH}")
    print(f"Tables: {TABLES}")
    print(f"Charts: {ASSETS}")
    print(f"Slides: 10 (9 presentation slides + 1 source appendix)")
    print(f"Core comparison scenarios: {tables['core']['scenarios'].tolist()}")
    print(
        "Forecast LP scenarios: "
        f"{tables['forecast_modes']['scenarios'].tolist()}"
    )


if __name__ == "__main__":
    build()
