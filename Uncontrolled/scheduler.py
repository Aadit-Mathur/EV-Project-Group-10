"""Immediate charging baseline."""

from typing import Mapping

import pandas as pd

from Helpers.contracts import Scenario, ScheduleColumns


def _schedule(scenario: Scenario, powers: Mapping[tuple[str, int], float]) -> pd.DataFrame:
    rows = []
    for session in scenario.sessions:
        for slot, timestamp in enumerate(scenario.timestamps):
            rows.append(
                {
                    ScheduleColumns.SCENARIO_ID: scenario.scenario_id,
                    ScheduleColumns.TIMESTAMP: pd.Timestamp(timestamp),
                    ScheduleColumns.EV_ID: session.ev_id,
                    ScheduleColumns.CHARGING_POWER_KW: float(powers.get((session.ev_id, slot), 0.0)),
                }
            )
    return pd.DataFrame(rows)


def run_uncontrolled(scenario: Scenario) -> pd.DataFrame:
    """Charge immediately at maximum power, without looking ahead."""

    scenario.validate()
    powers: dict[tuple[str, int], float] = {}
    for session in scenario.sessions:
        remaining = session.energy_kwh
        factor = session.efficiency if session.energy_is_battery_side else 1.0
        capacity = max(0, min(session.departure, scenario.slots) - session.arrival)
        possible = capacity * session.max_power_kw * scenario.slot_hours * factor
        if session.arrival >= scenario.slots or possible + 1e-9 < remaining:
            shortfall = max(0.0, remaining - possible)
            raise ValueError(f"Infeasible EV session {session.ev_id!r}: shortfall {shortfall:.6g} kWh")
        for slot in range(scenario.slots):
            if session.arrival <= slot < session.departure and remaining > 1e-9:
                power = min(session.max_power_kw, remaining / (scenario.slot_hours * factor))
                powers[session.ev_id, slot] = power
                remaining -= power * scenario.slot_hours * factor
    return _schedule(scenario, powers)
