#!/usr/bin/env python3
"""Stage 4-β CHB compiler selfcheck — §Facts deterministic + 4-β-2a/b harness hooks."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.chb_compiler import (  # noqa: E402
    CHB_SCHEMA,
    INTERPRETATION_ADVISORY_BANNER,
    ChbFactRow,
    USER_CONTEXT_BRIEF_PROFILES,
    assemble_facts_section,
    build_user_context_brief_block,
    chb_compiler_enabled,
    chb_stale_status,
    compile_chronic_health_brief,
    compile_interpretation_stub,
    compute_ledger_hash,
    compute_live_ledger_hash,
    load_latest_chb_artifact,
    load_slot_candidates,
    recompile_chb_if_stale,
    write_chb_artifact,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_facts_section_has_refs() -> None:
    facts = [
        ChbFactRow(
            text="LDL 2025-12-07: 2.45 mmol/L",
            ref_id="lab_2025-12-07_ldl",
            prov_type="lab_report",
            metric_id="ldl",
            value="2.45",
            unit="mmol/L",
            observed_at="2025-12-07",
        ),
    ]
    md = assemble_facts_section(facts)
    _assert("§Facts" in md, md)
    _assert("[ref: lab_2025-12-07_ldl]" in md, md)


def test_ledger_hash_stable() -> None:
    facts = [
        ChbFactRow(text="x", ref_id="r1", prov_type="wearable_import"),
        ChbFactRow(text="y", ref_id="r2", prov_type="wearable_import"),
    ]
    h1 = compute_ledger_hash(facts)
    h2 = compute_ledger_hash(facts)
    _assert(h1 == h2, "hash must be stable")
    _assert(len(h1) == 16, h1)


def test_slot_candidates_loaded() -> None:
    slots = load_slot_candidates()
    _assert(len(slots) >= 2, slots)
    kinds = {s.get("kind") for s in slots}
    _assert("time" in kinds and "aggregation" in kinds, kinds)


def test_compile_brief_structure() -> None:
    brief = compile_chronic_health_brief("default")
    _assert(brief.schema == CHB_SCHEMA, brief.schema)
    _assert(brief.user_id == "default", brief.user_id)
    _assert(brief.ledger_hash, "ledger_hash required")
    _assert("§Facts" in brief.facts_markdown, brief.facts_markdown)
    _assert("§Interpretation" in brief.interpretation_markdown, brief.interpretation_markdown)
    for f in brief.facts:
        _assert(f.ref_id and f.prov_type, f.as_dict())
        _assert("[ref:" in brief.facts_markdown or not brief.facts, brief.facts_markdown)


def test_interpretation_stub_only() -> None:
    brief = compile_chronic_health_brief("default")
    _assert("§Interpretation" in brief.interpretation_markdown, brief.interpretation_markdown)
    _assert(
        "derived_from" in json.dumps(brief.interpretation, ensure_ascii=False) or not brief.interpretation,
        brief.interpretation,
    )


def test_chb_compiler_default_off() -> None:
    prev = os.environ.pop("PHA_CHB_COMPILER", None)
    try:
        _assert(not chb_compiler_enabled(), "PHA_CHB_COMPILER must default off")
    finally:
        if prev is not None:
            os.environ["PHA_CHB_COMPILER"] = prev


def test_interpretation_mock_llm_advisory_only() -> None:
    """Mock LLM path — no network; §Interpretation is advisory, not numerics source."""
    facts = [
        ChbFactRow(
            text="近 90d 睡眠 均值: 7.2 h",
            ref_id="wearable_90d_sleep",
            prov_type="wearable_import",
            metric_id="sleep",
            value="7.2",
            unit="h",
        ),
    ]
    facts_md = assemble_facts_section(facts)

    def _mock_llm(_fm: str) -> str:
        return "睡眠均值趋势平稳（mock advisory，非数字源）。"

    prev = os.environ.get("PHA_CHB_COMPILER")
    os.environ["PHA_CHB_COMPILER"] = "1"
    try:
        items, md = compile_interpretation_stub(
            facts,
            enable_llm=True,
            facts_markdown=facts_md,
            llm_fn=_mock_llm,
        )
        _assert(items and items[0].get("prov_type") == "llm_advisory", items)
        _assert(INTERPRETATION_ADVISORY_BANNER in md, md)
        _assert("mock advisory" in md, md)
        _assert("7.2" not in items[0].get("text", ""), "interpretation must not invent numerics")
    finally:
        if prev is None:
            os.environ.pop("PHA_CHB_COMPILER", None)
        else:
            os.environ["PHA_CHB_COMPILER"] = prev


def test_user_context_brief_profiles() -> None:
    _assert("lifestyle" in USER_CONTEXT_BRIEF_PROFILES, USER_CONTEXT_BRIEF_PROFILES)
    _assert("combined_review" in USER_CONTEXT_BRIEF_PROFILES, USER_CONTEXT_BRIEF_PROFILES)
    _assert("wearable_only" in USER_CONTEXT_BRIEF_PROFILES, USER_CONTEXT_BRIEF_PROFILES)
    _assert("attachment_grounded_review" not in USER_CONTEXT_BRIEF_PROFILES, USER_CONTEXT_BRIEF_PROFILES)
    _assert("fact_card_interpret" not in USER_CONTEXT_BRIEF_PROFILES, USER_CONTEXT_BRIEF_PROFILES)
    from pha.chb_compiler import user_context_brief_sections

    _assert(user_context_brief_sections("wearable_only") == ("background",), user_context_brief_sections("wearable_only"))
    _assert("facts" in user_context_brief_sections("lifestyle"), user_context_brief_sections("lifestyle"))


def test_user_context_brief_block_from_artifact() -> None:
    brief = compile_chronic_health_brief("default")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_chb_artifact(brief, report_root=root)
        block = build_user_context_brief_block("default", profile="lifestyle", report_root=root)
        _assert("USER_CONTEXT_BRIEF" in block, block)
        _assert("§Facts" in block, block)
        loaded = load_latest_chb_artifact("default", report_root=root)
        _assert(loaded is not None and loaded.ledger_hash == brief.ledger_hash, loaded)


def test_user_context_brief_empty_without_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        block = build_user_context_brief_block("no_such_user", profile="lifestyle", report_root=Path(td))
        _assert(block == "", f"expected empty block, got: {block!r}")


def test_lineage_window_stub_regex_compiles() -> None:
    """Inline (?i) mid-pattern crashes CPython 3.11+ and SSE'd HTTP 0 on chat."""
    from pha.chb_compiler import _is_lineage_field_stub

    _assert(_is_lineage_field_stub("近12个月均值", locale="zh-CN"), "cn window stub")
    _assert(_is_lineage_field_stub("rolling mean", locale="en"), "en mean stub")
    _assert(
        not _is_lineage_field_stub("晚间补剂与作息相关", locale="zh-CN"),
        "caution sentence is not a field stub",
    )


