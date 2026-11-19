# EV Smart Charging Project Report

## 1. Objective

This project implements and compares three EV charging strategies:

1. Uncontrolled charging, which begins charging immediately.
2. Deterministic Time-of-Use (TOU) charging, which allocates energy to the
   cheapest eligible tariff slots.
3. Continuous Linear Programming (LP) smart charging, which optimizes
   normalized charging cost, grid peak, and solar utilization.

The LP is also compared in two information modes. Forecast-based LP uses
predicted solar generation, while perfect-foresight LP uses actual future solar
generation with the same sessions, tariff, objective, constraints, and solver.
Perfect foresight is a benchmark rather than a fourth charging strategy.

## 2. Authoritative Specification

Implementation follows
`Reference/EV_Smart_Charging_4_Person_Technical_Roadmap_Finalized.docx`,
including:

- One-hour slots and 24-hour scenario horizons.
- Continuous PuLP/CBC LP variables; no MILP or binary charging decisions.
- 100% delivered energy for feasible EV sessions.
- A 1:5:2 primary objective ratio for normalized cost, peak, and solar reward.
- Solar serving base load before EV charging, with no grid export.
- Grid-side treatment of the normalized EV energy values.
- A declared emissions metric with eGRID2018 CAMX factors for the normalized
  common-base package.
- Chronological forecasting with 70% training, 15% validation, and 15%
  held-out testing.

## 3. Dataset and Assumptions

The normalized common base contains 100 ACN charging sessions, hourly solar
generation for Pasadena, an assumed constant base load, reconstructed SCE
TOU-EV-4 hourly rates, and eGRID2018 CAMX emissions factors.

### 3.1 Data Normalization

The raw EV, solar, tariff, and emissions datasets were preprocessed into a
common normalized format. Timestamps were standardized to the California local
time convention and converted consistently across the source datasets. Units
were aligned, with power expressed in kW, energy in kWh, tariffs in
currency/kWh, and emissions in kg CO2/kWh. The hourly series were aligned to
the same timeline so that solar, base load, tariff, and grid-emissions values
could be matched to the same charging slots.

EV sessions were converted into structured records containing arrival time,
departure time, required energy, and maximum charging power. Missing values,
duplicate timestamps, anomalous energy records, and infeasible session data
were identified and documented. Assumptions such as the constant non-EV base
load and PV capacity were incorporated explicitly rather than hidden in the
strategy code. The resulting normalized datasets provide consistent, reproducible
inputs for uncontrolled charging, TOU charging, and LP smart charging.

The adopted primary grid-emissions factor is 0.225209 kg CO2/kWh. This replaces
the roadmap fallback of 0.4 kg CO2/kWh only because the implementation-ready
common base documents a location-matched CAMX factor.

We used the EPA eGRID2018 average emission factor for the CAMX
(California-Mexico) region because it matches the California-based study
geography. It represents average regional CO2 emitted per kWh generated.
We replaced the original provisional 0.4 kg CO2/kWh assumption with this more
geographically relevant, dataset-specific value.

The following are explicitly documented assumptions or proxies:

- ACN first/last telemetry timestamps represent arrival/departure proxies.
- Maximum cumulative session telemetry energy represents delivered energy.
- The cumulative ACN charging-energy value is treated as grid-side energy
  delivered through the charging station. It is not battery-side energy, so the
  0.9 charging-efficiency factor is not applied again. Applying 0.9 here would
  double-count charging losses and overestimate grid energy consumption.
- The 7.2 kW charger limit is a modelling assumption.
- PV is 100 kWp at 80% performance ratio using horizontal GHI.
- Base load is a constant 41.6667 kW.
- Tariff period mapping is approximate; demand and customer charges are
  excluded.
- The final scenario is a composite Pasadena-area simulation, not one complete
  measured facility reconstruction.

Full details are in `Data/EV_Assumptions_Implementation_Ready.md`,
`Data/normalised/ev_common_base/README.md`, and
`Data/normalised/ev_common_base/validation_report.txt`.

