"""Policy citation audit for narrated replies (Tax Chat Experience v2 · C1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_LEGAL_TRIGGER_RE = re.compile(
    r"(法实施条例|个人所得税法|税法|公告|令第|文号|第[一二三四五六七八九十百\d]+条|国家税务总局|财税)"
)


@dataclass
class CitationAuditResult:
    ok: bool
    reason: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "reason": self.reason, "warnings": self.warnings}


def _normalize_cite_surface(text: str) -> str:
    out = text or ""
    for ch in "【】《》""\"'":
        out = out.replace(ch, "")
    return re.sub(r"\s+", "", out)


def _label_fragments(label: str) -> list[str]:
    label = (label or "").strip()
    if not label:
        return []
    frags = [label, _normalize_cite_surface(label)]
    if len(label) > 8:
        frags.append(label[-8:])
        frags.append(_normalize_cite_surface(label)[-8:])
    if "实施条例" in label:
        frags.append("实施条例")
    if "第三十二条" in label:
        frags.append("第三十二条")
    if "个人所得税法" in label:
        frags.append("个人所得税法")
    return list(dict.fromkeys(f for f in frags if f and len(f) >= 4))


def audit_policy_citations(
    reply: str,
    citations: list[dict[str, str]] | list[Any],
) -> CitationAuditResult:
    """Narration with legal triggers must cite a known label from the bundle."""
    text = reply or ""
    norm_text = _normalize_cite_surface(text)
    if not _LEGAL_TRIGGER_RE.search(text):
        return CitationAuditResult(ok=True)

    labels: list[str] = []
    for c in citations or []:
        if isinstance(c, dict):
            labels.append(str(c.get("label") or ""))
        else:
            labels.append(str(getattr(c, "label", "") or ""))

    if not labels:
        return CitationAuditResult(ok=False, reason="uncited_legal_reference")

    for label in labels:
        if label and (label in text or _normalize_cite_surface(label) in norm_text):
            return CitationAuditResult(ok=True)
        for frag in _label_fragments(label):
            if frag and (frag in text or frag in norm_text):
                return CitationAuditResult(ok=True)

    return CitationAuditResult(ok=False, reason="citation_label_missing")
