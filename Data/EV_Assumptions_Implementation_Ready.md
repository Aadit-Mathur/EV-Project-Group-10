# EV Smart Charging Project --- Assumptions Register

**Project:** EV Smart Charging --- Group 10\
**Purpose:** Single reference for dataset choices, preprocessing
conventions, modelling assumptions and unresolved decisions.\
**Status:** Working register --- established decisions are distinguished
from provisional assumptions and open items.

> **Authority:** The finalized *EV Smart Charging --- Four-Person
> Technical Roadmap*, especially Section 13 (Finalized Decision Record),
> is the governing specification for the optimization model and shared
> modelling conventions. This file records the project-specific dataset
> choices made subsequently. If a dataset limitation requires changing a
> roadmap decision, document the reason and apply the change
> consistently across all strategies.

------------------------------------------------------------------------

## Implementation-ready parameter lock (supersedes earlier provisional wording)

The following values are the single source of truth for implementation:

- LP only; continuous decision variables; hourly time step.
- PV capacity = **100 kWp**; performance ratio = **0.80**; hourly PV output = `min(100, 100 * max(GHI,0)/1000 * 0.80)` kW. This intentionally replaces the earlier 100 kWp trial because 100 kWp never produced surplus above the assumed base load; 100 kWp yields meaningful surplus hours for testing solar-aware charging. Sensitivity: 75 and 125 kWp.
- Non-EV base load = **41.6667 kW constant**. Retained for reproducibility; clearly labelled modelling assumption, not measured building demand.
- Solar serves base load first; only `max(PV - base_load, 0)` is available to EVs; no export; unused surplus is curtailed.
- EV charger cap = **7.2 kW per EV** for every strategy. Do not clip or rewrite measured ACN telemetry. Flag observations above the modelling cap.
- EV energy target = maximum cumulative ACN delivered-energy value per session, interpreted as a grid-side energy proxy. Do not apply 0.9 efficiency again. The target is observed delivered energy, not original requested energy.
- Sessions are grouped by local arrival date. Each scenario begins at local midnight and has a minimum 24-hour horizon; extend the horizon to the next whole-hour boundary after the latest departure of any session arriving on that date. This replaces strict fixed-24-hour truncation. All strategies use identical scenario windows; never truncate sessions.
- Arrival/departure remain first/last telemetry timestamp proxies. Use arrival-inclusive and departure-exclusive availability. The last slot is only available if its start is earlier than departure.
- Two non-monotonic telemetry sessions retain their maximum cumulative energy target and are flagged; do not interpolate or smooth cumulative energy. Report these flags in results.
- Grid CO₂ primary = **0.225209 kg/kWh**, eGRID2018 CAMX average output. Sensitivity = 0.421614 kg/kWh non-baseload.
- Missing energy in the two verified no-current/no-power sessions = 0.0 kWh, with `zero_energy_no_charging_verified` provenance. No cross-session interpolation.

These locked values supersede contradictory earlier provisional statements in this register. If code comments or older sections differ, follow this section and the matching normalized CSV columns.

------------------------------------------------------------------------

## 1. Project scope

The project compares three charging strategies:

1.  Uncontrolled charging.
2.  Time-of-Use (TOU) charging.
3.  LP-based smart charging.

Forecast-based LP and perfect-foresight LP are two information modes of
the **same LP scheduler**, not a fourth charging strategy.

The optimization formulation is **continuous Linear Programming (LP),
not MILP**. Binary variables and MILP are outside the agreed scope
unless the project scope is deliberately changed.

All strategies must be evaluated using the same EV sessions, scenario
windows, time-slot length, charger limits, energy requirements, tariff
and relevant environmental inputs.

------------------------------------------------------------------------