## 4. LP Formulation

For EV `i` and slot `t`, the decision variable is continuous charging power
`P[i,t]`. Each EV is constrained to zero charging outside its availability
window and to `Pmax[i]` while connected. Energy delivered by each session is
required to equal its normalized grid-side energy target.

For each slot:

- EV aggregate power is the sum of individual EV charging powers.
- Grid import is at least base load plus EV power minus solar.
- Grid import is nonnegative, so excess solar is curtailed.
- Solar credited to EV charging is at most EV power and at most surplus solar
  after base load.
- Peak grid import is at least every slot's grid import.

The primary objective minimizes:

```text
(C_EV / C_ref) + 5(P_peak / P_ref) - 2(S_EV_solar / E_EV_grid)
```

We selected 1:5:2 for the cost, peak, and solar-reward terms because peak
demand reduction is the highest project priority. Because cost, peak demand,
and solar use have different units, cost is normalized by `C_ref`, peak demand
by `P_ref`, and solar use by `E_EV_grid` before the weighted terms are added.
The weights reflect our chosen priorities rather than constants estimated from
data. We also ran an equal-weight 1:1:1 case to test whether the conclusions
are sensitive to this choice. It is reported only as a sensitivity check and
does not replace the primary 1:5:2 result.

## 5. Forecasting

The mandatory forecasting target is solar generation. The Random Forest
configuration uses 100 estimators and a fixed random seed. The same-hour
historical test target shifted by 24 hours is retained as a persistence
baseline.

The chronological split generated by the real-data workflow was:

- Training: through 2018-06-02 22:00 UTC.
- Validation: through 2018-06-09 22:00 UTC.
- Held-out test: 2018-06-09 23:00 through 2018-06-16 23:00 UTC.

Forecast metrics for this split were:

| Metric | Random Forest | Persistence |
|---|---:|---:|
| Test MAE (kW) | 1.558790 | 0.696805 |
| Test RMSE (kW) | 2.321885 | 2.043225 |
| Validation MAE (kW) | 0.784120 | N/A |
| Validation RMSE (kW) | 1.337041 | N/A |

The Random Forest model did not outperform persistence on the held-out test
period. The forecast-based LP comparison is therefore limited to the six
scenarios whose complete horizons fall within the held-out test prediction
coverage.

The machine-readable forecast metrics are in
`Results/real_data/forecasts/solar_kw_forecast_metrics.json`, and the timestamped
predictions and plot are in `Results/real_data/forecasts/`.

## 6. Real-Data Experiment Results

### Plain-language summary

Using the normalized ACN, solar, tariff, and base-load scenarios, LP smart
charging delivered the required EV energy while generally making better use of
low-cost and solar energy than uncontrolled charging or TOU charging. Across
45 scenarios, LP charging had the lowest mean charging cost and much higher
mean solar use than the other two baseline strategies. Uncontrolled charging
had the lowest or nearly lowest peak in some aggregated values, but its cost
and solar use were worse because it did not delay charging based on tariffs or
surplus solar. TOU charging reduced cost compared with uncontrolled charging,
but it did not explicitly minimize peak demand or maximize solar use.

The forecast comparison should be read carefully: it covers only six
held-out scenarios with complete 24-hour predictions. On those six cases,
forecast-based LP was slightly more expensive and produced a slightly higher
peak than perfect-foresight LP, but it used the same amount of solar. This
shows that uncertainty in solar forecasts had a small cost-and-peak effect in
the available test windows, while perfect foresight remains an ideal benchmark
rather than an achievable operational result.

The 1:1:1 sensitivity case is very close to the primary 1:5:2 result in the
main outcomes. This suggests that the overall advantage of LP charging is not
caused entirely by the selected peak weight. The project is a composite
Pasadena-area study, however, not a measurement of one real charging site, so
the numerical totals should be interpreted as evidence of comparative behavior
under the documented assumptions rather than guaranteed real-world savings.

