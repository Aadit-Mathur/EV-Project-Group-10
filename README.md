# EV Smart Charging

This repository implements uncontrolled charging, Time-of-Use (TOU) charging,
and continuous LP-based smart charging. Forecast-based LP and perfect-foresight
LP reuse the same optimizer and are evaluated against the actual environment.

## Current implementation

- `LP_Optimizer/`: finalized continuous LP scheduler.
- `Helpers/`: shared contracts, data ingestion, forecasting, and schedule
  validation/metrics.
- `Uncontrolled/`: immediate-charging baseline.
- `TOU/`: deterministic Time-of-Use scheduler.
- `LP_Optimizer/`: continuous LP optimizer and its shared-contract adapter.
- `Experiments/`: reproducible experiment runner and normalized-data entry point.
Install dependencies with `pip install -r requirements.txt`, then run:

```text
python -m pytest -q
python -m Experiments.run_real
```

The production workflow preserves raw files, documents units/time zones and
geography, aligns timestamps consistently, and uses the normalized package
under `Data/normalised/ev_common_base/`. The roadmap's primary LP objective
remains the normalized 1:5:2 objective; the optional equal-weight run is
sensitivity only.

The primary LP uses a 1:5:2 weight ratio for normalized charging cost, peak
grid demand, and renewable-solar use. The objectives have different physical
units, so each is divided by a reference scale before weighting. The weights
reflect our chosen priority of peak-demand reduction; they are project choices,
not empirically estimated constants. The 1:1:1 equal-weight run is reported
only as a sensitivity check.

## Normalized real-data run

The current common base contains 100 ACN sessions, Open-Meteo ERA5 Pasadena
solar data, a constant 41.6667 kW base-load scenario, historical SCE TOU-EV-4
energy rates, and EPA eGRID2018 CAMX factors. Run the full backend experiment
with:

```text
python -m Experiments.run_real
```

Outputs are written to `Results/real_data/`, including per-scenario schedules,
strategy metrics, forecast predictions/plots, and an aggregate summary. Read
`Data/EV_Assumptions_Implementation_Ready.md` and the normalized package
`validation_report.txt` before changing any locked assumptions. The data is a
composite Pasadena-area simulation; ACN timestamp/energy fields, PV output,
constant base load, and tariff period mapping are documented proxies or
assumptions rather than one measured facility's complete record.

## Submission report

See `PROJECT_REPORT.md` for the methodology, implemented requirements, data
limitations, test evidence, and key results suitable for coursework
submission. The report links the source assumptions and generated artifacts
back to the reproducible commands above.