## 2. Selected datasets and provenance

  ---------------------------------------------------------------------------------
  Input             Selected source / choice  Current treatment   Status
  ----------------- ------------------------- ------------------- -----------------
  EV charging       Original ACN-Data         Use observed        Selected; field
                    sessions from             session records as  semantics and
                    `California_Garage_01`;   the primary EV      limits require
                    approximately 100         behaviour input     validation
                    selected sessions                             

  Alternate generated EV data `SYNTHETIC_EV_DATA.csv`   Not the primary EV  Excluded from
                    (CTGAN + KDE generated)   input; retain only  primary
                                              for a possible      experiment
                                              separate            
                                              scale/sensitivity   
                                              experiment          

  Solar             Open-Meteo historical     Use hourly          Selected; PV
                    ERA5 for Pasadena         GHI/DNI/DHI as      conversion
                                              weather-derived     assumptions open
                                              solar-resource      
                                              inputs; convert to  
                                              PV output before LP 
                                              use                 

  Non-EV base load  Explicit constant-load    30,000 kWh per      Selected
                    scenario assumption       30-day month,       assumption; not
                                              equivalent to 41.67 measured data
                                              kW continuously     

  Electricity       Southern California       Construct hourly    Selected; period
  tariff            Edison (SCE) TOU-EV-4     energy-price series mapping is
                    2018 rate sheets          using documented    approximate
                                              time-period         
                                              assumptions         

  Grid emissions    eGRID2018 CAMX average   0.225209 kg CO₂/kWh Primary adopted;
                    output factor              primary; non-baseload 0.421614 sensitivity 
                                              sourced replacement 
  ---------------------------------------------------------------------------------

### 2.1 Geographic and temporal compatibility

-   The solar resource data is for the Pasadena area. The requested
    coordinates were approximately 34.14° N, 118.12° W; the returned
    ERA5 grid point was approximately **34.25° N, 118.00° W**.
-   The EV sessions are from the Caltech-area ACN dataset, and the
    tariff is an SCE tariff. These inputs are geographically related to
    the Pasadena scenario but are not measurements from one identical
    physical installation.
-   The non-EV base load is an assumed constant profile, not a measured
    load series from the ACN garage.
-   Therefore, describe the integrated experiment as a **composite
    Pasadena-area simulation**, not as a reconstruction of one
    facility's measured historical operation.
-   Preserve this limitation in the methodology and results. Do not
    imply that the base load or PV output was measured at the ACN
    charging site.

------------------------------------------------------------------------

## 3. EV charging data assumptions

### 3.1 Primary dataset

-   Use the original ACN-Data `California_Garage_01` records as the
    primary EV-session input.
-   Approximately 100 sessions were selected for the project.
-   Preserve original session identifiers and raw records.
-   Do not substitute the excluded alternate generated EV dataset in the primary
    experiment without an explicit project decision.

### 3.2 Session-field interpretation

  -----------------------------------------------------------------------
  Required model field    Current interpretation  Validation required
                          / rule                  
  ----------------------- ----------------------- -----------------------
  EV/session ID           Preserve the original   Confirm unique
                          ACN session identifier  identifier column

  Arrival                 First recorded charging Confirm whether the
                          timestamp is the        source provides a
                          current proxy for       distinct connection
                          connection/arrival      timestamp

  Departure               Final recorded          Confirm whether the
                          timestamp or inferred   source provides a
                          disconnect is the       distinct disconnect
                          current proxy           timestamp and whether
                                                  the final record is
                                                  inclusive

  Required energy         Recorded energy         This is not necessarily
                          delivered is used as a  the driver's originally
                          proxy for the session   requested energy
                          energy requirement      

  Maximum charging power  Must come from          Do not invent an
                          charger/station         individual limit
                          metadata or a           
                          documented common limit 

  Charging efficiency     Apply only if the       Establish whether ACN
                          target energy is        energy is grid-side or
                          battery-side            battery-side
  -----------------------------------------------------------------------

**Important limitation:** final recorded energy delivered is an observed
outcome, not necessarily the driver's original requested battery energy.
Treating it as the required energy is a modelling proxy and must be
disclosed.

### 3.3 EV availability and feasibility

-   Charging is permitted only within the session's availability window.
-   Use a consistent arrival-inclusive, departure-exclusive slot
    convention unless source inspection requires another convention;
    document any change.
-   Charging power must be zero outside the availability window.
-   During an available slot, charging power must not exceed the
    applicable (P\_{`\max`{=tex},i}).
-   If the energy target cannot be delivered before departure under the
    power and efficiency limits, mark the session infeasible and report
    its shortfall.
-   Do not silently relax energy requirements or claim an infeasible
    session was completed.
