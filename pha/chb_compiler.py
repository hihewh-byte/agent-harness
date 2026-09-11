"""Stage 4-β — Chronic Health Brief (CHB) compiler.

Deterministic §Facts assembly from T0 ledger rows; §Interpretation is optional
and feature-flagged (default off).

4-β-2a: Harness Tier1 slot ``USER_CONTEXT_BRIEF`` (lifestyle / combined only).
4-β-2b: LLM §Interpretation via ``PHA_CHB_COMPILER=1`` (BYOK / mockable).

RIGID RED LINE: §Interpretation is advisory text only. It MUST NEVER be used as a
numerics / Manifest / LabelLedger source for control flow or dose math.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import statistics
import threading
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from pha.health_data import effective_query_reference_date
from pha.medical_storage import MedicalMetricRow, get_latest_medical_report, query_metrics_in_range
from pha.sqlite_storage import query_wearable_daily_range

logger = logging.getLogger(__name__)

CHB_SCHEMA = "pha.chb/v0.1"
DEFAULT_LOOKBACK_DAYS = 90
DEFAULT_REPORT_ROOT = Path(__file__).resolve().parent.parent / "reports" / "chb"
SLOT_CANDIDATES_PATH = Path(__file__).resolve().parent.parent / "rules" / "loop_slot_candidates.jsonl"

# Projection slices per harness profile (registry contract; not session ifs).
_CONTEXT_BRIEF_SECTIONS: dict[str, tuple[str, ...]] = {
    "lifestyle": ("facts", "background", "interpretation", "open_questions"),
    "combined_review": ("facts", "background", "interpretation", "open_questions"),
    "wearable_only": ("background",),
}
USER_CONTEXT_BRIEF_PROFILES: frozenset[str] = frozenset(_CONTEXT_BRIEF_SECTIONS)


def user_context_brief_sections(profile: str) -> tuple[str, ...]:
    return _CONTEXT_BRIEF_SECTIONS.get((profile or "").strip(), ())


def resolve_report_root(report_root: Path | None = None) -> Path:
    if report_root is not None:
        return Path(report_root)
    override = (os.environ.get("PHA_CHB_REPORT_ROOT") or "").strip()
    if override:
        return Path(override)
    return DEFAULT_REPORT_ROOT


INTERPRETATION_ADVISORY_BANNER = (
    "## §Interpretation（解读 · 非数字源 · ADVISORY ONLY）\n"
    "> 本栏仅为健康参考建议，**禁止**作为 Numerics Manifest / LabelLedger / "
    "剂量或控制流的数字来源。数字主权仅属于 §Facts（T0）。"
)

# Callable: facts_markdown -> interpretation body text (no header).
InterpretationLlmFn = Callable[[str], str]


@dataclass
class ChbFactRow:
    text: str
    ref_id: str
    prov_type: str  # lab_report | wearable_import | user_statement | attachment_ingest
    metric_id: str | None = None
    value: str | None = None
    unit: str | None = None
    observed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChronicHealthBrief:
    schema: str = CHB_SCHEMA
    user_id: str = "default"
    compiled_at: str = ""
    ledger_hash: str = ""
    input_hash: str = ""
    background_hash: str = ""
    lineage_hash: str = ""
    facts: list[ChbFactRow] = field(default_factory=list)
    interpretation: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    slot_hints: list[dict[str, Any]] = field(default_factory=list)
    facts_markdown: str = ""
    interpretation_markdown: str = ""
    background_markdown: str = ""
    lineage_markdown: str = ""
    background_rows: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "user_id": self.user_id,
            "compiled_at": self.compiled_at,
            "ledger_hash": self.ledger_hash,
            "input_hash": self.input_hash,
            "background_hash": self.background_hash,
            "lineage_hash": self.lineage_hash,
            "facts": [f.as_dict() for f in self.facts],
            "interpretation": list(self.interpretation),
            "open_questions": list(self.open_questions),
            "slot_hints": list(self.slot_hints),
            "facts_markdown": self.facts_markdown,
            "interpretation_markdown": self.interpretation_markdown,
            "background_markdown": self.background_markdown,
            "lineage_markdown": self.lineage_markdown,
            "background_rows": list(self.background_rows),
        }


def chb_compiler_enabled() -> bool:
    return (os.environ.get("PHA_CHB_COMPILER") or "0").strip().lower() in ("1", "true", "yes")


def user_context_brief_enabled() -> bool:
    """Opt-in injection of compiled CHB artifact into lifestyle/combined turns."""
    return (os.environ.get("PHA_USER_CONTEXT_BRIEF") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def chb_autocompile_enabled() -> bool:
    """GET /proactive/fact-card may compile in a background thread. Default on."""
    return (os.environ.get("PHA_CHB_AUTOCOMPILE") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def load_slot_candidates(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or SLOT_CANDIDATES_PATH
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.mean(values))


def read_lab_facts(
    user_id: str,
    *,
    reference_date: date | None = None,
    max_rows: int = 24,
) -> list[ChbFactRow]:
    """Read latest lab metric rows from medical ledger (T0)."""
    ref = reference_date or effective_query_reference_date()
    start = ref - timedelta(days=365 * 3)
    rows = query_metrics_in_range(user_id, start, ref)
    if not rows:
        report_d, latest = get_latest_medical_report(user_id)
        if not latest:
            return []
        rows = latest
        anchor = report_d
    else:
        anchor = rows[0].report_date

    facts: list[ChbFactRow] = []
    seen: set[str] = set()
    for r in rows[:max_rows]:
        code = (r.metric_code or r.metric_name or "").strip()
        if not code:
            continue
        key = f"{r.report_date}:{code}"
        if key in seen:
            continue
        seen.add(key)
        label = (r.name_zh or r.metric_name or code).strip()
        val = r.value
        unit = (r.unit or "").strip()
        val_s = f"{val:g}" if isinstance(val, (int, float)) else str(val or "—")
        ref_id = f"lab_{r.report_date.isoformat()}_{code}"
        facts.append(
            ChbFactRow(
                text=f"{label} {r.report_date.isoformat()}: {val_s}{(' ' + unit) if unit else ''}",
                ref_id=ref_id,
                prov_type="lab_report",
                metric_id=code.lower(),
                value=val_s,
                unit=unit or None,
                observed_at=r.report_date.isoformat(),
            ),
        )
    if not facts and anchor:
        facts.append(
            ChbFactRow(
                text=f"最近化验报告日期: {anchor.isoformat()}",
                ref_id=f"lab_report_{anchor.isoformat()}",
                prov_type="lab_report",
                observed_at=anchor.isoformat(),
            ),
        )
    return facts


def read_wearable_facts(
    user_id: str,
    *,
    reference_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[ChbFactRow]:
    """Aggregate wearable daily rows into T0 fact lines (90d window default)."""
    ref = reference_date or effective_query_reference_date()
    start = ref - timedelta(days=lookback_days)
    rows = list(query_wearable_daily_range(user_id, start, ref) or [])
    if not rows:
        return []

    sleep_vals = [float(r.sleep_hours) for r in rows if r.sleep_hours is not None]
    hrv_vals = [
        float(r.hrv_sdnn_ms if r.hrv_sdnn_ms is not None else r.hrv_rmssd_ms)
        for r in rows
        if r.hrv_sdnn_ms is not None or r.hrv_rmssd_ms is not None
    ]
    steps_vals = [float(r.steps) for r in rows if r.steps is not None]
    rhr_vals = [float(r.resting_heart_rate_bpm) for r in rows if r.resting_heart_rate_bpm is not None]

    facts: list[ChbFactRow] = []
    ref_base = f"wearable_{lookback_days}d_{ref.isoformat()}"

    def _add(metric_id: str, label: str, mean_val: float | None, unit: str) -> None:
        if mean_val is None:
            return
        val_s = f"{mean_val:.1f}"
        facts.append(
            ChbFactRow(
                text=f"近 {lookback_days}d {label} 均值: {val_s} {unit}",
                ref_id=f"{ref_base}_{metric_id}",
                prov_type="wearable_import",
                metric_id=metric_id,
                value=val_s,
                unit=unit,
                observed_at=ref.isoformat(),
            ),
        )

    _add("sleep", "睡眠", _mean(sleep_vals), "h")
    _add("hrv", "HRV", _mean(hrv_vals), "ms")
    _add("steps", "步数", _mean(steps_vals), "步/日")
    _add("rhr", "静息心率", _mean(rhr_vals), "bpm")
    return facts


def assemble_facts_section(facts: list[ChbFactRow]) -> str:
    """Deterministic §Facts markdown — no LLM."""
    if not facts:
        return "## §Facts（硬事实 · 可引用）\n- （暂无 T0 事实行）"
    lines = ["## §Facts（硬事实 · 可引用）"]
    for f in facts:
        lines.append(f"- {f.text} [ref: {f.ref_id}]")
    return "\n".join(lines)


def compile_interpretation_stub(
    facts: list[ChbFactRow],
    *,
    enable_llm: bool = False,
    facts_markdown: str = "",
    llm_fn: InterpretationLlmFn | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Compile §Interpretation. Default stub; LLM when ``PHA_CHB_COMPILER=1``.

    RIGID RED LINE: output is advisory only — never a numerics source.
    """
    derived = [f.ref_id for f in facts[:12]]
    if enable_llm and chb_compiler_enabled():
        body = compile_interpretation_llm(
            facts,
            facts_markdown=facts_markdown,
            llm_fn=llm_fn,
        )
        if body:
            items = [{"text": body, "derived_from": derived, "prov_type": "llm_advisory"}]
            md = f"{INTERPRETATION_ADVISORY_BANNER}\n- {body}"
            return items, md
    if not facts:
        return [], f"{INTERPRETATION_ADVISORY_BANNER}\n- （事实不足，暂无解读）"
    items = [
        {
            "text": "以上为 T0 账本可引用事实；启用 PHA_CHB_COMPILER=1 可生成趋势解读（仍为非数字源）。",
            "derived_from": derived,
            "prov_type": "stub",
        },
    ]
    md = (
        f"{INTERPRETATION_ADVISORY_BANNER}\n"
        "- 以上为 T0 账本可引用事实；启用 PHA_CHB_COMPILER=1 可生成趋势解读（仍为非数字源）。"
    )
    return items, md