Other notable observations are:

- LP smart charging used approximately 8.87 kWh of solar energy per scenario,
  almost twice the uncontrolled and TOU values of approximately 4.53 kWh and
  4.37 kWh.
- Grid-energy imported by the primary LP was about 618.70 kWh per scenario,
  compared with 623.04 kWh for uncontrolled charging and 623.20 kWh for TOU.
  The grid-import reduction was therefore modest even though charging cost
  improved substantially.
- TOU charging had the highest mean peak grid import among the three core
  strategies at 44.3183 kW, despite reducing mean charging cost relative to
  uncontrolled charging.
- The 1:1:1 sensitivity case reduced mean charging cost slightly relative to
  1:5:2 (0.4172 versus 0.4214), but increased mean peak from 42.8953 kW to
  43.0987 kW.
- Perfect foresight is best interpreted as an ideal information benchmark.
  Across the six complete held-out forecast scenarios, forecast-based LP stayed
  close to perfect foresight.
- The Random Forest did not outperform the 24-hour persistence baseline on the
  held-out period, indicating a forecasting opportunity rather than a
  demonstrated ML advantage.
- All 45 scenario schedules were feasible for the core and sensitivity runs.
  Forecast-LP coverage was deliberately restricted to six complete held-out
  scenarios.
- Mean CO2 followed mean grid import. The LP achieved 139.3362 kg compared
  with 140.3139 kg for uncontrolled charging and 140.3499 kg for TOU, a small
  reduction alongside the much larger cost and solar-utilization improvements.

An additional notable result is that changing the LP objective weights from
1:5:2 to 1:1:1 did not materially change mean peak grid import. The primary LP
result was 42.8953 kW and the equal-weight sensitivity result was 43.0987 kW,
which were both close to uncontrolled charging at 42.8891 kW. This suggests
that, under the selected data and simulation assumptions, the optimization
mainly improved charging cost and solar utilization rather than peak-demand
reduction. The constant base-load profile, solar availability, EV charging
requirements, and session availability windows may constrain the scope for
further peak reduction.

The real-data run processed 45 arrival-date scenarios and 100 EV sessions.
Every strategy schedule was feasible in the 45-scenario perfect-foresight,
uncontrolled, TOU, and sensitivity results.

Mean results across all 45 scenarios:

| Strategy | Feasible scenarios | Mean charging cost | Mean peak grid import (kW) | Mean solar-to-EV (kWh) | Mean grid energy (kWh) | Mean CO2 (kg) |
|---|---:|---:|---:|---:|---:|---:|
| Uncontrolled | 45 | 1.105246 | 42.889149 | 4.527591 | 623.038487 | 140.313875 |
| TOU | 45 | 0.679924 | 44.318300 | 4.367591 | 623.198487 | 140.349908 |
| LP perfect foresight | 45 | 0.421436 | 42.895261 | 8.868741 | 618.697337 | 139.336209 |
| LP equal-weight sensitivity | 45 | 0.417184 | 43.098701 | 8.868741 | 618.697337 | 139.336209 |

On the six held-out scenarios with complete forecast coverage:

| Information mode | Mean charging cost | Mean peak grid import (kW) | Mean solar-to-EV (kWh) |
|---|---:|---:|---:|
| Forecast-based LP | 0.613204 | 45.743516 | 9.231342 |
| Perfect foresight | 0.599997 | 45.569399 | 9.231342 |

For these six scenarios, forecast-based LP had mean charging cost 0.013207
higher than perfect foresight and mean peak grid import 0.174117 kW higher.
Solar-to-EV energy and grid/CO2 totals were identical because the model's
actual-input evaluation used the same physical scenario environment.

Perfect-foresight, controlled-evaluation artifacts for every scenario are in
`Results/real_data/strategy_metrics_all_scenarios.csv` and
`Results/real_data/information_mode_metrics_all_scenarios.csv`.

## 7. Verification

