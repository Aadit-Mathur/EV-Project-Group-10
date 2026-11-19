# Normalized Experiment Results

## What was tested

The experiment compared uncontrolled charging, Time-of-Use (TOU) charging,
and LP smart charging across 45 normalized arrival-date scenarios containing
100 EV sessions. The forecast-based LP and perfect-foresight LP runs use the
same physical model and are compared using the same test-period inputs.

## Weighting decision

The primary LP gives relative weights of 1:5:2 to normalized charging cost,
peak grid demand, and solar use. The weights were selected so peak-demand
reduction is prioritized, with charging cost and renewable utilization still
included. Because cost, peak demand, and solar use are measured in different
units, the model normalizes each objective before applying the weights.

These weights represent our chosen project priorities, not coefficients learned
from the data. A 1:1:1 equal-weight result is also included as a sensitivity
check and is not a replacement for the primary 1:5:2 result.

## Easy-to-understand outcome

Across all 45 scenarios, LP smart charging had lower mean charging cost and
used substantially more solar energy than uncontrolled or TOU charging.
Uncontrolled charging charged as soon as EVs arrived, while TOU charging moved
charging to cheaper tariff periods. Neither baseline optimized both cost and
solar use together. The LP scheduler could consider all normalized objectives
at the same time.

In the six held-out forecast scenarios, forecast-based LP was close to
perfect-foresight LP. Its mean charging cost was $0.013207 higher and its peak
was 0.174117 kW higher, while solar use was equal. Forecast error therefore
had a small measurable effect in these cases, but perfect foresight is an
ideal-information benchmark and should not be presented as a deployable
forecast method.

## Important limitation

The data are a composite Pasadena-area normalized scenario rather than one
complete measured facility record. Base load and PV output are modeled,
timestamps and ACN energy are proxies, and tariff mapping is approximate.
The figures demonstrate comparative behavior under these assumptions, not
guaranteed real-world savings.
