"""Shared schedule validation and strategy metrics."""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .contracts import Scenario, ScheduleColumns


def validate_schedule(schedule: pd.DataFrame, scenario: Scenario) -> list[str]:
    """Return physical validation errors instead of hiding invalid schedules."""

    errors: list[str] = []
    required = {column.value for column in ScheduleColumns}
    missing = required.difference(schedule.columns)
    if missing:
        return [f"missing schedule columns: {sorted(missing)}"]
    if schedule[list(required)].isna().any().any():
        errors.append("schedule contains missing required values")

    try:
        timestamps = pd.DatetimeIndex(scenario.timestamps)
        schedule_timestamps = pd.to_datetime(schedule[ScheduleColumns.TIMESTAMP])
    except (TypeError, ValueError):
        errors.append("schedule contains invalid timestamps")
        schedule_timestamps = pd.Series(dtype="datetime64[ns]")

    if len(schedule_timestamps) and not schedule_timestamps.isin(timestamps).all():
        errors.append("schedule contains timestamps outside the scenario horizon")
    if len(schedule_timestamps) and schedule.assign(
        _timestamp=schedule_timestamps
    ).duplicated([ScheduleColumns.EV_ID, "_timestamp"]).any():
        errors.append("schedule contains duplicate EV/timestamp rows")

    if schedule[ScheduleColumns.SCENARIO_ID].dropna().astype(str).nunique() > 1:
        errors.append("schedule contains multiple scenario IDs")

    known_ids = {str(session.ev_id) for session in scenario.sessions}
    schedule_ids = set(schedule[ScheduleColumns.EV_ID].dropna().astype(str))
    if schedule_ids - known_ids:
        errors.append("schedule contains unknown EV identifiers")

    for session in scenario.sessions:
        rows = schedule[schedule[ScheduleColumns.EV_ID].astype(str) == str(session.ev_id)].copy()
        if len(rows) != scenario.slots:
            errors.append(f"{session.ev_id}: expected {scenario.slots} rows, got {len(rows)}")
            continue
        rows = rows.assign(_timestamp=schedule_timestamps.loc[rows.index])
        rows = rows.set_index("_timestamp").reindex(timestamps)
        if rows.isna().all(axis=1).any():
            errors.append(f"{session.ev_id}: missing one or more scenario timestamps")
        try:
            powers = rows[ScheduleColumns.CHARGING_POWER_KW].to_numpy(dtype=float)
        except (TypeError, ValueError):
            errors.append(f"{session.ev_id}: charging power must be numeric")
            continue
        if np.any(~np.isfinite(powers)) or np.any(powers < -1e-7):
            errors.append(f"{session.ev_id}: charging power must be finite and non-negative")
        for slot, power in enumerate(powers):
            if not session.arrival <= slot < session.departure and abs(power) > 1e-7:
                errors.append(f"{session.ev_id}: power outside availability at slot {slot}")
            if session.arrival <= slot < session.departure and power > session.max_power_kw + 1e-7:
                errors.append(f"{session.ev_id}: power exceeds charger limit at slot {slot}")
        delivered = powers.sum() * scenario.slot_hours * (
            session.efficiency if session.energy_is_battery_side else 1.0
        )
        if not np.isclose(delivered, session.energy_kwh, atol=1e-6):
            errors.append(
                f"{session.ev_id}: delivered energy {delivered:.6g} "
                f"!= {session.energy_kwh:.6g}"
            )
    return errors


def evaluate_schedule(schedule: pd.DataFrame, scenario: Scenario) -> dict[str, float | bool]:
    """Evaluate a schedule against the actual scenario inputs."""

    scenario.validate()
    errors = validate_schedule(schedule, scenario)
    powers = (
        schedule.groupby(ScheduleColumns.TIMESTAMP)[ScheduleColumns.CHARGING_POWER_KW]
        .sum()
        .reindex(pd.DatetimeIndex(scenario.timestamps), fill_value=0.0)
        .to_numpy(dtype=float)
    )
    base = np.asarray(scenario.base_load_kw, dtype=float)
    solar = np.asarray(scenario.solar_kw, dtype=float)
    prices = np.asarray(scenario.prices, dtype=float)
    grid = np.maximum(0.0, base + powers - solar)
    base_only = np.maximum(0.0, base - solar)
    solar_to_ev = np.minimum(powers, np.maximum(0.0, solar - base))
    grid_energy = float(grid.sum() * scenario.slot_hours)
    incremental_cost = float(
        np.sum(prices * (grid - base_only) * scenario.slot_hours)
    )
    solar_energy = float(solar_to_ev.sum() * scenario.slot_hours)
    return {
        "feasible": not errors,
        "validation_error_count": float(len(errors)),
        "charging_cost": incremental_cost,
        "peak_grid_import_kw": float(grid.max()),
        "solar_energy_to_ev_kwh": solar_energy,
        "grid_energy_imported_kwh": grid_energy,
        "co2_kg": grid_energy * scenario.emissions_factor_kg_per_kwh,
        "ev_grid_energy_kwh": float(
            sum(
                session.energy_kwh / session.efficiency
                if session.energy_is_battery_side
                else session.energy_kwh
                for session in scenario.sessions
            )
        ),
        "validation_errors": "; ".join(errors),
    }


def evaluate_strategies(
    schedules: Mapping[str, pd.DataFrame],
    scenario: Scenario,
) -> pd.DataFrame:
    """Evaluate every strategy with the same physical metric definitions."""

    rows = []
    for strategy, schedule in schedules.items():
        rows.append({"strategy": strategy, **evaluate_schedule(schedule, scenario)})
    return pd.DataFrame(rows)