Automated verification covers:

- Baseline schedules and shared output schema.
- EV energy delivery, availability, and power limits.
- LP infeasible-session detection.
- Forecast and perfect-foresight LP information modes.
- Equal-weight sensitivity execution.
- Normalized scenario loading for 45 scenarios and 100 sessions.
- Chronological forecast split and MAE/RMSE reporting.

Test command:

```text
python -m pytest -q
```

Expected result: all tests pass.

## 8. Reproducibility

Install dependencies and run:

```text
python -m pytest -q
python -m Experiments.run_real
```

The real-data run regenerates per-scenario schedules, aggregate metrics,
forecast predictions, forecast metrics, and summary plots under
`Results/real_data/`.

## 9. Known Limitations

- This is a composite simulation with documented proxy and assumption fields,
  not a single measured site dataset.
- The base-load profile is constant rather than observed or forecasted.
- ACN timestamps and energy values are proxies for arrival, departure, and
  requested energy.
- The Random Forest did not outperform persistence on the held-out test period.
- Forecast-based LP coverage is 6 of 45 scenarios because the other scenario
  horizons occur before the held-out forecast tail.
- Tariff demand and customer charges are excluded.
- The emissions factor is an average factor and is used as an evaluation metric,
  not an LP objective term.
- Despite changing the LP weights from 1:5:2 to 1:1:1, mean peak grid import
  remained nearly unchanged and close to uncontrolled charging. This is an
  interesting dataset-specific result: the selected inputs may limit peak
  reduction, while the LP primarily improves cost and solar utilization.
- LP achieved almost twice the solar-to-EV energy of the uncontrolled and TOU
  baselines, while the reduction in imported grid energy and CO2 was relatively
  small.

## 10. References and Data Sources

### 10.1 Literature and Research

The experimental framework was informed by existing research on EV charging
coordination, grid-demand management, renewable-energy integration, and
forecast-aware scheduling.

1. Clement-Nyns, K., Haesen, E., & Driesen, J. (2010). “The Impact of Charging
   Plug-In Hybrid Electric Vehicles on a Residential Distribution Grid.” *IEEE
   Transactions on Power Systems*, 25(1), 371–380.
   https://doi.org/10.1109/TPWRS.2009.2036481
2. Deilami, S., Masoum, A. S., Moses, P. S., & Masoum, M. A. S. (2011).
   “Real-Time Coordination of Plug-In Electric Vehicle Charging in Smart Grids
   to Minimize Power Losses and Improve Voltage Profile.” *IEEE Transactions
   on Smart Grid*, 2(3), 456–467.
   https://doi.org/10.1109/TSG.2011.2159816
3. Ardakanian, O., Rosenberg, C., & Keshav, S. (2014). “Quantifying the Benefits
   of Extending Electric Vehicle Charging Deadlines with Solar Generation.”
   IEEE SmartGridComm.
   https://sites.ualberta.ca/~oardakan/files/sgc2014.pdf
4. Lee, Z. J., Li, T., & Low, S. H. (2019). “ACN-Data: Analysis and Applications
   of an Open EV Charging Dataset.” Proceedings of the Tenth ACM International
   Conference on Future Energy Systems.
   https://doi.org/10.1145/3307772.3328313

### 10.2 Data Sources

1. **EV charging sessions:** ACN-Data, California Garage (Caltech).
   https://ev.caltech.edu/dataset
2. **Solar generation:** Hourly Global Horizontal Irradiance data for the
   Pasadena area, used to derive modeled solar generation.
3. **Electricity tariff:** Southern California Edison (SCE), TOU-EV-4 tariff
   schedule, reconstructed for the simulation.
4. **Grid emissions:** US Environmental Protection Agency (EPA), eGRID2018,
   CAMX regional average emission factor.
   https://www.epa.gov/egrid/egrid2018-technical-support-document
5. **Base load:** A constant non-EV base load of 41.6667 kW, adopted as a
   simulation assumption.
