#!/usr/bin/env python3
"""C7 chat golden conversations — JSON-driven dialogue quality regression."""

import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import compose_grounded_reply, finalize_turn_with_composer
from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.chat_turn_service import ChatTurnRequest, resolve_chat_turn
from tax_agent.fx_rates import FxRateProvider
from tax_agent.session_context import SessionContext
from tax_agent.tax_guided_session import clear_tax_guided_session, get_tax_guided_session
from tax_agent.policy_kb import retrieve_top_cards
from tax_agent.tax_provenance import try_provenance_fast_turn

EVALS_DIR = ROOT / "evals" / "chat_golden_conversations"
SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"
FIXTURE_ANNUAL = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
FIXTURE_INCOME = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"

_FIXTURE_CACHE: dict[str, tuple[dict[str, Any], list[Any], dict[str, str]]] = {}


def _load_fixture(name: str) -> Optional[tuple[dict[str, Any], list[Any], dict[str, str]]]:
    if name in _FIXTURE_CACHE:
        return _FIXTURE_CACHE[name]
    if name != "futu_2022_classified":
        return None
    if not FIXTURE_ANNUAL.is_file() or not FIXTURE_INCOME.is_file():
        return None
    from tax_agent.futu_session_fifo import finalize_futu_session_dataset
    from tax_agent.parser.broker_parser import BrokerParser

    events_all: list[Any] = []
    pkgs: list[dict[str, Any]] = []
    for path in (FIXTURE_ANNUAL, FIXTURE_INCOME):
        pr = BrokerParser(template_id="broker_futu_v1").parse_path(path)
        pkg = (pr.data_quality or {}).get("futuTaxPackage")
        if pkg:
            pkgs.append(pkg)
        events_all.extend(pr.events)
    dq = {"futuTaxPackages": pkgs}
    events, _ = finalize_futu_session_dataset(events_all, dq)
    last_summary: dict[str, str] = {}
    _FIXTURE_CACHE[name] = (dq, events, last_summary)
    return dq, events, last_summary


def _mock_narrate(kind: str):
    def _fn(bundle, **kwargs):
        if kind == "timeout":
            return None, "timeout"
        if kind == "bad_numerics":
            return "2022年汇率是 9.9999，依据某虚构公告。", ""
        year = bundle.tax_year or 2022
        rate = (bundle.facts or {}).get("rate") or "6.3757"
        return (
            f"{year}年补缴汇率是{rate}，依据【个人所得税法实施条例第三十二条】。",
            "",
        )

    return _fn


def _assert_expect(
    label: str,
    reply: str,
    meta: dict[str, Any],
    expect: dict[str, Any],
    *,
    message: str = "",
) -> None:
    for token in expect.get("reply_contains") or []:
        assert token in reply, f"{label}: missing {token!r} in {reply[:120]!r}"
    for token in expect.get("reply_not_contains") or []:
        assert token not in reply, f"{label}: forbidden {token!r} in reply"
    prefix = expect.get("reply_starts_with")
    if prefix:
        assert reply.startswith(prefix), f"{label}: expected start {prefix!r}"
    if "profile" in expect:
        assert meta.get("profile") == expect["profile"], (label, meta.get("profile"))
    fb = expect.get("composer_fallback")
    if fb is not None:
        composer = (meta.get("composer") or {})
        assert composer.get("fallbackReason") == fb, (label, composer)
    if "narrated" in expect:
        composer = meta.get("composer") or {}
        assert composer.get("narrated") is expect["narrated"], (label, composer)
    if expect.get("guided_active") is not None:
        sid = meta.get("session_id")
        gs = get_tax_guided_session(sid) if sid else None
        active = bool(gs and gs.wizard_active)
        assert active == expect["guided_active"], (label, active)
    card_id = expect.get("card_id")
    if card_id and message:
        cards = retrieve_top_cards(message)
        assert cards and cards[0].id == card_id, (label, message, [c.id for c in cards])
    follow_ups = expect.get("follow_ups_count")
    if follow_ups is not None:
        # C1-4: followUps 须为 3 条可发送文本（由 resolve 路径写入 llm_meta）
        fu = meta.get("follow_ups") or []
        assert len(fu) == follow_ups, (label, fu)
        for item in fu:
            assert isinstance(item, str) and item.strip(), (label, fu)