-   Sessions crossing midnight must be represented across the
    appropriate consecutive time slots; do not truncate them without
    recording the exclusion.
- Scenario horizons start at local midnight and are at least 24 hours. If a session arriving on that date departs after midnight, extend that date's horizon to the next whole-hour boundary after the latest departure. Use the same extended horizon for all strategies; never truncate a session.

------------------------------------------------------------------------

## 4. Solar-resource and PV assumptions

### 4.1 Source data

-   Source: Open-Meteo historical ERA5.
-   Requested location: Pasadena, California.
-   Returned grid point: approximately 34.25° N, 118.00° W.
-   Period: **1 May--16 June 2018**, inclusive.
-   Expected source series: 1,128 hourly records.
-   Source time basis: UTC/GMT; convert timestamps to
    `America/Los_Angeles` for scenario alignment.
-   Available variables:
    -   GHI (`shortwave_radiation`) in W/m².
    -   DNI (`direct_normal_irradiance`) in W/m².
    -   DHI (`diffuse_radiation`) in W/m².

### 4.2 Interpretation and conversion

-   ERA5 is historical reanalysis, not direct measurement from the
    charging station.
-   Irradiance in W/m² is not electrical PV output in kW. Do not pass
    GHI/DNI/DHI directly to the LP as solar power.
-   Convert the solar-resource series into hourly PV electrical output
    using a documented PV model or a clearly labelled simplified
    conversion.
- Adopted implementation assumption: 100 kWp rated capacity and performance ratio 0.80. Use the simplified horizontal-GHI conversion: PV_kW = min(100, 100 × max(GHI_Wm2, 0) / 1000 × 0.80). This is a scenario assumption, not measured plant output; test 75 and 125 kWp as sensitivity cases.
-   Record the PV assumptions and units alongside the processed output.
-   Apply the same resulting solar-generation series to all charging
    strategies for a given scenario.

------------------------------------------------------------------------

## 5. Non-EV base-load assumption

The project currently uses a constant non-EV load instead of a measured
building-load profile.

\[ E\_{`\text{month}`{=tex}} = 30{,}000 `\text{kWh}`{=tex} \]

Using a 30-day month:

\[ P\_{`\text{base}`{=tex}} = `\frac{30{,}000}{30 \times 24}`{=tex} =
41.6667 `\text{kW}`{=tex} \]

**Chosen profile:**
(P\_{`\text{base}`{=tex},t}=41.6667 `\text{kW}`{=tex}) for every hourly
slot.

Assumptions and limitations:

-   The load is constant throughout the day, week and season.
-   This is a scenario assumption, not a measured ACN garage load and
    not a verified universal EPA garage benchmark.
-   No hourly, weekday/weekend or seasonal variation is represented.
-   The previously explored ComStock medium-office profile is not
    selected.
-   The earlier Marengo building-area estimate is not part of this
    assumption.
-   Since no historical base-load time series is being used, base load
    is treated as known in both forecast-based and perfect-foresight
    runs; it is not an ML forecast target.

------------------------------------------------------------------------

## 6. Electricity tariff assumptions

### 6.1 Source and scope

-   Tariff source: SCE TOU-EV-4 2018 rate sheets.
-   May 2018 is treated as winter; June 2018 is treated as summer.
-   The model uses an hourly energy-price series in currency/kWh.
-   Monthly customer charges and demand-related charges are not included
    in the hourly energy-price series. If a complete bill is later
    required, model these separately and state the applicable billing
    assumptions.
-   Confirm tariff eligibility before describing the schedule as the
    actual tariff applicable to a real facility. The rate schedule has
    separate-meter and demand-range eligibility conditions.

### 6.2 Time-period mapping

The time-period definitions selected for the simulation were taken from
a later TOU-EV-9 schedule and assumed to apply to the 2018 TOU-EV-4 rate
series. This transfer has **not been verified** against the 2018
TOU-EV-4 schedule and must be described as an approximation.

  Season / day                Local time            Model period
  --------------------------- --------------------- ----------------
  Summer weekday              4:00 PM--9:00 PM      On-peak
  Summer weekend or holiday   4:00 PM--9:00 PM      Mid-peak
  Summer, all other hours     All remaining hours   Off-peak
  Winter                      8:00 AM--4:00 PM      Super-off-peak
  Winter                      4:00 PM--9:00 PM      Mid-peak
  Winter                      9:00 PM--8:00 AM      Off-peak

