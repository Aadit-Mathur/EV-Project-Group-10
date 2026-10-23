"""Run the LP optimizer against deterministic synthetic data.

Run from the repository root:

    python -m LP_Optimizer.synthetic_test.run_synthetic
"""

from pathlib import Path

from LP_Optimizer import run_lp
from LP_Optimizer.synthetic_test.scenario import (
    build_synthetic_forecast,
    build_synthetic_scenario,
)


def main() -> None:
    scenario = build_synthetic_scenario()
    forecast_result = run_lp(scenario, forecast_inputs=build_synthetic_forecast())
    perfect_result = run_lp(scenario)

    output_dir = Path(__file__).with_name("outputs")
    output_dir.mkdir(exist_ok=True)
    forecast_result.schedule.to_csv(output_dir / "forecast_schedule.csv", index=False)
    forecast_result.slot_summary.to_csv(output_dir / "forecast_slot_summary.csv", index=False)
    perfect_result.schedule.to_csv(output_dir / "perfect_foresight_schedule.csv", index=False)
    perfect_result.slot_summary.to_csv(output_dir / "perfect_foresight_slot_summary.csv", index=False)

    print("Forecast-based LP")
    print(f"Status: {forecast_result.status}")
    print(f"Objective: {forecast_result.objective:.6f}")
    print(forecast_result.schedule.to_string(index=False))
    print("\nForecast metrics:")
    _print_metrics(forecast_result.metrics)

    print("\nPerfect-foresight LP")
    print(f"Status: {perfect_result.status}")
    print(f"Objective: {perfect_result.objective:.6f}")
    print(perfect_result.schedule.to_string(index=False))
    print("\nPerfect-foresight metrics:")
    _print_metrics(perfect_result.metrics)
    print(f"\nCSV results saved under {output_dir}")


def _print_metrics(metrics: dict[str, float]) -> None:
    for name, value in metrics.items():
        print(f"{name}: {value:.6f}")


if __name__ == "__main__":
    main()
