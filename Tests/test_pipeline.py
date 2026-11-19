import pytest

from Helpers.evaluator import evaluate_schedule
from Experiments.run_real import run_experiment
from Helpers.data_pipeline import load_normalized_scenarios
from Helpers.forecasting import forecast_target
from TOU.scheduler import run_tou
from Uncontrolled.scheduler import run_uncontrolled
import pandas as pd


@pytest.fixture
def scenario():
    scenarios = load_normalized_scenarios("Data/normalised/ev_common_base")
    return scenarios[0]


def test_baselines_share_contract_and_meet_energy(scenario):
    for schedule in (run_uncontrolled(scenario), run_tou(scenario)):
        assert list(schedule.columns) == [
            "scenario_id",
            "timestamp",
            "ev_id",
            "charging_power_kw",
        ]
        assert evaluate_schedule(schedule, scenario)["feasible"]


def test_experiment_runs_both_lp_information_modes(scenario):
    result = run_experiment(scenario, sensitivity=True)
    assert {"uncontrolled", "tou", "lp_perfect_foresight"} == set(result.schedules)
    assert set(result.information_mode_metrics.information_mode) == {"lp_perfect_foresight"}
    assert "lp_equal_weights_sensitivity" in set(result.metrics.strategy)


def test_normalized_chronological_forecast_contract():
    baseline = pd.read_csv(
        "Data/normalised/ev_common_base/common_hourly_baseline.csv"
    ).rename(
        columns={
            "timestamp_utc": "timestamp",
            "pv_generation_kw": "solar_kw",
        }
    )
    result = forecast_target(
        baseline[["timestamp", "solar_kw"]],
        "solar_kw",
    )
    assert result.predictions["timestamp"].is_monotonic_increasing
    assert result.metrics["model_mae"] >= 0
    assert result.metrics["train_fraction"] == 0.70
    assert result.metrics["validation_fraction"] == 0.15


def test_normalized_common_base_loads_all_scenarios():
    scenarios = load_normalized_scenarios("Data/normalised/ev_common_base")
    assert len(scenarios) == 45
    assert sum(len(item.sessions) for item in scenarios) == 100
    assert min(item.slots for item in scenarios) >= 24
    assert all(session.energy_is_battery_side is False for item in scenarios for session in item.sessions)