Season boundaries used:

-   Summer: 1 June 00:00 through 1 October 00:00.
-   Winter: 1 October 00:00 through 1 June 00:00.

Holiday list used:

-   New Year's Day.
-   Presidents' Day (third Monday in February).
-   Memorial Day (last Monday in May).
-   Independence Day (4 July).
-   Labor Day (first Monday in September).
-   Veterans Day.
-   Thanksgiving (fourth Thursday in November).
-   Christmas Day.

If a holiday falls on Sunday, the following Monday is observed. Saturday
holidays are not shifted. Within the selected 1 May--16 June 2018
period, Memorial Day (28 May 2018) is the relevant listed holiday.

### 6.3 Corrected bundled energy rates

The following rates include both the delivery and generation components
for the relevant 2018 rate sheets. They replace the earlier May values
that omitted the delivery component.

  -----------------------------------------------------------------------
  Model period                  May 2018 winter          June 2018 summer
  ------------------- ------------------------- -------------------------
  On-peak                         \$0.09211/kWh             \$0.28298/kWh

  Mid-peak                        \$0.07732/kWh             \$0.09667/kWh

  Off-peak                        \$0.06010/kWh             \$0.05615/kWh

  Super-off-peak                \$0.06010/kWh\*  Not used in the selected
                                                           summer mapping
  -----------------------------------------------------------------------

\*The 2018 TOU-EV-4 rate sheet does not establish a distinct winter
super-off-peak price. The winter off-peak price is used as a proxy for
the later schedule's super-off-peak time window. Label this
approximation in the tariff-generation script and report.

Tariff implementation rules:

-   Assign prices using local Pasadena time, not UTC clock time.
-   Apply the weekend/holiday distinction only as specified in the
    chosen period mapping.
-   Keep tariff prices known in both forecast-based and
    perfect-foresight modes; do not forecast a published tariff assumed
    to be known in advance.
-   Ensure each tariff timestamp maps to exactly one common scenario
    slot.
-   The prior tariff CSV that used May generation-only rates is
    superseded and must not be used.

------------------------------------------------------------------------

## 7. Grid-emissions assumption

The roadmap fallback was 0.4 kg CO₂/kWh. For implementation, replace it with the location-matched eGRID2018 CAMX total-output average factor: **0.225209 kg CO₂/kWh** (496.5 lb/MWh converted to kg/kWh). This is the primary factor throughout the dataset and all strategies. Retain **0.421614 kg CO₂/kWh** (CAMX non-baseload) as a sensitivity case only. The primary factor is an average-output factor, not a marginal-emissions factor. This is an explicit documented project choice replacing the roadmap fallback.

Additional conventions:

-   CO₂ is an evaluation metric, not a term in the finalized LP
    objective.
-   Calculate emissions from grid energy imported multiplied by the
    selected factor.
-   A regional average output factor is not a marginal emissions factor;
    do not describe it as marginal avoided emissions.
-   State whether transmission and distribution losses are included if
    the factor source makes that distinction relevant.

------------------------------------------------------------------------

## 8. Common time base and scenario construction

-   Initial common interval: (`\Delta `{=tex}t=1) hour.
-   Initial scenario horizon: 24 hours.
-   Common timezone for Pasadena-area alignment: `America/Los_Angeles`.
-   Convert UTC source timestamps using the timezone database; do not
    apply a fixed UTC offset because daylight-saving time changes the
    offset.
-   Use the same interval boundaries for EV availability, PV generation,
    base load and tariff.
-   Document timestamp semantics (interval start/end) and slot-boundary
    treatment.
-   If 1-hour resampling erases essential ACN session detail or makes
    too many sessions infeasible, test a finer common interval. Any
    change must apply to every strategy and both LP information modes.
-   Use only scenarios with a clearly defined common time window and
    aligned environmental inputs.
-   Do not combine unrelated dates into a single 24-hour scenario.
-   If a session or scenario extends beyond the available environmental
    data, record the chosen exclusion or boundary treatment.