def test_wearable_supplement_brief_mount() -> None:
    from pha.harness_plan import build_turn_evidence_plan

    plain = build_turn_evidence_plan("我最近的 HRV 怎么样？")
    _assert(plain.profile == "wearable_only", plain.profile)
    _assert("USER_CONTEXT_BRIEF" not in plain.slots_tier1, plain.slots_tier1)
    mixed = build_turn_evidence_plan(
        "今天是9月11号，昨天是9月10号，请对比我的这两天的HRV，"
        "同时请说出我正在服用的哪些补剂是对HRV有改善作用的。"
    )
    _assert(mixed.profile == "wearable_only", mixed.profile)
    _assert("USER_CONTEXT_BRIEF" in mixed.slots_tier1, mixed.slots_tier1)
    _assert("SUPPLEMENT_BG" not in mixed.slots_tier0 + mixed.slots_tier1, mixed)


def test_user_context_brief_forbidden_on_grounded() -> None:
    brief = compile_chronic_health_brief("default")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_chb_artifact(brief, report_root=root)
        block = build_user_context_brief_block(
            "default",
            profile="attachment_grounded_review",
            report_root=root,
        )
        _assert(block == "", "attachment_grounded_review must not inject USER_CONTEXT_BRIEF")


def test_write_artifact() -> None:
    brief = compile_chronic_health_brief("default")
    with tempfile.TemporaryDirectory() as td:
        path = write_chb_artifact(brief, report_root=Path(td))
        _assert(path.is_file(), str(path))
        doc = json.loads(path.read_text(encoding="utf-8"))
        _assert(doc.get("schema") == CHB_SCHEMA, doc)
        _assert(doc.get("slot_hints"), "slot hints from loop_slot_candidates.jsonl")


