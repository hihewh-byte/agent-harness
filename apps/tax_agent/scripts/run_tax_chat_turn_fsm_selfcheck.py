#!/usr/bin/env python3
"""Tax chat turn FSM selfcheck — phase order + plan-before-compose (local P1)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_turn_fsm import (  # noqa: E402
    TaxTurnPhase,
    TaxTurnPhaseRecorder,
    plan_precedes_compose,
    validate_phase_transition,
)


def main() -> int:
    failed = 0

    assert validate_phase_transition(None, TaxTurnPhase.INIT)
    assert validate_phase_transition(TaxTurnPhase.INIT, TaxTurnPhase.SESSION)
    assert validate_phase_transition(TaxTurnPhase.SCOPE, TaxTurnPhase.PLAN)
    assert validate_phase_transition(TaxTurnPhase.PLAN, TaxTurnPhase.FAST_LANE)
    assert validate_phase_transition(TaxTurnPhase.FAST_LANE, TaxTurnPhase.POST_AUDIT)
    assert validate_phase_transition(TaxTurnPhase.PLAN, TaxTurnPhase.DONE)
    assert not validate_phase_transition(TaxTurnPhase.COMPOSE, TaxTurnPhase.PLAN)
    print("PASS phase transition guards")

    # Happy path: plan → fast_lane → post_audit → done
    rec = TaxTurnPhaseRecorder()
    for ph in (
        TaxTurnPhase.INIT,
        TaxTurnPhase.SESSION,
        TaxTurnPhase.SCOPE,
        TaxTurnPhase.PLAN,
        TaxTurnPhase.FAST_LANE,
        TaxTurnPhase.POST_AUDIT,
        TaxTurnPhase.DONE,
    ):
        rec.enter(ph)
    rec.assert_plan_before_compose()
    assert plan_precedes_compose(rec.phases)
    print("PASS plan-before-compose (fast lane)")

    # Compose path
    rec2 = TaxTurnPhaseRecorder()
    for ph in (
        TaxTurnPhase.INIT,
        TaxTurnPhase.SESSION,
        TaxTurnPhase.SCOPE,
        TaxTurnPhase.PLAN,
        TaxTurnPhase.COMPOSE,
        TaxTurnPhase.POST_AUDIT,
        TaxTurnPhase.DONE,
    ):
        rec2.enter(ph)
    rec2.assert_plan_before_compose()
    print("PASS plan-before-compose (compose)")

    # Clarify early exit
    rec3 = TaxTurnPhaseRecorder()
    for ph in (
        TaxTurnPhase.INIT,
        TaxTurnPhase.SESSION,
        TaxTurnPhase.SCOPE,
        TaxTurnPhase.CLARIFY,
        TaxTurnPhase.DONE,
    ):
        rec3.enter(ph)
    assert plan_precedes_compose(rec3.phases)  # no compose → ok
    print("PASS clarify early exit")

    # Violation: compose without plan
    bad = [
        TaxTurnPhase.INIT,
        TaxTurnPhase.SESSION,
        TaxTurnPhase.COMPOSE,
    ]
    if plan_precedes_compose(bad):
        print("FAIL: expected plan_precedes_compose=False for compose-without-plan")
        failed += 1
    else:
        print("PASS detects compose-without-plan")

    rec_bad = TaxTurnPhaseRecorder()
    rec_bad.phases = list(bad)
    try:
        rec_bad.assert_plan_before_compose()
        print("FAIL: assert_plan_before_compose should raise")
        failed += 1
    except RuntimeError:
        print("PASS assert_plan_before_compose raises on violation")

    print("run_tax_chat_turn_fsm_selfcheck:", "PASS" if failed == 0 else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
