#!/usr/bin/env python3
"""Stage 2 selfcheck — semantic proposal gate, turn adoption, metric_pick clarify (no LLM)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_HEALTH_INTENT_CATALOG", "1")

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def _prop(kind: str, *pairs: tuple[str, str], error: str = "") -> dict:
    out = {"kind": kind, "metrics": [{"metric_id": m, "evidence": e} for m, e in pairs], "latency_ms": 0}
    if error:
        out["error"] = error
    return out


def gate_cases() -> None:
    from pha.semantic_intent import gate_proposal

    msg = "我今天在阳光下待的时间是不是太短了？"
    d = gate_proposal(msg, _prop("metric_query", ("time_in_daylight_min", "在阳光下待的时间")))
    check("gate adopt verbatim evidence", d.action == "adopt" and d.metric_ids == ["time_in_daylight_min"], str(d))
    d = gate_proposal(msg, _prop("metric_query", ("time_in_daylight_min", "日照时长")))
    check("gate reject non-verbatim evidence", d.action == "none", str(d))
    d = gate_proposal(msg, _prop("feeling_or_symptom", ("time_in_daylight_min", "在阳光下待的时间")))
    check("gate none on feeling kind", d.action == "none", str(d))
    d = gate_proposal(msg, _prop("metric_query", ("time_in_daylight_min", "今天")))
    check("gate reject modifier-only evidence", d.action == "none", str(d))
    d = gate_proposal(msg, _prop("metric_query", ("time_in_daylight_min", "阳")))
    check("gate reject too-short evidence", d.action == "none", str(d))
    d = gate_proposal(msg, _prop("metric_query", ("not_a_metric", "在阳光下待的时间")))
    check("gate reject non-eligible id", d.action == "none", str(d))
    d = gate_proposal(msg, _prop("metric_query", ("time_in_daylight_min", "在阳光下"), error="ConnectError"))
    check("gate none on proposer error", d.action == "none", str(d))
    msg2 = "运动后心跳恢复得怎么样"
    d = gate_proposal(
        msg2,
        _prop("metric_query", ("hrv_sdnn_ms", "心跳恢复"), ("resting_heart_rate_bpm", "心跳恢复")),
    )
    check(
        "gate clarify on shared evidence",
        d.action == "clarify" and set(d.candidates) == {"hrv_sdnn_ms", "resting_heart_rate_bpm"},
        str(d),
    )


def verify_cases() -> None:
    import pha.semantic_intent as si

    msg = "我今天在阳光下待的时间是不是太短了？"
    prop = _prop("metric_query", ("time_in_daylight_min", "在阳光下待的时间"))
    adopt = si.SemanticDecision("adopt", metric_ids=["time_in_daylight_min"])
    real = si.verify_metric
    try:
        for repick, want_action, want in (
            ("time_in_daylight_min", "adopt", ["time_in_daylight_min"]),
            ("environmental_audio_db", "clarify", ["time_in_daylight_min", "environmental_audio_db"]),
            ("none", "none", []),
        ):
            si.verify_metric = lambda *_a, _r=repick, **_k: {"metric_id": _r, "latency_ms": 0}  # type: ignore[assignment]
            d = si.verify_decision(msg, dict(prop), adopt)
            got = d.metric_ids if want_action == "adopt" else d.candidates
            check(f"verify repick={repick} → {want_action}", d.action == want_action and got == want, str(d))
        clar = si.SemanticDecision("clarify", candidates=["a", "b"])
        check("verify leaves clarify untouched", si.verify_decision(msg, dict(prop), clar) is clar)
    finally:
        si.verify_metric = real  # type: ignore[assignment]


def adoption_cases() -> None:
    from pha.intent_gates import infer_wearable_metric_ids
    from pha.ledger_passthrough_lookup import _named_registry_metric_ids, resolve_turn_wearable_scope
    from pha.semantic_intent import adopted_metric_ids_for, reset_turn_adoption, set_turn_adoption

    msg = "我今天在阳光下待的时间是不是太短了？"
    before_named = _named_registry_metric_ids(msg)
    check("zero-entity baseline has no named ids", before_named == (), str(before_named))
    tok = set_turn_adoption(msg, ["time_in_daylight_min"])
    try:
        check("adoption visible for same message", adopted_metric_ids_for(f"  {msg} ") == ("time_in_daylight_min",))
        check("adoption keyed by message", adopted_metric_ids_for("别的问题") == ())
        check("infer_wearable_metric_ids uses adoption", "time_in_daylight_min" in infer_wearable_metric_ids(msg))
        check("named registry ids use adoption", "time_in_daylight_min" in _named_registry_metric_ids(msg))
        scope = resolve_turn_wearable_scope("default", msg)
        check(
            "turn wearable scope uses adoption",
            "time_in_daylight_min" in scope.registry_ids and not scope.fail_closed_named,
            str(scope),
        )
        named = "昨晚深睡多久"
        check("adoption does not leak into other messages", "time_in_daylight_min" not in infer_wearable_metric_ids(named))
    finally:
        reset_turn_adoption(tok)
    check("adoption cleared after reset", _named_registry_metric_ids(msg) == before_named)


def eligibility_cases() -> None:
    from pha.semantic_intent import needs_semantic_proposal, run_semantic_proposal

    prev = os.environ.get("PHA_SEMANTIC_INTENT")
    try:
        os.environ["PHA_SEMANTIC_INTENT"] = "off"
        check("mode off → no proposal", not needs_semantic_proposal("default", "我今天在阳光下待的时间是不是太短了？"))
        check("mode off → run_semantic_proposal None", run_semantic_proposal("default", "我今天在阳光下待的时间是不是太短了？") is None)
        os.environ["PHA_SEMANTIC_INTENT"] = "shadow"
        check("zero-entity → eligible", needs_semantic_proposal("default", "我今天在阳光下待的时间是不是太短了？"))
        check("named metric → not eligible", not needs_semantic_proposal("default", "昨晚深睡多久"))
        check("casual → not eligible", not needs_semantic_proposal("default", "你好"))
    finally:
        if prev is None:
            os.environ.pop("PHA_SEMANTIC_INTENT", None)
        else:
            os.environ["PHA_SEMANTIC_INTENT"] = prev


def clarify_cases() -> None:
    import pha.clarify_turns as ct
    from pha.semantic_intent import build_metric_pick_scope, metric_pick_from_scope, metric_pick_replay

    original = "上周运动后心跳恢复得怎么样"
    scope = build_metric_pick_scope(original, ["hrv_sdnn_ms", "resting_heart_rate_bpm"])
    ids = [c["id"] for c in scope.clarify_choices]
    check("metric_pick scope needs clarification", scope.needs_clarification and scope.clarify_kind == "metric_pick")
    check("metric_pick prompt from catalog", bool((scope.clarify_prompt or "").strip()))
    check(
        "metric_pick choices + none",
        ids == ["metric_pick:hrv_sdnn_ms", "metric_pick:resting_heart_rate_bpm", "metric_pick:none"],
        str(ids),
    )
    stored = ct.clarify_scope_from_storage_dict(ct.clarify_scope_storage_dict(scope))
    picked = ct.resolve_scope_from_clarify_choice("metric_pick:hrv_sdnn_ms", pending_scope=stored)
    check("chip resolves to semantic_pick", picked.metric_source == "semantic_pick" and not picked.needs_clarification)
    check("pick carries original message", metric_pick_from_scope(picked) == (original, "hrv_sdnn_ms"), str(metric_pick_from_scope(picked)))
    none_pick = ct.resolve_scope_from_clarify_choice("metric_pick:none", pending_scope=stored)
    check("none chip → empty metric", metric_pick_from_scope(none_pick) == (original, ""))

    prev_mode, prev_clar = os.environ.get("PHA_SEMANTIC_INTENT"), os.environ.get("PHA_CLARIFY_TURNS")
    orig_loader = ct.load_pending_clarify_scope
    try:
        ct.load_pending_clarify_scope = lambda _sid: stored  # type: ignore[assignment]
        os.environ["PHA_CLARIFY_TURNS"] = "1"
        os.environ["PHA_SEMANTIC_INTENT"] = "shadow"
        check("replay disabled outside mode on", metric_pick_replay("s", "metric_pick:hrv_sdnn_ms") is None)
        os.environ["PHA_SEMANTIC_INTENT"] = "on"
        check("replay restores original + metric", metric_pick_replay("s", "metric_pick:hrv_sdnn_ms") == (original, "hrv_sdnn_ms"))
        check("replay none → empty metric", metric_pick_replay("s", "metric_pick:none") == (original, ""))
        check("replay ignores non metric_pick chips", metric_pick_replay("s", "2024") is None)
        check("replay unknown choice → None", metric_pick_replay("s", "metric_pick:bogus") is None)
    finally:
        ct.load_pending_clarify_scope = orig_loader  # type: ignore[assignment]
        for key, val in (("PHA_SEMANTIC_INTENT", prev_mode), ("PHA_CLARIFY_TURNS", prev_clar)):
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def orchestrator_cases() -> None:
    """Full chat turn with a stubbed proposer + LLM on a temp DB."""
    import json
    import tempfile

    import pha.chat_turn_orchestrator as orch
    import pha.semantic_intent as si
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st
    from pha.chat_background import init_background_schema
    from pha.chat_storage import create_session, init_chat_schema, list_messages
    from pha.intent_gates import infer_wearable_metric_ids

    class _FakeProvider:
        def __init__(self, model: str = "selfcheck-model", **_kwargs):
            self.model = model

        def stream_chat_messages(self, *, messages):
            yield "按库内数据作答。"

        def chat_with_tools(self, *, messages, tools):
            return {"message": {"role": "assistant", "content": "按库内数据作答。"}}

    adopt_msg = "我今天在阳光下待的时间是不是太短了？"
    pick_msg = "上周运动后恢复得怎么样"
    fixtures = {
        adopt_msg: _prop("metric_query", ("time_in_daylight_min", "在阳光下待的时间")),
        pick_msg: _prop("metric_query", ("hrv_sdnn_ms", "运动后恢复"), ("cardio_recovery_1min_bpm", "运动后恢复")),
    }
    calls: list[str] = []
    plans: list[dict] = []
    real_plan = orch.build_turn_evidence_plan

    def _fake_propose(message, *, model=None):
        calls.append(message)
        return dict(fixtures.get(message) or _prop("other"), model="stub")

    def _spy_plan(msg, **kw):
        plan = real_plan(msg, **kw)
        plans.append({"msg": msg, "profile": plan.profile, "ids": list(infer_wearable_metric_ids(msg))})
        return plan

    def _events(**kw) -> list[dict]:
        out = []
        for raw in orch.orchestrate_chat_turn_events(user_id="selfcheck", model="selfcheck-model", response_locale="zh-CN", **kw):
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out

    tmp = Path(tempfile.mkdtemp(prefix="pha-sem-"))
    old_db = st.DEFAULT_DB_PATH
    episodic_flags = ("PHA_HEALTH_TURN_RESOLVER", "PHA_EPISODIC_ALL_PROFILES", "PHA_GOAL_CLASSIFIER", "PHA_GOAL_SESSION_ANCHOR")
    old_env = {k: os.environ.get(k) for k in ("PHA_SEMANTIC_INTENT", "PHA_CLARIFY_TURNS", *episodic_flags)}
    for key in episodic_flags:
        os.environ[key] = "1"
    old_tls = getattr(sc._thread_local, "conn", None)
    if old_tls is not None:
        try:
            old_tls.close()
        except Exception:
            pass
    st.DEFAULT_DB_PATH = tmp / "pha_storage.db"
    sc.reset_schema_state_for_tests()
    st.init_schema()
    init_chat_schema()
    init_background_schema()
    prev_provider, prev_propose, prev_verify = orch.OllamaProvider, si.propose, si.verify_metric
    orch.OllamaProvider = _FakeProvider  # type: ignore[misc, assignment]
    orch.build_turn_evidence_plan = _spy_plan  # type: ignore[assignment]
    si.propose = _fake_propose  # type: ignore[assignment]
    si.verify_metric = lambda _m, mid, _e, **_k: {"metric_id": mid, "latency_ms": 0}  # type: ignore[assignment]
    try:
        os.environ["PHA_CLARIFY_TURNS"] = "1"

        os.environ["PHA_SEMANTIC_INTENT"] = "off"
        sid = create_session("selfcheck").id
        _events(user_message=adopt_msg, session_id=sid)
        check("e2e off: proposer not called", not calls, str(calls))

        os.environ["PHA_SEMANTIC_INTENT"] = "shadow"
        plans.clear()
        _events(user_message=adopt_msg, session_id=sid)
        check("e2e shadow: proposer called", calls == [adopt_msg], str(calls))
        check(
            "e2e shadow: routing unchanged",
            bool(plans) and "time_in_daylight_min" not in plans[-1]["ids"],
            str(plans[-1:]),
        )

        os.environ["PHA_SEMANTIC_INTENT"] = "on"
        plans.clear()
        evs = _events(user_message=adopt_msg, session_id=sid)
        check(
            "e2e on adopt: wearable plan with adopted metric",
            bool(plans) and plans[-1]["profile"] == "wearable_only" and "time_in_daylight_min" in plans[-1]["ids"],
            str(plans[-1:]),
        )
        check("e2e on adopt: done emitted", any(e.get("event") == "done" for e in evs))
        check("e2e adoption reset after turn", "time_in_daylight_min" not in infer_wearable_metric_ids(adopt_msg))

        sid2 = create_session("selfcheck").id
        plans.clear()
        evs = _events(user_message=pick_msg, session_id=sid2)
        clar = [e for e in evs if e.get("event") == "clarify"]
        ids = [c.get("id") for c in (clar[0].get("choices") if clar else [])]
        check("e2e on clarify: metric_pick chips", bool(clar) and clar[0].get("kind") == "metric_pick", str(clar[:1]))
        check("e2e on clarify: no plan built", not plans, str(plans))
        check("e2e on clarify: chips list candidates", "metric_pick:hrv_sdnn_ms" in ids and "metric_pick:none" in ids, str(ids))

        calls.clear()
        plans.clear()
        evs = _events(user_message="心率变异性", session_id=sid2, clarify_choice_id="metric_pick:hrv_sdnn_ms")
        check("e2e pick: proposer not re-called", not calls, str(calls))
        check(
            "e2e pick: original message replayed with picked metric",
            bool(plans) and plans[-1]["msg"] == pick_msg and plans[-1]["profile"] == "wearable_only" and "hrv_sdnn_ms" in plans[-1]["ids"],
            str(plans[-1:]),
        )
        check("e2e pick: no second clarify", not any(e.get("event") == "clarify" for e in evs))
        users = [m.content for m in list_messages(sid2) if m.role == "user"]
        check("e2e pick: history stores chip label, not a repeated question", users == [pick_msg, "心率变异性"], str(users))

        sid3 = create_session("selfcheck").id
        _events(user_message="昨晚深睡多久", session_id=sid3)
        calls.clear()
        plans.clear()
        _events(user_message="那前天呢？", session_id=sid3)
        check("e2e follow-up with focus metric: proposer skipped", not calls, str(calls))
        check(
            "e2e follow-up with focus metric: wearable plan carries focus metric",
            bool(plans) and plans[-1]["profile"] == "wearable_only" and bool(plans[-1]["ids"]),
            str(plans[-1:]),
        )
        check("e2e focus metric reset after turn", not infer_wearable_metric_ids("那前天呢？"))

        os.environ["PHA_SEMANTIC_INTENT"] = "off"
        evs = _events(user_message="心率变异性", session_id=sid2, clarify_choice_id="metric_pick:hrv_sdnn_ms")
        check(
            "e2e stale metric_pick chip with mode off → plain turn, no error",
            any(e.get("event") == "done" for e in evs) and not any(e.get("event") == "error" for e in evs),
            str([e.get("event") for e in evs]),
        )
    finally:
        orch.OllamaProvider = prev_provider  # type: ignore[misc]
        orch.build_turn_evidence_plan = real_plan  # type: ignore[assignment]
        si.propose = prev_propose  # type: ignore[assignment]
        si.verify_metric = prev_verify  # type: ignore[assignment]
        st.DEFAULT_DB_PATH = old_db
        sc.reset_schema_state_for_tests()
        for key, val in old_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def main() -> int:
    gate_cases()
    verify_cases()
    adoption_cases()
    eligibility_cases()
    clarify_cases()
    orchestrator_cases()
    print(f"\n{'OK' if not FAILS else 'FAILED'} — {len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
