"""Continuous LP scheduler for EV smart charging.

The model follows the finalized project roadmap:

* one-hour slots (or an explicitly supplied slot duration),
* battery-side energy requirements by default,
* no grid export,
* solar serves base load before EV charging,
* normalized objective weights of 1:5:2 for cost, peak, and solar use.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pulp


@dataclass(frozen=True)
class EVSession:
    """One EV charging session.

    ``arrival`` is inclusive and ``departure`` is exclusive. ``energy_kwh``
    is battery-side energy unless ``energy_is_battery_side`` is false.
    """

    ev_id: str
    arrival: int
    departure: int
    energy_kwh: float
    max_power_kw: float
    efficiency: float = 0.9
    energy_is_battery_side: bool = True


@dataclass(frozen=True)
class LPConfig:
    """Numerical and solver settings for :func:`run_lp`."""

    slot_hours: float = 1.0
    cost_weight: float = 1.0
    peak_weight: float = 5.0
    solar_weight: float = 2.0
    solver_msg: bool = False
    time_limit_seconds: int | None = None


@dataclass(frozen=True)
class ChargingScenario:
    """Inputs shared by all charging strategies."""

    prices: Sequence[float]
    base_load_kw: Sequence[float]
    solar_kw: Sequence[float]
    sessions: Sequence[EVSession]


@dataclass(frozen=True)
class LPResult:
    """Schedule and auditable LP outputs."""

    status: str
    objective: float
    schedule: pd.DataFrame
    slot_summary: pd.DataFrame
    metrics: Mapping[str, float]


def run_lp(
    scenario: ChargingScenario,
    forecast_inputs: Mapping[str, Sequence[float]] | None = None,
    config: LPConfig | None = None,
) -> LPResult:
    """Solve the forecast-based or perfect-foresight smart charging LP.

    ``forecast_inputs`` may contain ``solar_kw`` and/or ``base_load_kw``.
    Omitting it uses the scenario values, which is the perfect-foresight
    mode when those values are actual future inputs.
    """

    config = config or LPConfig()
    prices, base_load, solar = _resolve_inputs(scenario, forecast_inputs)
    _validate_inputs(prices, base_load, solar, scenario.sessions, config)
    slots = len(prices)

    infeasible = _infeasible_sessions(scenario.sessions, slots, config.slot_hours)
    if infeasible:
        details = ", ".join(f"{ev_id} (shortfall {shortfall:.6g} kWh)" for ev_id, shortfall in infeasible)
        raise ValueError(f"Infeasible EV session(s): {details}")

    available = {
        (session.ev_id, t): session.arrival <= t < session.departure
        for session in scenario.sessions
        for t in range(slots)
    }
    problem = pulp.LpProblem("ev_smart_charging", pulp.LpMinimize)
    power = {
        (session.ev_id, t): pulp.LpVariable(
            f"power_{_safe_name(session.ev_id)}_{t}", lowBound=0
        )
        for session in scenario.sessions
        for t in range(slots)
    }
    grid = {
        t: pulp.LpVariable(f"grid_import_{t}", lowBound=0) for t in range(slots)
    }
    solar_to_ev = {
        t: pulp.LpVariable(f"solar_to_ev_{t}", lowBound=0) for t in range(slots)
    }
    peak = pulp.LpVariable("peak_grid_import", lowBound=0)

    for session in scenario.sessions:
        delivered = pulp.lpSum(
            power[session.ev_id, t]
            * config.slot_hours
            * (session.efficiency if session.energy_is_battery_side else 1.0)
            for t in range(slots)
        )
        problem += delivered == session.energy_kwh, f"energy_{_safe_name(session.ev_id)}"
        for t in range(slots):
            if available[session.ev_id, t]:
                problem += (
                    power[session.ev_id, t] <= session.max_power_kw,
                    f"power_limit_{_safe_name(session.ev_id)}_{t}",
                )
            else:
                problem += power[session.ev_id, t] == 0, f"unavailable_{_safe_name(session.ev_id)}_{t}"

    ev_power = {
        t: pulp.lpSum(power[session.ev_id, t] for session in scenario.sessions)
        for t in range(slots)
    }
    surplus = np.maximum(0.0, solar - base_load)
    for t in range(slots):
        problem += grid[t] >= base_load[t] + ev_power[t] - solar[t], f"grid_balance_{t}"
        problem += grid[t] <= peak, f"peak_{t}"
        problem += solar_to_ev[t] <= ev_power[t], f"solar_ev_power_{t}"
        problem += solar_to_ev[t] <= float(surplus[t]), f"solar_surplus_{t}"

    ev_grid_energy = sum(
        session.energy_kwh / session.efficiency
        if session.energy_is_battery_side
        else session.energy_kwh
        for session in scenario.sessions
    )
    mean_price = float(np.mean(prices))
    c_ref = mean_price * ev_grid_energy
    p_ref = max(
        float(base_load[t])
        + sum(
            session.max_power_kw
            for session in scenario.sessions
            if available[session.ev_id, t]
        )
        for t in range(slots)
    )
    if c_ref <= 0 or p_ref <= 0 or ev_grid_energy <= 0:
        raise ValueError("prices, base load, and EV requirements must produce positive normalization references")

    base_only_grid = np.maximum(0.0, base_load - solar)
    cost = pulp.lpSum(
        prices[t] * (grid[t] - float(base_only_grid[t])) * config.slot_hours
        for t in range(slots)
    )
    solar_used = pulp.lpSum(solar_to_ev[t] * config.slot_hours for t in range(slots))
    objective = (
        config.cost_weight * cost / c_ref
        + config.peak_weight * peak / p_ref
        - config.solar_weight * solar_used / ev_grid_energy
    )
    problem += objective

    solver = pulp.PULP_CBC_CMD(msg=config.solver_msg, timeLimit=config.time_limit_seconds)
    status_code = problem.solve(solver)
    status = pulp.LpStatus.get(status_code, "Unknown")
    if status != "Optimal":
        raise RuntimeError(f"LP solver did not return an acceptable status: {status}")

    rows = []
    for session in scenario.sessions:
        for t in range(slots):
            rows.append(
                {
                    "ev_id": session.ev_id,
                    "slot": t,
                    "charging_power_kw": _value(power[session.ev_id, t]),
                    "available": available[session.ev_id, t],
                }
            )
    schedule = pd.DataFrame(rows)
    slot_summary = pd.DataFrame(
        {
            "slot": range(slots),
            "ev_power_kw": [_value(ev_power[t]) for t in range(slots)],
            "grid_import_kw": [_value(grid[t]) for t in range(slots)],
            "solar_to_ev_kw": [_value(solar_to_ev[t]) for t in range(slots)],
            "base_load_kw": base_load,
            "solar_kw": solar,
            "price": prices,
        }
    )
    metrics = _metrics(
        schedule, slot_summary, scenario.sessions, config, c_ref, p_ref, ev_grid_energy
    )
    _verify_solution(schedule, slot_summary, scenario.sessions, config)
    return LPResult(
        status=status,
        objective=float(pulp.value(problem.objective)),
        schedule=schedule,
        slot_summary=slot_summary,
        metrics=metrics,
    )


def _resolve_inputs(
    scenario: ChargingScenario,
    forecast_inputs: Mapping[str, Sequence[float]] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    inputs = forecast_inputs or {}
    return (
        np.asarray(scenario.prices, dtype=float),
        np.asarray(inputs.get("base_load_kw", scenario.base_load_kw), dtype=float),
        np.asarray(inputs.get("solar_kw", scenario.solar_kw), dtype=float),
    )


def _validate_inputs(
    prices: np.ndarray,
    base_load: np.ndarray,
    solar: np.ndarray,
    sessions: Sequence[EVSession],
    config: LPConfig,
) -> None:
    if config.slot_hours <= 0:
        raise ValueError("slot_hours must be positive")
    if len(prices) == 0 or not (len(prices) == len(base_load) == len(solar)):
        raise ValueError("prices, base_load_kw, and solar_kw must be non-empty and equally sized")
    if not np.isfinite(np.concatenate((prices, base_load, solar))).all():
        raise ValueError("scenario time series must contain only finite values")
    if (prices < 0).any() or (base_load < 0).any() or (solar < 0).any():
        raise ValueError("prices, base load, and solar values must be non-negative")
    ids = [session.ev_id for session in sessions]
    if len(ids) != len(set(ids)):
        raise ValueError("EV session identifiers must be unique")
    for session in sessions:
        if not session.ev_id or session.arrival < 0 or session.departure <= session.arrival:
            raise ValueError(f"invalid availability window for {session.ev_id!r}")
        if session.energy_kwh <= 0 or session.max_power_kw <= 0:
            raise ValueError(f"energy and max power must be positive for {session.ev_id!r}")
        if not 0 < session.efficiency <= 1:
            raise ValueError(f"efficiency must be in (0, 1] for {session.ev_id!r}")


def _infeasible_sessions(
    sessions: Sequence[EVSession], slots: int, slot_hours: float
) -> list[tuple[str, float]]:
    result = []
    for session in sessions:
        available_slots = max(0, min(session.departure, slots) - session.arrival)
        efficiency = session.efficiency if session.energy_is_battery_side else 1.0
        capacity = available_slots * session.max_power_kw * slot_hours * efficiency
        if session.arrival >= slots or capacity + 1e-9 < session.energy_kwh:
            result.append((session.ev_id, max(0.0, session.energy_kwh - capacity)))
    return result


def _verify_solution(
    schedule: pd.DataFrame,
    slot_summary: pd.DataFrame,
    sessions: Sequence[EVSession],
    config: LPConfig,
) -> None:
    for session in sessions:
        actual = schedule.loc[schedule.ev_id == session.ev_id, "charging_power_kw"].to_numpy()
        factor = session.efficiency if session.energy_is_battery_side else 1.0
        delivered = float(actual.sum() * config.slot_hours * factor)
        if not np.isclose(delivered, session.energy_kwh, atol=1e-6):
            raise RuntimeError(f"post-solve energy verification failed for {session.ev_id}")
        outside = schedule[(schedule.ev_id == session.ev_id) & ~schedule.available]
        if not np.allclose(outside.charging_power_kw, 0, atol=1e-7):
            raise RuntimeError(f"post-solve availability verification failed for {session.ev_id}")
        inside = schedule[(schedule.ev_id == session.ev_id) & schedule.available]
        if (inside.charging_power_kw > session.max_power_kw + 1e-7).any():
            raise RuntimeError(f"post-solve power verification failed for {session.ev_id}")
    if (slot_summary.grid_import_kw < -1e-7).any():
        raise RuntimeError("post-solve grid import verification failed")


def _metrics(
    schedule: pd.DataFrame,
    slot_summary: pd.DataFrame,
    sessions: Sequence[EVSession],
    config: LPConfig,
    c_ref: float,
    p_ref: float,
    ev_grid_energy: float,
) -> dict[str, float]:
    base_only = np.maximum(0, slot_summary.base_load_kw - slot_summary.solar_kw)
    cost = float(
        np.sum(
            slot_summary.price
            * (slot_summary.grid_import_kw - base_only)
            * config.slot_hours
        )
    )
    solar_used = float(slot_summary.solar_to_ev_kw.sum() * config.slot_hours)
    peak = float(slot_summary.grid_import_kw.max())
    return {
        "charging_cost": cost,
        "peak_grid_import_kw": peak,
        "solar_energy_to_ev_kwh": solar_used,
        "normalized_cost": cost / c_ref,
        "normalized_peak": peak / p_ref,
        "normalized_solar": solar_used / ev_grid_energy,
        "ev_grid_energy_kwh": ev_grid_energy,
    }


def _value(variable: pulp.LpVariable | pulp.LpAffineExpression) -> float:
    value = pulp.value(variable)
    if value is None:
        raise RuntimeError("solver returned an unset variable")
    return float(value)


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)