def compile_interpretation_llm(
    facts: list[ChbFactRow],
    *,
    facts_markdown: str = "",
    llm_fn: InterpretationLlmFn | None = None,
) -> str:
    """BYOK LLM trend synthesis from §Facts snapshot only (no raw device dump).

    Returns advisory prose only. Callers MUST NOT treat output as numerics source.
    """
    if llm_fn is not None:
        return llm_fn(facts_markdown or assemble_facts_section(facts)).strip()

    fm = facts_markdown or assemble_facts_section(facts)
    system = (
        "你是慢性健康简报编译器。仅基于用户提供的 §Facts 事实块做趋势研判。"
        "禁止编造 §Facts 中未出现的数字、日期或诊断。"
        "输出 2-4 条短句，每条须可追溯到 §Facts 中的 [ref:…]。"
        "禁止输出具体剂量或用药指令。"
    )
    user = f"§Facts 快照：\n{fm}\n\n请输出 §Interpretation 趋势研判（纯文本，非数字源）："
    try:
        from pha.llm_provider import get_llm_provider

        provider = get_llm_provider()
        raw = provider.chat_completion(system_prompt=system, user_message=user)
        return str(raw or "").strip()
    except Exception as exc:
        logger.warning("CHB LLM interpretation failed: %s", exc)
        return ""


