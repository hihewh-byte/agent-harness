"""Tax chat turn FSM — phase order guards (PHA chat_turn_fsm twin, local-only).

Enforces Plan-before-Compose for filing turns. Disable with TAX_CHAT_TURN_FSM=0.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Sequence


class TaxTurnPhase(str, Enum):
    """Ordered harness phases for one /tax/chat turn."""

    INIT = "init"
    SESSION = "session"
    SCOPE = "scope"
    CLARIFY = "clarify"
    PLAN = "plan"
    FAST_LANE = "fast_lane"
    COMPOSE = "compose"
    POST_AUDIT = "post_audit"
    DONE = "done"
    ERROR = "error"


_PHASE_RANK = {p: i for i, p in enumerate(TaxTurnPhase)}

_PLAN_PHASES = frozenset({TaxTurnPhase.PLAN})
_COMPOSE_PHASES = frozenset({TaxTurnPhase.COMPOSE, TaxTurnPhase.FAST_LANE})


def fsm_strict_enabled() -> bool:
    return (os.environ.get("TAX_CHAT_TURN_FSM") or "1").strip().lower() not in (
        "0",
        "false",
        "off",
    )


def validate_phase_transition(
    previous: TaxTurnPhase | None,
    next_phase: TaxTurnPhase,
) -> bool:
    if previous is None:
        return next_phase == TaxTurnPhase.INIT
    if next_phase == TaxTurnPhase.ERROR:
        return True
    # Allow DONE from any non-error phase (early exits: clarify / profile)
    if next_phase == TaxTurnPhase.DONE:
        return previous != TaxTurnPhase.ERROR
    prev_rank = _PHASE_RANK.get(previous, -1)
    next_rank = _PHASE_RANK.get(next_phase, -1)
    return next_rank >= prev_rank


def plan_precedes_compose(phases: Sequence[TaxTurnPhase]) -> bool:
    """True when PLAN ran before COMPOSE/FAST_LANE (or no compose occurred)."""
    plan_idx = None
    compose_idx = None
    for i, ph in enumerate(phases):
        if ph in _PLAN_PHASES and plan_idx is None:
            plan_idx = i
        if ph in _COMPOSE_PHASES and compose_idx is None:
            compose_idx = i
    if compose_idx is None:
        return True
    if plan_idx is None:
        return False
    return plan_idx < compose_idx


@dataclass
class TaxTurnPhaseRecorder:
    phases: List[TaxTurnPhase] = field(default_factory=list)

    def enter(self, phase: TaxTurnPhase) -> None:
        prev = self.phases[-1] if self.phases else None
        if fsm_strict_enabled() and not validate_phase_transition(prev, phase):
            raise RuntimeError(f"invalid tax turn phase transition: {prev} -> {phase}")
        self.phases.append(phase)

    def assert_plan_before_compose(self) -> None:
        if not plan_precedes_compose(self.phases):
            raise RuntimeError(
                "consensus violation: COMPOSE/FAST_LANE reached without PLAN phase",
            )

    def as_names(self) -> list[str]:
        return [p.value for p in self.phases]


__all__ = [
    "TaxTurnPhase",
    "TaxTurnPhaseRecorder",
    "fsm_strict_enabled",
    "plan_precedes_compose",
    "validate_phase_transition",
]
