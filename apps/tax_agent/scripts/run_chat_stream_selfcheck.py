#!/usr/bin/env python3
"""SSE /tax/chat/stream selfcheck (Tax Chat Experience v2 · C3)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import stream_compose_grounded_reply
from tax_agent.chat_sse import iter_chat_sse_events, sse_format
from tax_agent.chat_turn_service import ChatTurnRequest, resolve_chat_turn
from tax_agent.fx_rates import FxRateProvider
from tax_agent.session_context import SessionContext

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _parse_sse(chunks: list[str]) -> list[tuple[str, dict]]:
    text = "".join(chunks)
    out: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        ev = "message"
        data = ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                ev = line[7:].strip()
            if line.startswith("data: "):
                data = line[6:]
        if data:
            out.append((ev, json.loads(data)))
    return out


def _mock_stream(bundle, **kwargs):
    rate = bundle.facts.get("rate") if isinstance(bundle.facts, dict) else "6.3757"
    year = bundle.tax_year or 2022
    yield f"{year}年补缴汇率是{rate}，依据【个人所得税法实施条例第三十二条】。"
    return


def main() -> int:
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    ctx = SessionContext(
        dataset_id=None,
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    req = ChatTurnRequest(
        session_id="sse-selfcheck",
        message="22年的补申报的汇率是如何确定的",
        tax_year=2025,
        llm_model="__off__",
    )

    events = list(
        iter_chat_sse_events(
            req,
            ctx,
            turn_focus_payload=lambda _s: {},
        )
    )
    parsed = _parse_sse(events)
    names = [e[0] for e in parsed]
    assert names[0] == "meta", names
    assert "fact_card" in names, names
    assert "done" in names, names
    assert "delta" not in names, "LLM off should skip deltas"
    done = next(d for e, d in parsed if e == "done")
    assert "6.3757" in done["reply"]
    print("PASS C3-2 LLM off: meta → fact_card → done")

    req2 = ChatTurnRequest(
        session_id="sse-selfcheck-2",
        message="22年的补申报的汇率是如何确定的",
        tax_year=2025,
        llm_model="auto",
    )
    events2 = list(
        iter_chat_sse_events(
            req2,
            ctx,
            turn_focus_payload=lambda _s: {},
            stream_fn=_mock_stream,
        )
    )
    parsed2 = _parse_sse(events2)
    names2 = [e[0] for e in parsed2]
    assert names2.index("meta") < names2.index("fact_card") < names2.index("delta") < names2.index("done")
    assert "follow_ups" in names2
    print("PASS C3-1 event order meta → fact_card → delta → follow_ups → done")

    outcome = resolve_chat_turn(req, ctx, apply_composer=True)
    assert "6.3757" in outcome.reply
    print("PASS C3-3 POST sync path unchanged")

    assert sse_format("meta", {"ok": True}).startswith("event: meta")
    print("PASS sse_format")

    annual = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
    income = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"
    if annual.is_file() and income.is_file():
        from tax_agent.answer_composer import fact_bundle_fact_card
        from tax_agent.futu_session_fifo import finalize_futu_session_dataset
        from tax_agent.parser.broker_parser import BrokerParser

        events_all: list = []
        pkgs: list = []
        for p in (annual, income):
            pr = BrokerParser(template_id="broker_futu_v1").parse_path(p)
            pkg = (pr.data_quality or {}).get("futuTaxPackage")
            if pkg:
                pkgs.append(pkg)
            events_all.extend(pr.events)
        dq = {"futuTaxPackages": pkgs}
        events, _ = finalize_futu_session_dataset(events_all, dq)
        ctx3 = SessionContext(
            session_id="sse-classified",
            dataset_id="sse-ds",
            tax_year=2025,
            fx_policy="cn_supplemental",
            fx_provider=provider,
            data_quality=dq,
            events=events,
            last_summary={"taxableIncomeCny": "1056.77", "netTaxDueCny": "96.08"},
        )
        req3 = ChatTurnRequest(
            session_id="sse-classified",
            message="2022年股息利息一共多少",
            dataset_id="sse-ds",
            tax_year=2025,
            llm_model="__off__",
        )
        events3 = list(
            iter_chat_sse_events(
                req3,
                ctx3,
                turn_focus_payload=lambda _s: {},
            )
        )
        parsed3 = _parse_sse(events3)
        fc = next(d for e, d in parsed3 if e == "fact_card")
        assert fc.get("profile") == "insight_fast", fc
        hl = fc.get("highlights") or []
        assert any(h.get("label") == "股息应补" for h in hl), hl
        done3 = next(d for e, d in parsed3 if e == "done")
        assert "38.38" in done3["reply"] and "股息" in done3["reply"]
        card = fact_bundle_fact_card(
            __import__("tax_agent.fact_bundle", fromlist=["build_insight_fact_bundle"]).build_insight_fact_bundle(
                __import__("tax_agent.tax_insight", fromlist=["build_tax_insight"]).build_tax_insight(
                    focus="classified_income",
                    tax_year=2022,
                    data_quality=dq,
                    events=events,
                    last_summary={"netTaxDueCny": "96.08"},
                    fx_provider=provider,
                ),
                fallback_markdown="",
            )
        )
        assert card.get("highlights"), card
        print("PASS C3-4 classified income fact_card + SSE")
    else:
        print("SKIP C3-4 classified income (fixtures missing)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
