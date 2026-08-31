"""Numerics audit — 报税回复数字须 ⊆ filing_table + classifiedIncome / combinedRows（§2.4）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from tax_agent.filing_session_state import FilingSessionState
from tax_agent.harness_plan import FilingTurnPlan

_MANIFEST_MAX_CHARS = int(os.environ.get("TAX_MANIFEST_MAX_CHARS", "500"))
_DECIMAL_RE = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?(?!\d)")
_FX_RATE_RE = re.compile(r"(?<!\d)([4-8]\.\d{4})(?!\d)")
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_SMALL_INT_ALLOW = frozenset({"0", "1", "2", "3", "4", "5", "10", "12", "20", "30", "50", "90", "100"})


@dataclass
class NumericsAuditResult:
    ok: bool
    allowed_count: int
    cited_count: int
    unknown: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "allowedCount": self.allowed_count,
            "citedCount": self.cited_count,
            "unknown": self.unknown[:20],
            "warnings": self.warnings,
        }


def _normalize_decimal_token(raw: str) -> str | None:
    t = (raw or "").replace(",", "").strip()
    if not t:
        return None
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".")


def _collect_numeric_strings(obj: Any, out: set[str]) -> None:
    if obj is None:
        return
    if isinstance(obj, (int, float, Decimal)):
        n = _normalize_decimal_token(str(obj))
        if n:
            out.add(n)
        return
    if isinstance(obj, str):
        n = _normalize_decimal_token(obj)
        if n and len(n) >= 2:
            out.add(n)
        for m in _FX_RATE_RE.finditer(obj):
            out.add(m.group(1))
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_numeric_strings(v, out)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numeric_strings(v, out)


def build_numerics_manifest(
    state: FilingSessionState,
    plan: FilingTurnPlan,
) -> set[str]:
    """从 filing snapshot / summary 提取允许出现在回复中的数字集合。"""
    allowed: set[str] = set()
    snap = state.last_filing_snapshot or {}
    _collect_numeric_strings(snap, allowed)
    _collect_numeric_strings(state.last_provenance, allowed)
    _collect_numeric_strings(state.last_insight, allowed)

    year = state.effective_tax_year(plan)
    if state.data_quality:
        from tax_agent.filing_session_state import build_authoritative_filing_report

        rep = build_authoritative_filing_report(state, years=[year])
        if not rep.get("error"):
            _collect_numeric_strings(rep, allowed)
    allowed.add(str(year))
    if year > 2000:
        allowed.add(str(year - 1))
    return allowed


def format_numerics_manifest_block(
    manifest: set[str],
    *,
    tax_year: int,
) -> str:
    """压缩 manifest 供 Tier0 注入。"""
    fx = sorted(x for x in manifest if _FX_RATE_RE.fullmatch(x))
    big = sorted(
        (x for x in manifest if x not in fx and len(x.replace(".", "")) >= 3),
        key=lambda x: (-len(x), x),
    )[:24]
    lines = [
        "【Numerics Manifest · 回复中金额/税额仅可引用下列登记值】",
        f"- taxYear: {tax_year}",
    ]
    if fx:
        lines.append(f"- fxRates: {', '.join(fx[:4])}")
    if big:
        lines.append(f"- amounts: {', '.join(big)}")
    block = "\n".join(lines)
    if len(block) > _MANIFEST_MAX_CHARS:
        block = block[:_MANIFEST_MAX_CHARS] + "…"
    return block


_PLACEHOLDER_RE = re.compile(r"\{\{NUM_(\d+)\}\}")


def freeze_numerics_placeholders(
    text: str,
    manifest: set[str],
) -> tuple[str, dict[str, str]]:
    """将 manifest 中数字替换为 {{NUM_n}}，供 LLM 润色后还原。"""
    if not text or not manifest:
        return text, {}
    candidates = sorted(
        (n for n in manifest if n and len(str(n)) >= 2),
        key=lambda x: (-len(str(x)), str(x)),
    )
    mapping: dict[str, str] = {}
    out = text
    idx = 0
    for num in candidates:
        if num not in out:
            continue
        token = f"{{{{NUM_{idx}}}}}"
        out = out.replace(str(num), token)
        mapping[token] = str(num)
        idx += 1
    return out, mapping


def restore_numerics_placeholders(text: str, mapping: dict[str, str]) -> str:
    out = text or ""
    for token, num in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(token, num)
    return out


def placeholders_intact(polished: str, mapping: dict[str, str]) -> bool:
    """润色稿须保留全部占位符（或已还原为原数字）。"""
    if not mapping:
        return True
    for token, num in mapping.items():
        if token in polished:
            continue
        if num in polished:
            continue
        return False
    return True


def _span_inside_fx(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    for fs, fe in spans:
        if start >= fs and end <= fe:
            return True
    return False


def extract_significant_numbers(text: str) -> list[str]:
    text = text or ""
    found: list[str] = []
    fx_spans: list[tuple[int, int]] = []
    for m in _FX_RATE_RE.finditer(text):
        found.append(m.group(1))
        fx_spans.append(m.span())
    for m in _DECIMAL_RE.finditer(text):
        if _span_inside_fx(fx_spans, m.start(), m.end()):
            continue
        whole = m.group(1).replace(",", "")
        frac = m.group(2) or ""
        token = f"{whole}.{frac}" if frac else whole
        norm = _normalize_decimal_token(token)
        if norm:
            found.append(norm)
    return found


def _is_benign_number(token: str, text: str) -> bool:
    if token in _SMALL_INT_ALLOW:
        return True
    if _YEAR_RE.fullmatch(token):
        y = int(token)
        if 2015 <= y <= 2035:
            return True
    # 百分比语境
    if re.search(rf"{re.escape(token)}\s*%", text):
        return True
    # 中文月日（12月31日、31日）— 叙述层常提及末日，非申报金额
    if token.isdigit() and 1 <= int(token) <= 31:
        if re.search(rf"\d{{1,2}}月{re.escape(token)}(?:日)?", text):
            return True
        if re.search(rf"{re.escape(token)}\s*日", text):
            return True
    return False


def audit_response_numerics(
    reply: str,
    manifest: set[str],
    *,
    strict: bool | None = None,
) -> NumericsAuditResult:
    """检查回复中的数字是否均在 manifest 内。"""
    if strict is None:
        strict = os.environ.get("TAX_NUMERICS_AUDIT_STRICT", "0").strip() in ("1", "true", "yes")

    if not manifest:
        return NumericsAuditResult(
            ok=True,
            allowed_count=0,
            cited_count=0,
            warnings=["manifest_empty_skip"],
        )

    cited = extract_significant_numbers(reply)
    unknown: list[str] = []
    for token in cited:
        if token in manifest:
            continue
        if _is_benign_number(token, reply):
            continue
        if token not in unknown:
            unknown.append(token)

    warnings: list[str] = []
    if unknown:
        warnings.append(f"unregistered_numerics:{','.join(unknown[:8])}")

    ok = len(unknown) == 0
    if not ok and strict:
        warnings.append("strict_mode_violation")

    return NumericsAuditResult(
        ok=ok,
        allowed_count=len(manifest),
        cited_count=len(cited),
        unknown=unknown,
        warnings=warnings,
    )


def _narrative_strict_enabled(plan: FilingTurnPlan) -> bool:
    if plan.profile == "filing_narrative":
        return True
    return os.environ.get("TAX_NUMERICS_AUDIT_STRICT", "0").strip() in ("1", "true", "yes")


def audit_turn_reply(
    reply: str,
    state: FilingSessionState,
    plan: FilingTurnPlan,
) -> tuple[str, NumericsAuditResult]:
    """审计并可选用脚注标注未登记数字；filing_narrative 默认 strict。"""
    manifest = build_numerics_manifest(state, plan)
    strict = _narrative_strict_enabled(plan)
    result = audit_response_numerics(reply, manifest, strict=strict)
    if result.ok or not result.unknown:
        return reply, result
    if strict:
        from tax_agent.filing_narrative import build_filing_narrative

        year = state.effective_tax_year(plan)
        fallback = build_filing_narrative(
            data_quality=state.data_quality,
            tax_year=year,
            fx_provider=state.fx_provider,
            events=state.events,
        )
        if not fallback.get("error"):
            safe = fallback.get("narrative") or reply
            return (
                safe
                + "\n\n（已回退至申报数据表确定性叙述；原 LLM 草稿含未登记数字。）",
                result,
            )
    footnote = (
        "\n\n（系统提示：上文含未在申报数据表登记的数值，请以「生成申报数据表」为准。）"
    )
    return reply + footnote, result