-   Keep raw files unchanged. Save cleaned, transformed and aligned
    files under `Data/processed/`.
-   For every processed dataset, record source, original filename,
    units, timezone, transformations, missing-data treatment and
    exclusions.

------------------------------------------------------------------------

## 9. Charging-strategy and LP conventions

### 9.1 Shared physical constraints

-   EV charging power is continuous and nonnegative.
-   Charging power is zero outside each EV's availability window.
-   Charging power does not exceed the EV/charger maximum power.
-   Deliver 100% of each included EV's required energy whenever
    physically feasible.
-   If a session is infeasible, report it and its energy shortfall; do
    not silently relax the target.
-   Apply charging efficiency exactly once.
-   Power is measured in kW; energy in kWh; tariff in currency/kWh;
    emissions in kg CO₂.
-   Energy delivered during a slot is power multiplied by slot duration,
    with efficiency applied according to the energy convention.

### 9.2 Efficiency and energy convention

The roadmap specifies (`\eta=0.9`{=tex}) where the required energy is
battery-side energy.

For battery-side target (E_i):

\[ `\sum`{=tex}*t P*{i,t}`\Delta `{=tex}t,`\eta`{=tex}\_i = E_i \]

For grid-side energy target (E_i):

\[ `\sum`{=tex}*t P*{i,t}`\Delta `{=tex}t = E_i \]

Do not apply efficiency twice. The ACN energy-field convention must be
verified before choosing which equation applies to the observed data.

### 9.3 Solar and grid treatment

-   Solar serves non-EV base load first.
-   Only solar surplus after base load can be credited to EV charging.
-   Grid import is nonnegative.
-   Grid export is out of scope.
-   Surplus solar not used by the site is curtailed.
-   Peak load means maximum grid import after the solar offset, not
    gross site demand.

The LP uses:

\[ P\_{`\text{grid}`{=tex},t}`\geq`{=tex}
P\_{`\text{base}`{=tex},t}+P\_{`\text{EV}`{=tex},t}-P\_{`\text{solar}`{=tex},t}
\]

\[ P\_{`\text{grid}`{=tex},t}`\geq 0`{=tex} \]

Solar surplus is precomputed from known inputs:

\[ P\_{`\text{solar-surplus}`{=tex},t}
=`\max`{=tex}(0,P\_{`\text{solar}`{=tex},t}-P\_{`\text{base}`{=tex},t})
\]

Solar allocated to EV charging (u_t) satisfies:

\[ 0`\leq `{=tex}u_t`\leq `{=tex}P\_{`\text{EV}`{=tex},t},
`\qquad`{=tex} u_t`\leq `{=tex}P\_{`\text{solar-surplus}`{=tex},t} \]

### 9.4 Finalized LP objective

Minimize:

\[ J = `\frac{C_{\text{EV}}}{C_{\text{ref}}}`{=tex}
+5`\frac{P_{\text{peak}}}{P_{\text{ref}}}`{=tex}
-2`\frac{S_{\text{EV,solar}}}{E_{\text{EV,grid}}}`{=tex} \]

Primary normalized weights:

\[ w_C:w_P:w_R=1:5:2 \]

We selected 1:5:2 to prioritize peak-demand reduction while still accounting
for charging cost and renewable-solar utilization. Charging cost, peak demand
and solar use have different physical units, so cost is divided by
`C_ref`, peak by `P_ref`, and solar use by `E_EV_grid` before the weights are
applied. These weights represent our chosen priorities and are not empirically
estimated constants. The optional 1:1:1 equal-weight result is a sensitivity
check only; it does not replace or amend the primary 1:5:2 model.

Definitions:

\[ S\_{`\text{EV,solar}`{=tex}}=`\sum`{=tex}\_t u_t`\Delta `{=tex}t \]

For battery-side requirements:

\[ E\_{`\text{EV,grid}`{=tex}}=`\sum`{=tex}\_i`\frac{E_i}{\eta_i}`{=tex}
\]

\[ C\_{`\text{EV}`{=tex}}= `\sum`{=tex}*t `\pi`{=tex}*t
`\left`{=tex}(P*{`\text{grid}`{=tex},t}-P*{`\text{grid,base-only}`{=tex},t}`\right`{=tex})`\Delta `{=tex}t
\]