def test_chb_stale_detection() -> None:
    """4-β-2c: live T0 hash vs on-disk artifact."""
    live = compute_live_ledger_hash("default")
    _assert(live and len(live) == 16, live)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        status = chb_stale_status("default", report_root=root)
        _assert(status["is_stale"], "missing artifact must be stale")
        _assert(status["live_hash"] == live, status)

        brief = compile_chronic_health_brief("default")
        write_chb_artifact(brief, report_root=root)
        status = chb_stale_status("default", report_root=root)
        _assert(not status["is_stale"], status)
        _assert(status["artifact_hash"] == live, status)

        stale_doc = {
            "schema": CHB_SCHEMA,
            "user_id": "default",
            "compiled_at": "2099-01-01T00:00:00+00:00",
            "ledger_hash": "deadbeefdeadbeef",
            "facts": [],
            "interpretation": [],
            "open_questions": [],
            "slot_hints": [],
            "facts_markdown": "",
            "interpretation_markdown": "",
        }
        stale_path = root / "default" / "brief_deadbeefdeadbeef.json"
        stale_path.write_text(json.dumps(stale_doc) + "\n", encoding="utf-8")
        status = chb_stale_status("default", report_root=root)
        _assert(status["is_stale"], "wrong ledger_hash in newest artifact must be stale")


def test_recompile_if_stale_dry_run_and_write() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        status, path = recompile_chb_if_stale("default", report_root=root, dry_run=True)
        _assert(status["is_stale"], status)
        _assert(path is None, "dry-run must not write")

        status, path = recompile_chb_if_stale("default", report_root=root)
        _assert(path is not None and path.is_file(), path)
        _assert(not status["is_stale"], status)

        status2, path2 = recompile_chb_if_stale("default", report_root=root)
        _assert(path2 is None, "fresh artifact must skip recompile")
        _assert(not status2["is_stale"], status2)
        _assert(status2["artifact_count"] >= 1, status2)


