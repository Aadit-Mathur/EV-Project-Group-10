"""Deterministic greedy Time-of-Use scheduler."""

from typing import Mapping

import pandas as pd

from Helpers.contracts import Scenario, ScheduleColumns
from Uncontrolled.scheduler import _schedule


def run_tou(scenario: Scenario) -> pd.DataFrame:
    """Allocate each EV's energy to cheapest eligible tariff slots."""

    scenario.validate()
    powers: dict[tuple[str, int], float] = {}
    for session in scenario.sessions:
        factor = session.efficiency if session.energy_is_battery_side else 1.0
        eligible = list(range(max(0, session.arrival), min(session.departure, scenario.slots)))
        possible = len(eligible) * session.max_power_kw * scenario.slot_hours * factor
        if possible + 1e-9 < session.energy_kwh:
            shortfall = max(0.0, session.energy_kwh - possible)
            raise ValueError(f"Infeasible EV session {session.ev_id!r}: shortfall {shortfall:.6g} kWh")
        remaining = session.energy_kwh
        for slot in sorted(eligible, key=lambda item: (float(scenario.prices[item]), item)):
            power = min(session.max_power_kw, remaining / (scenario.slot_hours * factor))
            powers[session.ev_id, slot] = power
            remaining -= power * scenario.slot_hours * factor
            if remaining <= 1e-9:
                break
    return _schedule(scenario, powers)