\[ P\_{`\text{grid,base-only}`{=tex},t}
=`\max`{=tex}(0,P\_{`\text{base}`{=tex},t}-P\_{`\text{solar}`{=tex},t})
\]

\[
C\_{`\text{ref}`{=tex}}=`\operatorname{mean}`{=tex}(`\pi`{=tex}*t),E*{`\text{EV,grid}`{=tex}}
\]

\[ P\_{`\text{ref}`{=tex}}=
`\max`{=tex}*t`\left`{=tex}(P*{`\text{base}`{=tex},t}+ `\sum`{=tex}*i
a*{i,t}P\_{i,`\max`{=tex}}`\right`{=tex}) \]

where (a\_{i,t}=1) when EV (i) is available in slot (t), and 0
otherwise.

Do not alter the objective, normalization or primary weights
independently. An optional equal-weight sensitivity check (1:1:1) may be
reported separately; the primary results remain based on 1:5:2.

### 9.5 Strategy-specific rules

-   **Uncontrolled:** charge as soon as the EV arrives, at maximum
    allowed power, until its energy requirement is met or its charging
    window ends. It must not look ahead to future prices or solar.
-   **TOU:** preferentially allocate charging to lower-price available
    slots, respecting availability, charger power and energy
    requirements. Use deterministic tie-breaking (for example, earlier
    slot first). Do not add the LP's peak or solar objective to this
    strategy.
-   **LP smart charging:** solve the continuous LP with the finalized
    objective and constraints.
-   Use one shared evaluator to calculate metrics from each schedule and
    the same scenario inputs. Do not let each strategy calculate
    headline metrics using different definitions.

------------------------------------------------------------------------

## 10. Forecasting and perfect-foresight assumptions

-   Mandatory ML forecast target: solar generation.
-   Forecast base load only if a suitable historical time series exists.
    With the current constant assumed base load, treat it as known in
    both modes.
-   Published TOU tariffs are known inputs and are not forecast.
-   EV arrival, departure and required energy are treated as known
    inputs in both modes. This deliberately isolates uncertainty in
    solar and, where applicable, base load.
-   Forecast horizon: 24 hours, matching the LP scenario horizon.
-   Chronological data split: 70% training, 15% validation and 15%
    held-out testing. Do not shuffle time-series observations.
-   Compare a persistence/same-hour historical baseline with one
    scikit-learn model, preferably `RandomForestRegressor`.
-   Use only features available at prediction time (for example,
    hour-of-day, day-of-week and available past-value lags).
-   Report MAE and RMSE for each forecast target and inspect
    actual-versus-predicted plots.
-   Forecast-based LP uses predicted future values for the forecast
    targets.
-   Perfect-foresight LP uses actual future values for those same
    uncertain inputs.
-   Both modes must reuse the same LP function, objective, constraints,
    EV sessions, tariff, test windows and solver settings.
-   Evaluate both schedules against the actual test-period environment.
-   Perfect foresight is an ideal-information benchmark, not a practical
    deployable forecast.

------------------------------------------------------------------------

## 11. Out-of-scope items

Unless the project scope is explicitly changed, the following are out of
scope:

-   Mixed Integer Linear Programming (MILP) and binary decision
    variables.
-   Grid export.
-   Vehicle-to-grid (V2G).
-   Battery degradation and battery-health modelling.
-   Reinforcement learning.
-   Physical charger control or hardware integration.
-   A frontend, database or cloud deployment requirement.

------------------------------------------------------------------------

## 12. Open items --- do not let individual implementations guess