def load_latest_chb_artifact(
    user_id: str,
    *,
    report_root: Path | None = None,
) -> ChronicHealthBrief | None:
    """Load newest ``brief_*.json`` for user (mtime). Returns None if missing."""
    uid = (user_id or "default").strip() or "default"
    root = resolve_report_root(report_root)
    out_dir = root / uid
    if not out_dir.is_dir():
        return None
    candidates = sorted(
        out_dir.glob("brief_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(doc.get("schema") or "") != CHB_SCHEMA:
            continue
        facts = [
            ChbFactRow(
                text=str(r.get("text") or ""),
                ref_id=str(r.get("ref_id") or ""),
                prov_type=str(r.get("prov_type") or ""),
                metric_id=r.get("metric_id"),
                value=r.get("value"),
                unit=r.get("unit"),
                observed_at=r.get("observed_at"),
            )
            for r in (doc.get("facts") or [])
            if isinstance(r, dict)
        ]
        return ChronicHealthBrief(
            schema=CHB_SCHEMA,
            user_id=str(doc.get("user_id") or uid),
            compiled_at=str(doc.get("compiled_at") or ""),
            ledger_hash=str(doc.get("ledger_hash") or ""),
            input_hash=str(doc.get("input_hash") or ""),
            background_hash=str(doc.get("background_hash") or ""),
            lineage_hash=str(doc.get("lineage_hash") or ""),
            facts=facts,
            interpretation=list(doc.get("interpretation") or []),
            open_questions=list(doc.get("open_questions") or []),
            slot_hints=list(doc.get("slot_hints") or []),
            facts_markdown=str(doc.get("facts_markdown") or assemble_facts_section(facts)),
            interpretation_markdown=str(doc.get("interpretation_markdown") or ""),
            background_markdown=str(doc.get("background_markdown") or ""),
            lineage_markdown=str(doc.get("lineage_markdown") or ""),
            background_rows=[
                {
                    "category": str(r.get("category") or ""),
                    "text": str(r.get("text") or ""),
                    "rel_key": str(r.get("rel_key") or ""),
                    "prov_type": str(r.get("prov_type") or "user_statement"),
                }
                for r in (doc.get("background_rows") or [])
                if isinstance(r, dict) and str(r.get("text") or "").strip()
            ],
        )
    return None


def build_user_context_brief_block(
    user_id: str,
    *,
    profile: str,
    report_root: Path | None = None,
    recompile_if_stale: bool = False,
) -> str:
    """Tier1 slot body for ``USER_CONTEXT_BRIEF``.

    Reads newest artifact by mtime; empty when missing (never blocks turn).
    Sections come from the profile registry map, not session-level ifs.
    """
    prof = (profile or "").strip()
    sections = user_context_brief_sections(prof)
    if not sections:
        return ""
    uid = (user_id or "default").strip() or "default"
    brief = load_latest_chb_artifact(uid, report_root=report_root)
    if brief is None and recompile_if_stale:
        try:
            brief = compile_chronic_health_brief(
                uid,
                enable_llm_interpretation=chb_compiler_enabled(),
            )
            write_chb_artifact(brief, report_root=report_root)
        except Exception as exc:
            logger.warning("CHB compile for USER_CONTEXT_BRIEF failed: %s", exc)
            return ""
    if brief is None:
        return ""

    parts = [
        "【USER_CONTEXT_BRIEF · Tier1 · 慢性健康简报 · 只读】",
        f"ledger_hash={brief.ledger_hash} compiled_at={brief.compiled_at}",
    ]
    if "facts" in sections:
        parts.append(brief.facts_markdown.strip())
    if "background" in sections:
        bg_md = render_chb_background_markdown(brief, locale=_chb_locale(uid))
        if bg_md:
            parts.append(bg_md)
    if "interpretation" in sections and brief.interpretation_markdown.strip():
        parts.append(brief.interpretation_markdown.strip())
    if "open_questions" in sections and brief.open_questions:
        parts.append("## §Open Questions")
        for q in brief.open_questions:
            parts.append(f"- {q}")
    return "\n\n".join(p for p in parts if p).strip()


def _chb_locale(user_id: str) -> str:
    try:
        from pha.fact_card_prefs import load_fact_card_locale

        return (load_fact_card_locale(user_id) or "zh-CN").strip() or "zh-CN"
    except Exception:
        return "zh-CN"


def compute_input_hash(ledger_hash: str, background_hash: str, lineage_hash: str) -> str:
    blob = f"{ledger_hash}|{background_hash}|{lineage_hash}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def compute_live_background_hash(
    user_id: str,
    *,
    locale: str = "zh-CN",
    as_of: str | None = None,
) -> str:
    from pha.fact_card_background_brief import compile_background_statement_rows

    _rows, meta = compile_background_statement_rows(
        user_id,
        locale=locale,
        as_of=as_of,
    )
    digest = str(meta.get("digest") or "")
    return digest[:16] if digest else hashlib.sha256(b"").hexdigest()[:16]


_LINEAGE_SPLIT_RE = re.compile(r"[。！？!?\n]+")
# re.I must be a compile flag: Python 3.11+ rejects inline (?i) after the first alternative.
_LINEAGE_WINDOW_STUB_RE = re.compile(
    r"近.{0,16}(均值|最低|最高|夜数|天数)|\b(mean|minimum|maximum|percentile)\b",
    re.I,
)


def _is_lineage_field_stub(text: str, *, locale: str) -> bool:
    """True when a denumerized fragment is a metric-field label, not a caution."""
    from pha.fact_card_background_brief import is_background_text_stub

    if is_background_text_stub(text, locale=locale):
        return True
    body = (text or "").strip().lstrip("-–—• ").strip()
    return bool(_LINEAGE_WINDOW_STUB_RE.search(body))


def _lineage_sentences(text: str, *, locale: str) -> list[str]:
    from pha.fact_card_background_brief import denumerize_background_line
    from pha.numerics_manifest import leftover_s_level_numeric_tokens

    out: list[str] = []
    for chunk in _LINEAGE_SPLIT_RE.split(text or ""):
        raw = chunk.strip().lstrip("-–—• ").strip()
        if len(raw) < 8:
            continue
        cleaned = denumerize_background_line(raw, locale=locale)
        if not cleaned or leftover_s_level_numeric_tokens(cleaned):
            continue
        if _is_lineage_field_stub(cleaned, locale=locale):
            continue
        out.append(cleaned)
    return out


def assemble_background_section(
    user_id: str,
    *,
    locale: str = "zh-CN",
    as_of: str | None = None,
) -> tuple[str, str, list[dict[str, str]]]:
    """Return (markdown, hash, rows). Compiled statement rows; never §Facts."""
    from pha.fact_card_background_brief import (
        compile_background_statement_rows,
        render_background_brief_markdown,
    )

    rows, meta = compile_background_statement_rows(
        user_id,
        locale=locale,
        as_of=as_of,
    )
    digest = str(meta.get("digest") or "")
    digest = digest[:16] if digest else hashlib.sha256(b"").hexdigest()[:16]
    payload = [r.as_dict() for r in rows]
    if not rows:
        return "", digest, []
    header = "## §Background（自述 · 非数字源 · ADVISORY ONLY）"
    body = render_background_brief_markdown(rows, locale=locale)
    md = f"{header}\n{body.strip()}"
    return md, digest, payload


def assemble_lineage_section(
    user_id: str,
    *,
    locale: str = "zh-CN",
    lookback_days: int = 30,
    min_freq: int = 2,
    interpret_root: Path | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Repeated interpret-cache cautions; denumerized; no LLM."""
    from pha.fact_card_interpret import interpret_dir

    uid = (user_id or "default").strip() or "default"
    root = interpret_root if interpret_root is not None else interpret_dir()
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(1, int(lookback_days)))
    counts: dict[str, int] = {}
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            if str(doc.get("status") or "") != "done":
                continue
            audit = doc.get("numerics_audit") or {}
            if isinstance(audit, dict) and audit.get("passed") is False:
                continue
            owner = str(doc.get("user_id") or uid).strip() or uid
            if owner != uid:
                continue
            stamp = str(doc.get("generated_at") or "")
            if stamp:
                try:
                    generated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                    if generated.tzinfo is None:
                        generated = generated.replace(tzinfo=timezone.utc)
                    if generated < cutoff:
                        continue
                except ValueError:
                    pass
            for sent in _lineage_sentences(str(doc.get("text") or ""), locale=locale):
                counts[sent] = counts.get(sent, 0) + 1
    kept = [s for s, n in counts.items() if n >= max(1, int(min_freq))]
    kept.sort()
    blob = json.dumps(kept, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    if not kept:
        return "", digest
    lines = ["## §Interpretation lineage（反复出现的注意事项 · 非数字源）"]
    lines.extend(f"- {row}" for row in kept)
    return "\n".join(lines), digest


def render_chb_background_markdown(
    brief: ChronicHealthBrief,
    *,
    locale: str = "zh-CN",
) -> str:
    """Render §Background from compiled rows + current copy (lead is not frozen)."""
    from pha.fact_card_background_brief import (
        BackgroundStatementRow,
        render_background_brief_markdown,
    )

    rows: list[BackgroundStatementRow] = []
    for item in brief.background_rows or []:
        if not isinstance(item, dict):
            continue
        cat = str(item.get("category") or "").strip()
        text = str(item.get("text") or "").strip()
        rel = str(item.get("rel_key") or "bg_brief_rel_earlier").strip()
        if not cat or not text:
            continue
        rows.append(
            BackgroundStatementRow(
                category=cat,
                text=text,
                rel_key=rel or "bg_brief_rel_earlier",
                prov_type=str(item.get("prov_type") or "user_statement"),
            )
        )
    if not rows:
        return (brief.background_markdown or "").strip()
    header = "## §Background（自述 · 非数字源 · ADVISORY ONLY）"
    body = render_background_brief_markdown(rows, locale=locale)
    return f"{header}\n{body.strip()}"


def project_chb_for_fact_card_interpret(
    brief: ChronicHealthBrief,
    *,
    locale: str = "zh-CN",
) -> str:
    """Interpret projection: §Background + lineage only. Never §Facts."""
    parts = [
        render_chb_background_markdown(brief, locale=locale),
        (brief.lineage_markdown or "").strip(),
    ]
    text = "\n\n".join(p for p in parts if p)
    if "§Facts" in text:
        logger.warning("CHB interpret projection dropped leaked §Facts")
        text = "\n\n".join(
            block for block in text.split("\n\n") if "§Facts" not in block
        )
    return text.strip()


def _last_compile_marker(user_id: str, *, report_root: Path | None = None) -> Path:
    uid = (user_id or "default").strip() or "default"
    root = resolve_report_root(report_root)
    return root / uid / ".last_compile_day"


def maybe_autocompile_chb(
    user_id: str,
    *,
    report_root: Path | None = None,
    reference_date: date | None = None,
    now: date | None = None,
) -> dict[str, Any]:
    """Same-day-once compile. Failures never raise to the card path."""
    uid = (user_id or "default").strip() or "default"
    if not chb_autocompile_enabled():
        return {"skipped": "flag_off", "user_id": uid}
    day = (now or date.today()).isoformat()
    marker = _last_compile_marker(uid, report_root=report_root)
    try:
        if marker.is_file() and marker.read_text(encoding="utf-8").strip()[:10] == day:
            return {"skipped": "same_day", "user_id": uid}
    except OSError:
        pass
    path: Path | None = None
    try:
        status, path = recompile_chb_if_stale(
            uid,
            report_root=report_root,
            reference_date=reference_date,
        )
    except Exception as exc:
        logger.warning("CHB autocompile failed user=%s: %s", uid, exc)
        return {"error": type(exc).__name__, "user_id": uid}
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(day + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("CHB compile-day marker failed user=%s: %s", uid, exc)
    return {
        "user_id": uid,
        "status": status,
        "path": str(path) if path else None,
        "skipped": None,
    }


def schedule_chb_autocompile(user_id: str) -> None:
    """Fire-and-forget; GET /proactive/fact-card must not wait."""
    uid = (user_id or "default").strip() or "default"

    def _run() -> None:
        try:
            maybe_autocompile_chb(uid)
        except Exception as exc:  # pragma: no cover
            logger.warning("CHB background compile crashed user=%s: %s", uid, exc)

    threading.Thread(target=_run, name=f"pha-chb-autocompile-{uid}", daemon=True).start()


def compute_ledger_hash(facts: list[ChbFactRow]) -> str:
    payload = json.dumps([f.as_dict() for f in facts], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def read_live_t0_facts(
    user_id: str,
    *,
    reference_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[ChbFactRow]:
    """Read current live T0 facts from medical + wearable ledgers."""
    uid = (user_id or "default").strip() or "default"
    ref = reference_date or effective_query_reference_date()
    return read_lab_facts(uid, reference_date=ref) + read_wearable_facts(
        uid,
        reference_date=ref,
        lookback_days=lookback_days,
    )


def compute_live_ledger_hash(
    user_id: str,
    *,
    reference_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> str:
    """Hash of serialized live T0 facts (same algorithm as ``compile_chronic_health_brief``)."""
    return compute_ledger_hash(
        read_live_t0_facts(
            user_id,
            reference_date=reference_date,
            lookback_days=lookback_days,
        ),
    )


def list_chb_report_user_ids(*, report_root: Path | None = None) -> list[str]:
    """Discover user_id directories under ``reports/chb/`` (always includes ``default``)."""
    root = resolve_report_root(report_root)
    ids: list[str] = []
    if root.is_dir():
        ids = sorted(
            d.name
            for d in root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
    if "default" not in ids:
        ids.insert(0, "default")
    return ids


def list_chb_artifact_paths(
    user_id: str,
    *,
    report_root: Path | None = None,
) -> list[Path]:
    """All ``brief_*.json`` paths for user (mtime descending)."""
    uid = (user_id or "default").strip() or "default"
    root = resolve_report_root(report_root)
    out_dir = root / uid
    if not out_dir.is_dir():
        return []
    return sorted(out_dir.glob("brief_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def chb_stale_status(
    user_id: str,
    *,
    report_root: Path | None = None,
    reference_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    locale: str | None = None,
) -> dict[str, Any]:
    """Compare live input hash (T0 + background + lineage) vs newest artifact."""
    uid = (user_id or "default").strip() or "default"
    loc = (locale or "").strip() or _chb_locale(uid)
    ref = reference_date or effective_query_reference_date()
    live_hash = compute_live_ledger_hash(
        uid,
        reference_date=reference_date,
        lookback_days=lookback_days,
    )
    live_bg = compute_live_background_hash(uid, locale=loc, as_of=ref.isoformat())
    live_lin = assemble_lineage_section(uid, locale=loc)[1]
    live_input = compute_input_hash(live_hash, live_bg, live_lin)
    latest = load_latest_chb_artifact(uid, report_root=report_root)
    artifact_hash = (latest.ledger_hash or "").strip() if latest else ""
    artifact_input = (latest.input_hash or "").strip() if latest else ""
    exact_path = resolve_report_root(report_root) / uid / f"brief_{live_input}.json"
    is_stale = latest is None or live_input != artifact_input
    return {
        "user_id": uid,
        "live_hash": live_hash,
        "live_input_hash": live_input,
        "artifact_hash": artifact_hash or None,
        "artifact_input_hash": artifact_input or None,
        "is_stale": is_stale,
        "exact_artifact_exists": exact_path.is_file(),
        "artifact_count": len(list_chb_artifact_paths(uid, report_root=report_root)),
    }


def recompile_chb_if_stale(
    user_id: str,
    *,
    report_root: Path | None = None,
    reference_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    enable_llm_interpretation: bool | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], Path | None]:
    """Offline compile when live T0 hash diverges from newest artifact."""
    uid = (user_id or "default").strip() or "default"
    status = chb_stale_status(
        uid,
        report_root=report_root,
        reference_date=reference_date,
        lookback_days=lookback_days,
    )
    if not status["is_stale"]:
        return status, None
    if dry_run:
        return status, None
    llm = (
        chb_compiler_enabled()
        if enable_llm_interpretation is None
        else enable_llm_interpretation
    )
    brief = compile_chronic_health_brief(
        uid,
        reference_date=reference_date,
        lookback_days=lookback_days,
        enable_llm_interpretation=llm,
    )
    path = write_chb_artifact(brief, report_root=report_root)
    status["artifact_hash"] = brief.ledger_hash
    status["is_stale"] = False
    status["exact_artifact_exists"] = True
    status["artifact_count"] = len(list_chb_artifact_paths(uid, report_root=report_root))
    return status, path


def compile_chronic_health_brief(
    user_id: str,
    *,
    reference_date: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    slot_candidates: list[dict[str, Any]] | None = None,
    enable_llm_interpretation: bool = False,
) -> ChronicHealthBrief:
    uid = (user_id or "default").strip() or "default"
    ref = reference_date or effective_query_reference_date()
    lab_facts = read_lab_facts(uid, reference_date=ref)
    wear_facts = read_wearable_facts(uid, reference_date=ref, lookback_days=lookback_days)
    facts = lab_facts + wear_facts
    slots = slot_candidates if slot_candidates is not None else load_slot_candidates()
    facts_md = assemble_facts_section(facts)

    interpretation, interp_md = compile_interpretation_stub(
        facts,
        enable_llm=enable_llm_interpretation,
        facts_markdown=facts_md,
    )
    open_q: list[str] = []
    if not lab_facts:
        open_q.append("尚未有化验面板 T0 行；上传 PDF/截图可补 §Facts。")
    if not wear_facts:
        open_q.append("尚未有穿戴日聚合；导入 Apple Health export.zip 可补 §Facts。")
    from pha.chb_gap_harvest import load_gap_open_questions, merge_gap_questions

    gap_q = load_gap_open_questions(uid, report_root=DEFAULT_REPORT_ROOT)
    open_q = merge_gap_questions(open_q, [{"question": q} for q in gap_q])

    brief = ChronicHealthBrief(
        user_id=uid,
        compiled_at=datetime.now(timezone.utc).isoformat(),
        ledger_hash=compute_ledger_hash(facts),
        facts=facts,
        interpretation=interpretation,
        open_questions=open_q,
        slot_hints=slots,
        facts_markdown=facts_md,
        interpretation_markdown=interp_md,
    )
    locale = _chb_locale(uid)
    as_of = ref.isoformat() if hasattr(ref, "isoformat") else None
    bg_md, bg_hash, bg_rows = assemble_background_section(
        uid, locale=locale, as_of=as_of
    )
    lin_md, lin_hash = assemble_lineage_section(uid, locale=locale)
    brief.background_markdown = bg_md
    brief.lineage_markdown = lin_md
    brief.background_hash = bg_hash
    brief.lineage_hash = lin_hash
    brief.background_rows = bg_rows
    brief.input_hash = compute_input_hash(brief.ledger_hash, bg_hash, lin_hash)
    return brief


def write_chb_artifact(
    brief: ChronicHealthBrief,
    *,
    report_root: Path | None = None,
) -> Path:
    root = resolve_report_root(report_root)
    out_dir = root / brief.user_id
    out_dir.mkdir(parents=True, exist_ok=True)
    name_hash = (brief.input_hash or brief.ledger_hash or "unknown").strip() or "unknown"
    path = out_dir / f"brief_{name_hash}.json"
    path.write_text(json.dumps(brief.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = [
    "CHB_SCHEMA",
    "ChbFactRow",
    "ChronicHealthBrief",
    "INTERPRETATION_ADVISORY_BANNER",
    "InterpretationLlmFn",
    "USER_CONTEXT_BRIEF_PROFILES",
    "user_context_brief_sections",
    "assemble_facts_section",
    "build_user_context_brief_block",
    "chb_compiler_enabled",
    "chb_autocompile_enabled",
    "user_context_brief_enabled",
    "compile_chronic_health_brief",
    "compile_interpretation_llm",
    "compile_interpretation_stub",
    "chb_stale_status",
    "compute_ledger_hash",
    "compute_live_ledger_hash",
    "compute_input_hash",
    "assemble_background_section",
    "assemble_lineage_section",
    "project_chb_for_fact_card_interpret",
    "maybe_autocompile_chb",
    "schedule_chb_autocompile",
    "list_chb_artifact_paths",
    "list_chb_report_user_ids",
    "read_live_t0_facts",
    "recompile_chb_if_stale",
    "load_latest_chb_artifact",
    "load_slot_candidates",
    "read_lab_facts",
    "read_wearable_facts",
    "write_chb_artifact",
]
