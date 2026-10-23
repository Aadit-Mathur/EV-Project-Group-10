# EV Smart Charging — Linear Optimizer

`optimizer.py` implements Role 3's continuous LP smart-charging scheduler. It
uses PuLP with CBC and does not introduce binary variables.

## Model

For every EV `i` and time slot `t`, `P[i,t] >= 0` is charging power in kW.
Arrival is inclusive and departure is exclusive. Power is zero outside the
availability window and is capped by the EV's maximum power while connected.

For battery-side requirements, the energy equality is:

```
sum(P[i,t] * slot_hours * efficiency[i]) = required_battery_energy[i]
```

The model also contains nonnegative grid-import variables, a nonnegative peak
variable, and `u[t]`, the solar power credited to EV charging:

```
grid[t] >= base_load[t] + sum_i(P[i,t]) - solar[t]
u[t] <= sum_i(P[i,t])
u[t] <= max(0, solar[t] - base_load[t])
peak >= grid[t]
```

No grid export is modeled; excess solar is curtailed. The objective is the
roadmap's normalized objective:

```
(C_EV / C_ref) + 5 * (P_peak / P_ref) - 2 * (S_EV_solar / E_EV_grid)
```

`C_EV` is incremental grid-import cost over the base-only grid profile,
`C_ref = mean(price) * E_EV_grid`, and `P_ref` is the maximum possible
base-load-plus-available-EV-power profile. Solar is credited only after base
load is served.

## Usage

```python
from LP_Optimizer.optimizer import ChargingScenario, EVSession, run_lp

scenario = ChargingScenario(
    prices=[2.0, 1.0, 3.0],
    base_load_kw=[2.0, 2.0, 2.0],
    solar_kw=[0.0, 3.0, 0.0],
    sessions=[EVSession("ev-1", 0, 3, 1.8, 1.0)],
)
result = run_lp(scenario)
print(result.schedule)
print(result.metrics)
```

Forecast mode reuses exactly the same model:

```python
forecast_result = run_lp(
    scenario,
    forecast_inputs={"solar_kw": predicted_solar, "base_load_kw": predicted_base},
)
perfect_foresight_result = run_lp(scenario)
```

The function rejects physically infeasible sessions before solving and performs
independent post-solve checks for energy, availability, power, and grid-import
constraints.

Run the focused tests with:

```text
python -m pytest -q
```