def test_p15_background_lineage_projection_autocompile() -> None:
    """M1-P15: §Background, combo stale, interpret projection, lineage freq, same-day once."""
    import pha.sqlite_connection as sc
    import pha.sqlite_storage as st
    from datetime import datetime, timezone

    from pha.chat_background import init_background_schema
    from pha.chat_storage import init_chat_schema
    from pha.chb_compiler import (
        assemble_lineage_section,
        maybe_autocompile_chb,
        project_chb_for_fact_card_interpret,
    )
    from pha.fact_card_background_brief import build_fact_card_background_brief
    from pha.numerics_manifest import leftover_s_level_numeric_tokens

    tmp = Path(tempfile.mkdtemp(prefix="pha-p15-"))
    db = tmp / "pha_storage.db"
    report_root = tmp / "chb"
    interpret_root = tmp / "interpret"
    interpret_root.mkdir()
    old_db = st.DEFAULT_DB_PATH
    old_interp = os.environ.get("PHA_FACT_CARD_INTERPRET_DIR")
    old_chb = os.environ.get("PHA_CHB_REPORT_ROOT")
    old_auto = os.environ.get("PHA_CHB_AUTOCOMPILE")
    os.environ["PHA_FACT_CARD_INTERPRET_DIR"] = str(interpret_root)
    os.environ["PHA_CHB_REPORT_ROOT"] = str(report_root)
    os.environ["PHA_CHB_AUTOCOMPILE"] = "1"
    st.DEFAULT_DB_PATH = db
    old_tls = getattr(sc._thread_local, "conn", None)
    if old_tls is not None:
        try:
            old_tls.close()
        except Exception:
            pass
    sc.reset_schema_state_for_tests()
    st.init_schema()
    init_chat_schema()
    init_background_schema()
    uid = "selfcheck-p15"

    def _restore() -> None:
        st.DEFAULT_DB_PATH = old_db
        if old_interp is None:
            os.environ.pop("PHA_FACT_CARD_INTERPRET_DIR", None)
        else:
            os.environ["PHA_FACT_CARD_INTERPRET_DIR"] = old_interp
        if old_chb is None:
            os.environ.pop("PHA_CHB_REPORT_ROOT", None)
        else:
            os.environ["PHA_CHB_REPORT_ROOT"] = old_chb
        if old_auto is None:
            os.environ.pop("PHA_CHB_AUTOCOMPILE", None)
        else:
            os.environ["PHA_CHB_AUTOCOMPILE"] = old_auto
        sc.reset_schema_state_for_tests()

    def _insert(content: str, category: str = "supplement") -> None:
        conn = st._connect()
        try:
            conn.execute(
                "INSERT INTO user_health_background_notes "
                "(user_id, note_date, category, content) VALUES (?, ?, ?, ?)",
                (uid, "2026-09-05", category, content),
            )
            conn.commit()
        finally:
            conn.close()

    try:
        _insert("每晚补剂项B 400mg，我在吃药物项A类")
        live_text, live_meta = build_fact_card_background_brief(
            uid, locale="zh-CN", prefer_chb=True
        )
        _assert(live_meta.get("brief_source") == "live_notes", live_meta)
        _assert("药物项A" in live_text, live_text)
        _assert("400" not in live_text, live_text)

        brief = compile_chronic_health_brief(uid)
        _assert("§Background" in brief.background_markdown, brief.background_markdown)
        leftover = leftover_s_level_numeric_tokens(brief.background_markdown)
        _assert(not leftover, leftover)
        _assert("§Facts" not in (brief.background_markdown or ""), brief.background_markdown)
        proj = project_chb_for_fact_card_interpret(brief)
        _assert("§Facts" not in proj, proj)
        _assert("药物项A" in proj, proj)
        _assert("无关则忽略" not in proj, proj)
        _assert("本槽在场" in proj, proj)
        _assert(brief.background_rows, brief)
        for stmt in brief.background_rows:
            _assert(stmt.get("prov_type") == "user_statement", stmt)
            _assert("value" not in stmt and "unit" not in stmt and "metric_id" not in stmt, stmt)
            leftover_row = leftover_s_level_numeric_tokens(str(stmt.get("text") or ""))
            _assert(not leftover_row, leftover_row)
        _assert("400" not in json.dumps(brief.background_rows, ensure_ascii=False), brief.background_rows)
        lifestyle = build_user_context_brief_block(uid, profile="lifestyle")
        write_chb_artifact(brief, report_root=report_root)
        lifestyle = build_user_context_brief_block(
            uid, profile="lifestyle", report_root=report_root
        )
        _assert("§Facts" in lifestyle, lifestyle)
        _assert("§Background" in lifestyle, lifestyle)
        _assert("药物项A" in lifestyle, lifestyle)
        wearable_brief = build_user_context_brief_block(
            uid, profile="wearable_only", report_root=report_root
        )
        _assert("§Facts" not in wearable_brief, wearable_brief)
        _assert("§Background" in wearable_brief, wearable_brief)
        _assert("药物项A" in wearable_brief, wearable_brief)
        _assert("无关则忽略" not in lifestyle, lifestyle)
        _assert("fact_card_interpret" not in USER_CONTEXT_BRIEF_PROFILES, USER_CONTEXT_BRIEF_PROFILES)
        interp_proj = project_chb_for_fact_card_interpret(
            load_latest_chb_artifact(uid, report_root=report_root)  # type: ignore[arg-type]
        )
        _assert("§Facts" not in interp_proj, interp_proj)

        status = chb_stale_status(uid, report_root=report_root)
        _assert(not status["is_stale"], status)
        chb_text, chb_meta = build_fact_card_background_brief(
            uid, locale="zh-CN", prefer_chb=True
        )
        _assert(chb_meta.get("brief_source") == "chb", chb_meta)
        _assert("药物项A" in chb_text, chb_text)

        _insert("最近睡眠都偏晚而且容易醒")
        status = chb_stale_status(uid, report_root=report_root)
        _assert(status["is_stale"], status)
        status, path = recompile_chb_if_stale(uid, report_root=report_root)
        _assert(path is not None and path.is_file(), path)
        _assert(not status["is_stale"], status)

        now = datetime.now(timezone.utc).isoformat()
        repeated = "力量训练当天建议偏轻松安排，注意恢复。"
        once = "这句注意事项只出现一次所以不进脉络。"
        other = "完全不同的第三句注意事项足够长。"
        table = "今日值：32.6 ms。百分位：15.2 pct。近12个月均值：32.3。"
        for name, text in (
            ("a", repeated + once),
            ("b", repeated),
            ("c", other),
            ("d", table),
            ("e", table),
        ):
            (interpret_root / f"{name}.json").write_text(
                json.dumps(
                    {
                        "status": "done",
                        "user_id": uid,
                        "generated_at": now,
                        "numerics_audit": {"passed": True},
                        "text": text,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        lin_md, _digest = assemble_lineage_section(
            uid, interpret_root=interpret_root, locale="zh-CN"
        )
        _assert("偏轻松" in lin_md, lin_md)
        _assert("只出现一次" not in lin_md, lin_md)
        _assert("今日值" not in lin_md, lin_md)
        _assert("百分位" not in lin_md, lin_md)
        _assert("均值" not in lin_md, lin_md)

        first = maybe_autocompile_chb(uid, report_root=report_root, now=date(2026, 9, 10))
        second = maybe_autocompile_chb(uid, report_root=report_root, now=date(2026, 9, 10))
        _assert(second.get("skipped") == "same_day", (first, second))
    finally:
        _restore()


def main() -> int:
    test_facts_section_has_refs()
    print("PASS §Facts ref markers")
    test_ledger_hash_stable()
    print("PASS ledger hash stable")
    test_slot_candidates_loaded()
    print("PASS slot candidates loaded")
    test_compile_brief_structure()
    print("PASS compile brief structure")
    test_interpretation_stub_only()
    print("PASS interpretation stub")
    test_chb_compiler_default_off()
    print("PASS PHA_CHB_COMPILER default off")
    test_interpretation_mock_llm_advisory_only()
    print("PASS mock LLM interpretation (advisory only)")
    test_user_context_brief_profiles()
    print("PASS USER_CONTEXT_BRIEF profile gate")
    test_user_context_brief_block_from_artifact()
    print("PASS USER_CONTEXT_BRIEF block from artifact")
    test_user_context_brief_empty_without_artifact()
    print("PASS USER_CONTEXT_BRIEF empty without artifact")
    test_user_context_brief_forbidden_on_grounded()
    print("PASS USER_CONTEXT_BRIEF forbidden on grounded")
    test_lineage_window_stub_regex_compiles()
    print("PASS lineage window stub regex compiles on 3.11+")
    test_wearable_supplement_brief_mount()
    print("PASS wearable_only mounts USER_CONTEXT_BRIEF on schema positive score")
    test_write_artifact()
    print("PASS write artifact")
    test_chb_stale_detection()
    print("PASS CHB stale detection (4-β-2c)")
    test_recompile_if_stale_dry_run_and_write()
    print("PASS recompile_if_stale dry-run + write")
    test_p15_background_lineage_projection_autocompile()
    print("PASS P15 background + lineage + projection + same-day compile")
    print("OK pha_chb_compiler_selfcheck (Stage 4-β-2a/b/c + M1-P15)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