The following must be verified or explicitly approved before final
experiments.

  --------------------------------------------------------------------------
  ID                      Open item               Required resolution
  ----------------------- ----------------------- --------------------------
  O-01                    ACN energy semantics    Confirm whether the
                                                  selected energy field is
                                                  grid-side or battery-side;
                                                  select the efficiency
                                                  equation accordingly

  O-02                    ACN arrival/departure   Confirm the exact
                          semantics               connection/disconnection
                                                  fields and interval
                                                  boundary meaning

  O-03                    Charger maximum power   Obtain station/charger
                                                  metadata or approve a
                                                  documented common
                                                  (P\_{`\max`{=tex}})

  O-04                    PV system               Resolved: 100 kWp, PR 0.80,
                                                  simplified horizontal-GHI model

  O-05                    Emissions factor        Resolved: 0.225209 kg CO₂/kWh
                                                  primary; 0.421614 sensitivity

  O-06                    Tariff period mapping   Verify later TOU-EV-9
                                                  periods against 2018
                                                  TOU-EV-4, or retain and
                                                  label the approximation

  O-07                    Winter super-off-peak   Retain winter off-peak
                          rate                    price as a proxy or obtain
                                                  an authoritative
                                                  applicable rate

  O-08                    Demand charges          Decide whether the
                                                  coursework reports
                                                  energy-only cost or a
                                                  separate
                                                  demand-charge/bill
                                                  estimate

  O-09                    Time resolution         Validate that hourly slots
                                                  preserve sufficient
                                                  session detail and do not
                                                  create excessive
                                                  infeasibility

  O-10                    Scenario boundary       Define handling for
                          policy                  sessions crossing midnight
                                                  or the 24-hour horizon

  O-11                    Sample selection        Record the exact ACN
                                                  session IDs and
                                                  deterministic selection
                                                  method for reproducibility

  O-12                    Base-load realism       Retain constant 41.67 kW
                                                  and disclose limitation,
                                                  or replace only with a
                                                  documented compatible
                                                  measured/profile dataset
  --------------------------------------------------------------------------

No missing measurement should be fabricated. If a data source lacks an
input, use a clearly labelled scenario assumption or simplify the
experiment and state the limitation.

------------------------------------------------------------------------

## 13. Required validation before LP integration

The preprocessing pipeline should produce a validation report covering:

1.  Source row counts and selected row counts.
2.  Missing values, duplicate records and invalid values.
3.  Timestamp parsing, timezone conversion and daylight-saving handling.
4.  Coverage start/end and gaps for every time series.
5.  Unit consistency and conversions.
6.  EV session arrival/departure ordering and duration.
7.  Implied EV charging power and comparison with the approved
    (P\_{`\max`{=tex}}).
8.  Session energy feasibility under availability, power and efficiency
    limits.
9.  Sessions crossing midnight or scenario boundaries.
10. Exactly one tariff and environmental input per required time slot.
11. Nonnegative PV output, base load and grid import.
12. Reconciliation of hourly energy with power multiplied by
    (`\Delta `{=tex}t).
13. Identical scenario inputs supplied to all strategies.
14. Reproducibility of sample selection and preprocessing.

Raw datasets must remain unchanged. Save aligned outputs under
`Data/processed/`, and save the preprocessing script, configuration,
data dictionary and validation report with the project.

------------------------------------------------------------------------

## 14. Change-control rule

Any change to an established assumption must be recorded with:

-   The original assumption.
-   The replacement assumption.
-   Why the change was necessary (for example, a source-data
    limitation).
-   Which datasets, scenarios, strategies and metrics are affected.
-   Confirmation that the change was applied consistently.
-   The date and person responsible for the change.

**No teammate should independently change the common time step, energy
convention, charger limits, tariff mapping, emissions factor, LP
objective or objective weights inside their own strategy
implementation.**


------------------------------------------------------------------------

## 13. Adopted working assumptions — update 18 November 2026

This section supersedes earlier statements in this register that described PV conversion, charger power, ACN energy convention and the primary emissions factor as unresolved or merely candidate values. These are adopted working assumptions for implementation; limitations remain explicit.

### 13.1 Representative EV charger limit

- Use **7.2 kW per EV** as the common maximum charging power in the primary simulation (representative 240 V, 30 A Level-2 charger).
- Apply the same limit to uncontrolled, TOU and LP schedules.
- Preserve observed ACN telemetry power. Do not clip or rewrite the source observations. Flag any session whose observed maximum exceeds 7.2 kW; this indicates the assumption may not fit every observed session.
- This is a representative charger assumption, not verified ACN EVSE metadata. Run 7.5 kW as a sensitivity case if useful.

### 13.2 ACN session energy convention