def _run_turn(
    turn: dict[str, Any],
    *,
    session_id: str,
    provider: FxRateProvider,
) -> tuple[str, dict[str, Any]]:
    mock = turn.get("mock_narrate")
    if mock in ("timeout", "bad_numerics", "good"):
        bundle_turn = try_provenance_fast_turn(
            turn["message"],
            SessionContext(
                session_id=session_id,
                dataset_id=turn.get("dataset_id"),
                tax_year=2025,
                fx_policy="cn_supplemental",
                fx_provider=provider,
                data_quality=turn.get("data_quality"),
            ),
        )
        assert bundle_turn and bundle_turn.fact_bundle
        composed = compose_grounded_reply(
            bundle_turn.fact_bundle,
            user_message=turn["message"],
            llm_on=True,
            narrate_fn=_mock_narrate(mock),
        )
        meta = {
            "profile": bundle_turn.fact_bundle.profile,
            "session_id": session_id,
            "composer": {
                "narrated": composed.narrated,
                "fallbackReason": composed.fallback_reason or "none",
            },
        }
        return composed.reply, meta

    req = ChatTurnRequest(
        session_id=session_id,
        message=turn["message"],
        dataset_id=turn.get("dataset_id"),
        tax_year=2025,
        llm_model=turn.get("llm_model", "__off__"),
    )
    data_quality = turn.get("data_quality")
    events: list[Any] | None = None
    last_summary = turn.get("last_summary")
    fixture = turn.get("fixture")
    if fixture:
        loaded = _load_fixture(fixture)
        if not loaded:
            print(f"SKIP turn (fixture {fixture!r} unavailable)")
            return "", {"profile": None, "session_id": session_id, "composer": {}, "skipped": True}
        data_quality, events, last_summary = loaded
    ctx = SessionContext(
        session_id=session_id,
        dataset_id=turn.get("dataset_id"),
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
        data_quality=data_quality,
        events=events,
        last_summary=last_summary,
    )
    outcome = resolve_chat_turn(req, ctx, apply_composer=True)
    composer = (outcome.llm_meta.get("runtime") or {}).get("composer") or {}
    bundle = outcome.turn.fact_bundle if outcome.turn else None
    if not composer and bundle:
        _, comp_meta = finalize_turn_with_composer(
            ChatTurnResult(
                reply=outcome.reply,
                action=outcome.action,
                fact_bundle=bundle,
                follow_ups=outcome.follow_ups,
            ),
            user_message=turn["message"],
            llm_on=req.llm_model != "__off__",
        )
        composer = comp_meta.get("composer") or {}
    meta = {
        "profile": (outcome.plan.profile if outcome.plan else None)
        or (outcome.harness or {}).get("profile"),
        "session_id": session_id,
        "composer": composer,
        "follow_ups": outcome.follow_ups or outcome.llm_meta.get("followUps"),
    }
    return outcome.reply, meta


def _run_case(case: dict[str, Any], provider: FxRateProvider) -> None:
    case_id = case["id"]
    session_id = case.get("session_id") or f"c7-{case_id}"
    clear_tax_guided_session(session_id)
    for idx, turn in enumerate(case.get("turns") or []):
        sid = turn.get("session_id") or session_id
        reply, meta = _run_turn(turn, session_id=sid, provider=provider)
        if meta.get("skipped"):
            print(f"SKIP {case_id}#{idx} (fixture missing)")
            continue
        _assert_expect(
            f"{case_id}#{idx}",
            reply,
            meta,
            turn.get("expect") or {},
            message=turn.get("message") or "",
        )
    print(f"PASS {case_id}")


def main() -> int:
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    assert provider
    files = sorted(EVALS_DIR.glob("*.json"))
    assert files, f"no JSON in {EVALS_DIR}"
    count = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for case in data.get("cases") or []:
            _run_case(case, provider)
            count += 1
    print(f"PASS C7 golden conversations ({count} cases from {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
