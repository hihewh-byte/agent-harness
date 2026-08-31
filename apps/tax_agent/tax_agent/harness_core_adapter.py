"""Thin bridge: tax plans/phases → ``harness_core`` (monorepo or sibling package)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


class HarnessCoreUnavailable(ImportError):
    """``harness_core`` not on PYTHONPATH."""


def _candidate_src_dirs() -> list[Path]:
    here = Path(__file__).resolve()
    roots: list[Path] = []
    env = (os.environ.get("HARNESS_CORE_SRC") or "").strip()
    if env:
        roots.append(Path(env))
    for anc in here.parents:
        for parts in (
            ("packages", "harness_core", "src"),
            ("harness_core", "src"),
        ):
            src = anc.joinpath(*parts)
            if (src / "harness_core").is_dir():
                roots.append(src)
    # Legacy myAgents layout: tax_agent beside harness_core/
    legacy = here.parents[2] / "harness_core" / "src"
    if (legacy / "harness_core").is_dir():
        roots.append(legacy)
    deduped: list[Path] = []
    seen: set[str] = set()
    for src in roots:
        key = str(src.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(src)
    return deduped


def ensure_harness_core() -> None:
    try:
        import harness_core  # noqa: F401

        return
    except ImportError:
        pass
    for src in _candidate_src_dirs():
        if (src / "harness_core").is_dir():
            p = str(src)
            if p not in sys.path:
                sys.path.insert(0, p)
            try:
                import harness_core  # noqa: F401

                return
            except ImportError:
                continue
    raise HarnessCoreUnavailable(
        "harness_core not found; pip install -e packages/harness_core or set HARNESS_CORE_SRC"
    )


def harness_core_available() -> bool:
    try:
        ensure_harness_core()
        return True
    except HarnessCoreUnavailable:
        return False


def to_core_plan(plan: Any) -> Any:
    """Map ``FilingTurnPlan`` → ``TurnPlanData`` (domain fields → domain_meta)."""
    ensure_harness_core()
    from harness_core.turn_plan import as_turn_plan_data

    return as_turn_plan_data(plan)


def record_domain_phases(domain_phase_names: Sequence[str]) -> Any:
    ensure_harness_core()
    from harness_core.turn_fsm import PhaseRecorder, map_domain_phase

    rec = PhaseRecorder()
    for name in domain_phase_names:
        core = map_domain_phase(str(name))
        rec.enter(core, domain_alias=str(name))
    return rec


def assert_plan_before_compose_domain(domain_phase_names: Sequence[str]) -> None:
    rec = record_domain_phases(domain_phase_names)
    rec.assert_plan_before_compose()


def mirror_domain_recorder(domain_phase_names: Sequence[str]) -> list[str]:
    rec = record_domain_phases(domain_phase_names)
    rec.assert_plan_before_compose()
    return rec.as_names()


def integrity_from_mapping(data: Mapping[str, Any] | None) -> Any:
    ensure_harness_core()
    from harness_core.integrity import IntegrityResult

    return IntegrityResult.from_mapping(data)


def plan_vs_actual_via_core(
    plan: Any,
    *,
    tools_executed: Sequence[str] = (),
    slot_contents: Mapping[str, str] | None = None,
    tool_error: str | None = None,
    integrity: Mapping[str, Any] | None = None,
) -> list[str]:
    ensure_harness_core()
    from harness_core.plan_vs_actual import compute_plan_vs_actual

    return compute_plan_vs_actual(
        to_core_plan(plan),
        tools_executed=tools_executed,
        slot_contents=slot_contents,
        tool_error=tool_error,
        integrity=integrity,
    )


def smoke_adapter_roundtrip(plan: Any) -> dict[str, Any]:
    core_plan = to_core_plan(plan)
    phases = [
        "init",
        "session",
        "scope",
        "plan",
        "fast_lane",
        "post_audit",
        "done",
    ]
    rec = record_domain_phases(phases)
    rec.assert_plan_before_compose()
    return {
        "core_profile": core_plan.profile,
        "core_slots_tier0": list(core_plan.slots_tier0),
        "core_fast_lane": bool(core_plan.fast_lane),
        "core_phases": rec.as_names(),
        "domain_aliases": list(rec.domain_aliases),
        "domain_meta": dict(core_plan.domain_meta),
    }


__all__ = [
    "HarnessCoreUnavailable",
    "assert_plan_before_compose_domain",
    "ensure_harness_core",
    "harness_core_available",
    "integrity_from_mapping",
    "mirror_domain_recorder",
    "plan_vs_actual_via_core",
    "record_domain_phases",
    "smoke_adapter_roundtrip",
    "to_core_plan",
]
