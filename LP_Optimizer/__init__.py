"""Role 3 linear optimizer package."""

from .optimizer import ChargingScenario, EVSession, LPConfig, LPResult, run_lp


def run_lp_strategy(*args, **kwargs):
    """Lazily import the shared-contract adapter to avoid package cycles."""

    from .strategy import run_lp_strategy as _run_lp_strategy

    return _run_lp_strategy(*args, **kwargs)

__all__ = [
    "ChargingScenario",
    "EVSession",
    "LPConfig",
    "LPResult",
    "run_lp",
    "run_lp_strategy",
]
