"""Adapter from the shared scenario contract to the existing LP optimizer."""

from typing import Mapping, Sequence

import pandas as pd

from Helpers.contracts import Scenario, ScheduleColumns
from .optimizer import ChargingScenario, LPConfig, run_lp


def run_lp_strategy(
    scenario: Scenario,
    forecast_inputs: Mapping[str, Sequence[float]] | None = None,
    config: LPConfig | None = None,
) -> pd.DataFrame:
    """Run the continuous LP and adapt its output to the shared contract."""

    scenario.validate()
    result = run_lp(
        scenario=ChargingScenario(
            prices=scenario.prices,
            base_load_kw=scenario.base_load_kw,
            solar_kw=scenario.solar_kw,
            sessions=scenario.sessions,
        ),
        forecast_inputs=forecast_inputs,
        config=config or LPConfig(slot_hours=scenario.slot_hours),
    )
    schedule = result.schedule.copy()
    schedule[ScheduleColumns.SCENARIO_ID] = scenario.scenario_id
    schedule[ScheduleColumns.TIMESTAMP] = [
        pd.Timestamp(scenario.timestamps[int(slot)]) for slot in schedule["slot"]
    ]
    return schedule[
        [
            ScheduleColumns.SCENARIO_ID,
            ScheduleColumns.TIMESTAMP,
            ScheduleColumns.EV_ID,
            ScheduleColumns.CHARGING_POWER_KW,
        ]
    ]
