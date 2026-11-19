"""Dataset inspection, alignment, validation, and scenario construction."""

from pathlib import Path
from math import ceil, floor
from typing import Mapping

import pandas as pd

from LP_Optimizer.optimizer import EVSession

from .contracts import Scenario


def inventory_csvs(root: str | Path) -> pd.DataFrame:
    """List CSV files and their basic shape without altering raw data."""

    rows = []
    for path in sorted(Path(root).rglob("*.csv")):
        frame = pd.read_csv(path, nrows=5)
        rows.append({"path": str(path), "columns": ", ".join(frame.columns), "sample_rows": len(frame)})
    return pd.DataFrame(rows)


def build_scenario(
    timeseries: pd.DataFrame,
    sessions: pd.DataFrame,
    mapping: Mapping[str, str],
    scenario_id: str = "scenario-1",
    slot_hours: float = 1.0,
    emissions_factor_kg_per_kwh: float = 0.4,
) -> Scenario:
    """Build a validated scenario from aligned time-series and EV tables."""

    required = {"timestamp", "price", "base_load_kw", "solar_kw"}
    missing = required.difference(mapping)
    if missing:
        raise ValueError(f"mapping missing required keys: {sorted(missing)}")
    frame = timeseries.rename(columns={source: target for target, source in mapping.items()}).copy()
    expected = ["timestamp", "price", "base_load_kw", "solar_kw"]
    if any(column not in frame for column in expected):
        raise ValueError(f"timeseries must provide columns: {expected}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp")
    if frame[expected].isna().any().any():
        raise ValueError("timeseries contains missing required values")
    if (frame[["price", "base_load_kw", "solar_kw"]] < 0).any().any():
        raise ValueError("price, base load, and solar values must be non-negative")
    ev_columns = {"ev_id", "arrival", "departure", "energy_kwh", "max_power_kw"}
    if not ev_columns.issubset(sessions.columns):
        raise ValueError(f"sessions must provide columns: {sorted(ev_columns)}")
    ev_sessions = tuple(
        EVSession(
            ev_id=str(row.ev_id),
            arrival=int(row.arrival),
            departure=int(row.departure),
            energy_kwh=float(row.energy_kwh),
            max_power_kw=float(row.max_power_kw),
            efficiency=float(getattr(row, "efficiency", 0.9)),
            energy_is_battery_side=bool(getattr(row, "energy_is_battery_side", True)),
        )
        for row in sessions.itertuples(index=False)
    )
    scenario = Scenario(
        scenario_id=scenario_id,
        timestamps=tuple(frame["timestamp"]),
        prices=tuple(frame["price"]),
        base_load_kw=tuple(frame["base_load_kw"]),
        solar_kw=tuple(frame["solar_kw"]),
        sessions=ev_sessions,
        slot_hours=slot_hours,
        emissions_factor_kg_per_kwh=emissions_factor_kg_per_kwh,
    )
    scenario.validate()
    return scenario


def load_normalized_scenarios(
    root: str | Path,
    emissions_factor_kg_per_kwh: float = 0.225209,
) -> list[Scenario]:
    """Load the normalized common-base package into aligned scenarios."""

    package = Path(root)
    baseline = pd.read_csv(package / "common_hourly_baseline.csv")
    sessions = pd.read_csv(package / "ev_sessions_normalized.csv")
    mapping = pd.read_csv(package / "scenario_mapping.csv")
    required_baseline = {
        "timestamp_local",
        "base_load_kw_assumed",
        "pv_generation_kw",
        "energy_rate_usd_per_kwh",
    }
    missing = required_baseline.difference(baseline.columns)
    if missing:
        raise ValueError(f"normalized baseline is missing columns: {sorted(missing)}")
    required_sessions = {
        "session_id",
        "arrival_time_local_proxy",
        "departure_time_local_proxy",
        "energy_delivered_kwh_proxy",
        "p_max_kw_assumed",
    }
    missing = required_sessions.difference(sessions.columns)
    if missing:
        raise ValueError(f"normalized sessions are missing columns: {sorted(missing)}")
    required_mapping = {
        "session_id",
        "scenario_date_local",
        "scenario_horizon_start_local",
        "scenario_horizon_end_local",
    }
    missing = required_mapping.difference(mapping.columns)
    if missing:
        raise ValueError(f"scenario mapping is missing columns: {sorted(missing)}")

    baseline = baseline.copy()
    baseline["timestamp_local"] = pd.to_datetime(baseline["timestamp_local"], utc=True)
    baseline = baseline.sort_values("timestamp_local").drop_duplicates("timestamp_local")
    if baseline[["base_load_kw_assumed", "pv_generation_kw", "energy_rate_usd_per_kwh"]].isna().any().any():
        raise ValueError("normalized baseline contains missing required values")

    sessions = sessions.set_index("session_id")
    mapping["scenario_date_local"] = mapping["scenario_date_local"].astype(str)
    scenarios: list[Scenario] = []
    for scenario_date, group in mapping.groupby("scenario_date_local", sort=True):
        start = pd.Timestamp(group["scenario_horizon_start_local"].iloc[0], tz="UTC")
        end = pd.Timestamp(group["scenario_horizon_end_local"].iloc[0], tz="UTC")
        window = baseline[(baseline["timestamp_local"] >= start) & (baseline["timestamp_local"] < end)].copy()
        if window.empty:
            raise ValueError(f"no normalized environmental inputs for scenario {scenario_date}")
        expected_hours = int((end - start).total_seconds() / 3600)
        if len(window) != expected_hours:
            raise ValueError(
                f"scenario {scenario_date} has {len(window)} aligned rows; expected {expected_hours}"
            )
        session_objects = []
        for row in group.itertuples(index=False):
            source = sessions.loc[row.session_id]
            arrival = pd.Timestamp(source.arrival_time_local_proxy, tz="UTC")
            departure = pd.Timestamp(source.departure_time_local_proxy, tz="UTC")
            arrival_slot = floor((arrival - start).total_seconds() / 3600)
            departure_slot = ceil((departure - start).total_seconds() / 3600)
            if arrival_slot < 0 or departure_slot > len(window) or departure_slot <= arrival_slot:
                raise ValueError(f"invalid scenario slot mapping for session {row.session_id}")
            energy = float(source.energy_delivered_kwh_proxy)
            max_power = float(source.p_max_kw_assumed)
            if energy < 0 or max_power <= 0:
                raise ValueError(f"invalid energy or power for session {row.session_id}")
            session_objects.append(
                EVSession(
                    ev_id=str(row.session_id),
                    arrival=arrival_slot,
                    departure=departure_slot,
                    energy_kwh=energy,
                    max_power_kw=max_power,
                    efficiency=1.0,
                    energy_is_battery_side=False,
                )
            )
        scenario = Scenario(
            scenario_id=str(scenario_date),
            timestamps=tuple(window["timestamp_local"]),
            prices=tuple(window["energy_rate_usd_per_kwh"].astype(float)),
            base_load_kw=tuple(window["base_load_kw_assumed"].astype(float)),
            solar_kw=tuple(window["pv_generation_kw"].astype(float)),
            sessions=tuple(session_objects),
            slot_hours=1.0,
            emissions_factor_kg_per_kwh=emissions_factor_kg_per_kwh,
        )
        scenario.validate()
        scenarios.append(scenario)
    return scenarios
