"""Deterministic 24-hour synthetic inputs for local optimizer testing."""

from LP_Optimizer import ChargingScenario, EVSession


def build_synthetic_scenario() -> ChargingScenario:
    """Return a feasible 24-hour scenario with overlapping EV sessions."""

    return ChargingScenario(
        prices=[
            0.12, 0.11, 0.10, 0.10, 0.11, 0.14,
            0.18, 0.22, 0.25, 0.24, 0.20, 0.16,
            0.13, 0.11, 0.10, 0.11, 0.15, 0.22,
            0.30, 0.32, 0.28, 0.22, 0.17, 0.14,
        ],
        base_load_kw=[
            1.8, 1.7, 1.6, 1.6, 1.7, 2.0,
            2.4, 2.8, 3.0, 3.1, 3.0, 2.8,
            2.6, 2.5, 2.4, 2.5, 2.8, 3.2,
            3.5, 3.4, 3.0, 2.7, 2.3, 2.0,
        ],
        solar_kw=[
            0.0, 0.0, 0.0, 0.0, 0.0, 0.1,
            0.4, 1.0, 1.8, 2.6, 3.2, 3.6,
            3.8, 3.5, 2.9, 2.1, 1.2, 0.5,
            0.1, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
        sessions=[
            EVSession("ev-1", arrival=0, departure=8, energy_kwh=5.4, max_power_kw=2.0),
            EVSession("ev-2", arrival=7, departure=18, energy_kwh=7.2, max_power_kw=2.0),
            EVSession("ev-3", arrival=16, departure=24, energy_kwh=3.6, max_power_kw=1.5),
        ],
    )


def build_synthetic_forecast() -> dict[str, list[float]]:
    """Return deliberately imperfect solar and base-load forecasts."""

    scenario = build_synthetic_scenario()
    return {
        "solar_kw": [
            value * 0.9 + (0.1 if index in (9, 10, 14) else 0.0)
            for index, value in enumerate(scenario.solar_kw)
        ],
        "base_load_kw": [
            value + (0.2 if index in (7, 8, 18, 19) else 0.0)
            for index, value in enumerate(scenario.base_load_kw)
        ],
    }
