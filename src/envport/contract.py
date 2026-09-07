"""Explicit probe contract; only trusted, locally supplied Python is executed."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class StepResult:
    observation: Any
    reward: float
    terminated: bool


@dataclass(frozen=True)
class ProbeSpec:
    """Environment-specific expectations, not universally inferred semantics.

    Action sequences must be valid from reset(seed). A successful oracle must
    produce at least oracle_grade_min; no-op must not exceed noop_grade_max.
    Bounds are inclusive. A probe may run at most 1,000 actions per sequence.
    """

    noop_actions: tuple[Any, ...]
    oracle_actions: tuple[Any, ...]
    reward_min: float = 0.0
    reward_max: float = 1.0
    grade_min: float = 0.0
    grade_max: float = 1.0
    noop_grade_max: float = 0.0
    oracle_grade_min: float = 1.0


class Environment(Protocol):
    """Observations and actions must be finite, JSON-compatible values.

    reset(seed) restores initial state; observe() is side-effect-free;
    grade() evaluates the current state without changing it; close() releases
    resources. envport_probe() is optional for basic reset/isolation checks.
    """

    def reset(self, seed: int) -> Any: ...
    def observe(self) -> Any: ...
    def step(self, action: Any) -> StepResult: ...
    def grade(self) -> float: ...
    def close(self) -> None: ...
