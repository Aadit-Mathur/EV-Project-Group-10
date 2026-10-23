# Synthetic LP tests

This folder provides a deterministic 24-hour scenario until the project
datasets are available.

## Run the optimizer

From the repository root:

```text
.\.venv\Scripts\python.exe -m LP_Optimizer.synthetic_test.run_synthetic
```

The runner solves both:

1. forecast-based LP using intentionally imperfect solar and base-load inputs;
2. perfect-foresight LP using the actual synthetic scenario.

It prints both schedules and writes these files to `outputs`:

- `forecast_schedule.csv`
- `forecast_slot_summary.csv`
- `perfect_foresight_schedule.csv`
- `perfect_foresight_slot_summary.csv`

The schedule uses one-hour slots. Arrival is inclusive and departure is
exclusive. All synthetic sessions use the default 0.9 battery charging
efficiency.

To use the scenario in another script:

```python
from LP_Optimizer import run_lp
from LP_Optimizer.synthetic_test.scenario import (
    build_synthetic_forecast,
    build_synthetic_scenario,
)

scenario = build_synthetic_scenario()
result = run_lp(scenario, forecast_inputs=build_synthetic_forecast())
print(result.schedule)
```
