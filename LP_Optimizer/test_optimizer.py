import numpy as np
import pytest

from LP_Optimizer.optimizer import ChargingScenario, EVSession, LPConfig, run_lp


def test_lp_meets_energy_and_respects_availability():
    scenario = ChargingScenario(
        prices=[1, 1, 1],
        base_load_kw=[2, 2, 2],
        solar_kw=[0, 0, 0],
        sessions=[EVSession("ev-1", arrival=1, departure=3, energy_kwh=1.8, max_power_kw=1)],
    )

    result = run_lp(scenario)

    assert result.status == "Optimal"
    schedule = result.schedule
    assert schedule.loc[schedule.slot == 0, "charging_power_kw"].iloc[0] == pytest.approx(0)
    assert schedule.charging_power_kw.max() <= 1 + 1e-8
    assert result.metrics["ev_grid_energy_kwh"] == pytest.approx(2)
    assert schedule.charging_power_kw.sum() * 0.9 == pytest.approx(1.8)


def test_lp_uses_surplus_solar_and_prefers_lower_cost_when_peak_is_tied():
    scenario = ChargingScenario(
        prices=[10, 1, 10],
        base_load_kw=[1, 1, 1],
        solar_kw=[0, 3, 0],
        sessions=[EVSession("ev-1", arrival=0, departure=3, energy_kwh=1.8, max_power_kw=1)],
    )

    result = run_lp(scenario)

    powers = result.schedule.set_index("slot").charging_power_kw
    assert powers[1] == pytest.approx(1)
    assert result.metrics["solar_energy_to_ev_kwh"] == pytest.approx(1)
    assert result.slot_summary.grid_import_kw.min() >= -1e-8


def test_infeasible_session_is_reported():
    scenario = ChargingScenario(
        prices=[1],
        base_load_kw=[1],
        solar_kw=[0],
        sessions=[EVSession("ev-1", 0, 1, energy_kwh=2, max_power_kw=1)],
    )

    with pytest.raises(ValueError, match="Infeasible EV session"):
        run_lp(scenario)


def test_forecast_inputs_reuse_same_model():
    scenario = ChargingScenario(
        prices=[1, 1],
        base_load_kw=[1, 1],
        solar_kw=[0, 0],
        sessions=[EVSession("ev-1", 0, 2, energy_kwh=0.9, max_power_kw=1)],
    )

    result = run_lp(scenario, forecast_inputs={"solar_kw": np.array([1, 0])})

    assert result.status == "Optimal"
    assert result.slot_summary.solar_kw.tolist() == [1, 0]