- For each session, use the **maximum** value of cumulative `Energy Delivered (kWh)` as the observed delivered-energy proxy; the field resets to zero at `UNPLUGGED`.
- Adopt this value as a **grid-side energy target proxy** for the primary model. Therefore use `\sum_t P_{i,t}\Delta t = E_i` and do **not** multiply by the roadmap's 0.9 efficiency a second time.
- This is an explicit modelling interpretation. The field documentation does not conclusively establish the physical meter location, and observed delivered energy is not necessarily the driver's originally requested energy.
- Two sessions have missing energy but zero current and zero power throughout. Assign 0.0 kWh and flag them `zero_energy_no_charging_verified`; do not interpolate across sessions. Missing values during observed charging must be flagged for review, not fabricated.

### 13.3 PV system scenario

- Adopt **100 kWp** installed PV capacity and **0.80** performance ratio for the primary scenario.
-   Use the simplified horizontal-GHI conversion:

  `PV_kW_t = min(100, 100 * max(GHI_Wm2_t, 0) / 1000 * 0.80)`

- GHI is in W/m² and PV output is in kW. This approximation does not explicitly model panel tilt, azimuth, temperature or detailed system losses. It is a scenario estimate, not measured PV generation.
-   Use 75 kWp and 125 kWp as optional PV-capacity sensitivity cases. Use the same PV series for every charging strategy in a given scenario.

### 13.4 Primary grid-emissions factor

- Adopt **0.225209 kg CO2/kWh** as the working primary factor: eGRID2018 CAMX total output average, 496.5 lb/MWh converted to kg/kWh.
- Retain **0.421614 kg CO2/kWh** (CAMX non-baseload) as a sensitivity factor, not the primary value.
- This formally replaces the roadmap's 0.4 kg CO2/kWh fallback because a region- and year-specific eGRID factor is available. Identify it as an average output factor, not a marginal factor. No gross-loss adjustment is applied.

### 13.5 Common data package

The updated `EV_Common_Base_Normalized.zip` reflects these working assumptions. In particular, `ev_sessions_normalized.csv` now contains the 7.2 kW assumed cap, above-cap observation flag and energy-imputation method; `common_hourly_baseline.csv` now contains calculated PV output and the adopted emissions factor. The validation report records remaining limitations.


------------------------------------------------------------------------

## 13. Implementation readiness and data-quality disposition

The normalized package has been updated to match the locked assumptions above. `common_hourly_baseline.csv` now includes PV output, solar-to-base allocation, and solar surplus available to EVs. `scenario_mapping.csv` now records extended per-date horizons and verifies arrival/departure containment. `ev_sessions_normalized.csv` contains the common 7.2 kW cap and explicit energy-quality flags.

The two non-monotonic cumulative-energy sessions are retained rather than silently corrected: the session target is the maximum observed cumulative value, which avoids using a potentially reset/decreasing final reading. They remain flagged for transparent reporting. Three sessions have observed maximum power above 7.2 kW; raw observations remain untouched and the LP cap remains 7.2 kW as a deliberate common comparison limit.

The 100 kWp PV choice is a scenario-design assumption selected to create nonzero PV surplus under the retained constant 41.6667 kW base load. It is not claimed to represent a measured site. The project is a composite simulation; all three strategies must use identical base load, PV, tariff, emissions, sessions, availability windows, and scenario horizons.

### Final implementation checklist

- [x] PV electrical output calculated and solar surplus available to EVs exposed as a column.
- [x] PV/base-load mismatch resolved by adopting 100 kWp scenario capacity.
- [x] Sessions crossing midnight retained through variable-length scenario horizons.
- [x] Non-monotonic telemetry retained with explicit quality flags and robust max-cumulative energy target.
- [x] 7.2 kW common LP cap recorded without altering raw observations.
- [x] Emissions factor contradiction resolved: 0.225209 primary; 0.421614 sensitivity.
- [x] Same scenario windows and assumptions mandated across all strategies.

**Status: ready for LP implementation.** Remaining limitations are documented modelling assumptions, not blockers: ACN timestamps are proxies, the ACN energy target is a delivered-energy proxy, PV uses a simplified GHI conversion, the base load is constant, and tariff period mapping is approximate.
