# EV Smart Charging — Normalised Common Base

Updated integrated baseline built from 100 original ACN `California_Garage_01` session files, Open-Meteo ERA5 Pasadena irradiance, reconstructed SCE TOU-EV-4 2018 hourly energy rates, and eGRID2018 CAMX emissions factors.

## Files

| File | Purpose |
|---|---|
| `ev_sessions_normalized.csv` | One row per ACN session; timestamp proxies, duration, energy proxy, observed power, 7.2 kW assumed charger cap and data-quality flags |
| `acn_telemetry_normalized.csv.gz` | All 401,449 telemetry rows with UTC and Pasadena local timestamps |
| `solar_normalized.csv` | Hourly GHI/DNI/DHI with UTC and local timestamps |
| `tariff_normalized.csv` | Corrected hourly SCE tariff series and assumptions |
| `egrid2018_camx_emissions_factors.csv` | CAMX average and non-baseload CO2 factors |
| `common_hourly_baseline.csv` | Aligned solar/tariff inputs, constant base load, calculated PV output and emissions factor |
| `scenario_mapping.csv` | Maps each EV session to a local arrival-date scenario with a minimum 24-hour horizon extended when necessary |
| `validation_report.txt` | Data-quality checks, transformations and limitations |

## Adopted working assumptions

- PV: 100 kWp, performance ratio 0.80, simplified horizontal-GHI conversion: `PV_kW = min(100, 100 * max(GHI_Wm2, 0) / 1000 * 0.80)`. This is a scenario assumption, not measured plant output; test 75 and 125 kWp as sensitivity cases.
- EV charger limit: 7.2 kW per EV as a common Level-2 modelling assumption. Observed ACN power remains unchanged; sessions with observed maxima above 7.2 kW are flagged. This is not a verified ACN EVSE limit.
- ACN energy: use the maximum cumulative `Energy Delivered (kWh)` per session as the grid-side delivered-energy proxy; do not multiply by 0.9 again. This is a modelling interpretation, not a verified meter-location fact.
- Two sessions with missing energy but zero current and zero power throughout are assigned 0.0 kWh and flagged `zero_energy_no_charging_verified`; no cross-session interpolation is used.
- Grid emissions: 0.225209 kg CO2/kWh (eGRID2018 CAMX total output average) is the adopted working primary factor; 0.421614 kg CO2/kWh (non-baseload) is retained for sensitivity. This replaces the roadmap fallback of 0.4 and must be stated transparently.

## Limitations still requiring attention

1. First/last telemetry timestamps are arrival/departure proxies, not confirmed plug-in/unplug timestamps.
2. ACN energy is an observed outcome, not the driver's original requested energy.
3. The 7.2 kW limit is assumed, not sourced from ACN EVSE metadata.
4. ERA5 is reanalysis, and the PV formula is simplified; panel tilt, azimuth, temperature and detailed losses are not modelled.
5. Base load is assumed constant at 41.6667 kW, not measured. PV capacity is set to 100 kWp so the assumed system produces some surplus after serving this base load.
6. TOU-EV-9 time definitions are transferred approximately to the 2018 TOU-EV-4 price schedule; winter super-off-peak uses the off-peak price as a proxy.
7. The common hourly series has 1,121 rows; the final seven tariff hours have no matching solar record.
8. Two sessions fail the pre-UNPLUGGED energy monotonicity check; their maximum cumulative energy is retained as the session energy proxy and both are explicitly flagged. The anomalies do not justify fabricating or smoothing energy values.
9. ACN, solar, tariff and base-load inputs form a composite Pasadena-area simulation, not a single-site measured reconstruction.

Read `validation_report.txt` and
`../../EV_Assumptions_Implementation_Ready.md` before running the LP.


## Scenario boundary policy (implementation)

Each arrival-date scenario has a minimum 24-hour horizon starting at local midnight. If any session arriving on that date departs after midnight, the scenario horizon is extended to the next whole-hour boundary after the latest such departure. All strategies must use exactly the same extended horizon. Sessions are never clipped; charging is permitted only between the observed arrival/departure proxies.
