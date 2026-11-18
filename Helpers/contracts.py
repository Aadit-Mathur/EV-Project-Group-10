"""Common scenario and schedule contracts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

import pandas as pd

from LP_Optimizer.optimizer import EVSession


class ScheduleColumns(StrEnum):
    SCENARIO_ID = "scenario_id"
    TIMESTAMP = "timestamp"
    EV_ID = "ev_id"
    CHARGING_POWER_KW = "charging_power_kw"


@dataclass(frozen=True)
class Scenario:
    """Aligned inputs consumed by every strategy."""

    scenario_id: str
    timestamps: Sequence[pd.Timestamp]
    prices: Sequence[float]
    base_load_kw: Sequence[float]
    solar_kw: Sequence[float]
    sessions: Sequence[EVSession]
    slot_hours: float = 1.0
    emissions_factor_kg_per_kwh: float = 0.4

    @property
    def slots(self) -> int:
        return len(self.timestamps)

    def validate(self) -> None:
        if self.slot_hours <= 0:
            raise ValueError("slot_hours must be positive")
        if self.slots == 0:
            raise ValueError("scenario must contain at least one timestamp")
        lengths = [len(self.prices), len(self.base_load_kw), len(self.solar_kw)]
        if any(length != self.slots for length in lengths):
            raise ValueError("timestamps, prices, base load, and solar must align")
        if self.emissions_factor_kg_per_kwh < 0:
            raise ValueError("emissions factor must be non-negative")
        pd.DatetimeIndex(self.timestamps)
