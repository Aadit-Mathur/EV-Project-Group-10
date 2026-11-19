import pytest

from Helpers.evaluator import evaluate_schedule
from Experiments.run_real import run_experiment
from Experiments.run_real import save_rebound_artifacts
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


def test_rebound_artifacts_are_derived_from_real_scenario_schedules(tmp_path):
    rebound_rows = [
        {
            "scenario_id": "A",
            "uncontrolled_peak_ev_kw": 10.0,
            "tou_peak_ev_kw": 14.0,
            "uncontrolled_peak_grid_kw": 40.0,
            "tou_peak_grid_kw": 44.0,
            "uncontrolled_peak_grid_slot": 1,
            "tou_peak_grid_slot": 2,
            "uncontrolled_peak_local_hour": 1,
            "tou_peak_local_hour": 2,
        },
        {
            "scenario_id": "B",
            "uncontrolled_peak_ev_kw": 12.0,
            "tou_peak_ev_kw": 11.0,
            "uncontrolled_peak_grid_kw": 45.0,
            "tou_peak_grid_kw": 43.0,
            "uncontrolled_peak_grid_slot": 3,
            "tou_peak_grid_slot": 4,
            "uncontrolled_peak_local_hour": 3,
            "tou_peak_local_hour": 4,
        },
    ]
    profile_rows = [
        {
            "scenario_id": "A",
            "local_hour": 1,
            "uncontrolled_ev_kw": 10.0,
            "tou_ev_kw": 14.0,
            "uncontrolled_grid_kw": 40.0,
            "tou_grid_kw": 44.0,
        },
        {
            "scenario_id": "B",
            "local_hour": 1,
            "uncontrolled_ev_kw": 12.0,
            "tou_ev_kw": 11.0,
            "uncontrolled_grid_kw": 45.0,
            "tou_grid_kw": 43.0,
        },
    ]

    summary = save_rebound_artifacts(rebound_rows, profile_rows, tmp_path)
    values = dict(zip(summary["metric"], summary["value"]))
    assert values["tou_peak_grid_higher_count"] == 1
    assert values["tou_peak_grid_lower_count"] == 1
    assert (tmp_path / "tou_rebound_peak.csv").exists()
    assert (tmp_path / "tou_rebound_summary.csv").exists()
    assert (tmp_path / "tou_rebound_profile.png").exists()
