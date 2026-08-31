"""PolicyKB — 审定政策知识卡检索与 policy_qa 快车道（Tax Chat Experience v2 · C2）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from tax_agent.fact_bundle import FactBundle, PolicyCitation
from tax_agent.tax_intent_catalog import token_in_message

_KB_DIR = Path(__file__).resolve().parent.parent / "rules" / "knowledge" / "cn_overseas_income"

_OFF_KB_POLICY_RE = re.compile(
    r"(税|申报|汇算|滞纳|境外|离岸|外国|海外|法国|美国税|日本税|德国税|怎么算|要不要|能不能)",
    re.I,
)
_FOREIGN_OFF_KB_RE = re.compile(
    r"(法国|美国税|日本税|德国税|英国税|外国.*税|海外.*税)",
    re.I,
)


@dataclass(frozen=True)
class KnowledgeCard:
    id: str
    title_zh: str
    question_patterns: tuple[dict[str, Any], ...]
    answer_t0: str
    citations: tuple[dict[str, str], ...]
    effective_date: str
    review_status: str

    def score_message(self, message: str) -> float:
        total = 0.0
        for rule in self.question_patterns:
            token = str(rule.get("token") or "").strip()
            if token and token_in_message(token, message):
                total += float(rule.get("weight") or 1.0)
        return total

    def citation_objects(self) -> list[PolicyCitation]:
        out: list[PolicyCitation] = []
        for c in self.citations:
            cid = str(c.get("id") or "").strip()
            label = str(c.get("label") or "").strip()
            if cid and label:
                out.append(PolicyCitation(id=cid, label=label))
        return out


def kb_allow_draft() -> bool:
    return os.environ.get("TAX_KB_ALLOW_DRAFT", "0").strip().lower() in ("1", "true", "yes")


@lru_cache(maxsize=1)
def load_knowledge_cards(*, include_draft: bool | None = None) -> tuple[KnowledgeCard, ...]:
    if include_draft is None:
        include_draft = kb_allow_draft()
    cards: list[KnowledgeCard] = []
    if not _KB_DIR.is_dir():
        return tuple()
    for path in sorted(_KB_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in data.get("cards") or []:
            if not isinstance(raw, dict):
                continue
            status = str(raw.get("review_status") or "draft").strip().lower()
            if status != "reviewed" and not include_draft:
                continue
            patterns = tuple(raw.get("question_patterns") or ())
            cites = tuple(raw.get("citations") or ())
            cards.append(
                KnowledgeCard(
                    id=str(raw.get("id") or ""),
                    title_zh=str(raw.get("title_zh") or ""),
                    question_patterns=patterns,
                    answer_t0=str(raw.get("answer_t0") or "").strip(),
                    citations=cites,
                    effective_date=str(raw.get("effective_date") or ""),
                    review_status=status,
                )
            )
    return tuple(cards)


def score_knowledge_cards(message: str) -> tuple[float, list[KnowledgeCard]]:
    """Return (best_total_score, matched_cards_sorted_by_score)."""
    msg = (message or "").strip()
    if not msg:
        return 0.0, []
    scored: list[tuple[float, KnowledgeCard]] = []
    for card in load_knowledge_cards():
        s = card.score_message(msg)
        if s > 0:
            scored.append((s, card))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    if not scored:
        return 0.0, []
    total = scored[0][0]
    return total, [c for _, c in scored]


def retrieve_top_cards(message: str, *, limit: int = 2) -> list[KnowledgeCard]:
    _, cards = score_knowledge_cards(message)
    return cards[:limit]


def list_reviewed_topic_titles() -> list[str]:
    return [c.title_zh for c in load_knowledge_cards() if c.review_status == "reviewed"]


def policy_question_off_kb_score(message: str) -> float:
    """Score for policy-like questions with no KB hit (out-of-scope path)."""
    kb_score, _ = score_knowledge_cards(message)
    if kb_score > 0:
        return 0.0
    msg = message or ""
    if _FOREIGN_OFF_KB_RE.search(msg):
        return 5.0
    if _OFF_KB_POLICY_RE.search(msg):
        return 2.0
    return 0.0


def policy_question_off_kb(message: str) -> bool:
    return policy_question_off_kb_score(message) > 0


def format_policy_kb_reply_zh(cards: list[KnowledgeCard]) -> str:
    if not cards:
        return format_policy_kb_out_of_scope_zh()
    if len(cards) == 1:
        c = cards[0]
        lines = [c.answer_t0.strip()]
        if c.citations:
            cite_labels = "、".join(str(x.get("label")) for x in c.citations if x.get("label"))
            lines.append(f"\n**依据**：{cite_labels}")
        lines.append(f"\n（知识卡：{c.title_zh} · T0）")
        return "\n".join(lines)

    lines = ["以下根据知识库回答您的问题：", ""]
    for i, c in enumerate(cards, 1):
        lines.append(f"**{i}. {c.title_zh}**")
        lines.append(c.answer_t0.strip())
        if c.citations:
            cite_labels = "、".join(str(x.get("label")) for x in c.citations if x.get("label"))
            lines.append(f"依据：{cite_labels}")
        lines.append("")
    lines.append("（政策知识库 T0 · 多条合并）")
    return "\n".join(lines)


def format_policy_kb_out_of_scope_zh() -> str:
    topics = list_reviewed_topic_titles()
    topic_line = "、".join(topics[:12]) if topics else "（暂无）"
    return (
        "该问题超出当前政策知识库范围，我无法据此给出可靠答复。\n\n"
        f"**当前已覆盖主题**：{topic_line}。\n\n"
        "如需具体年度税额或汇率，请上传富途税表后提问「测算某年税额」或「某年汇率依据」。"
    )


def _collect_card_numerics(cards: list[KnowledgeCard]) -> set[str]:
    nums: set[str] = set()
    for c in cards:
        for m in re.finditer(r"(?<!\d)(20\d{2})(?!\d)", c.answer_t0):
            nums.add(m.group(1))
        for m in re.finditer(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日", c.answer_t0):
            nums.add(f"{m.group(1)}月{m.group(2)}日")
        if "20%" in c.answer_t0:
            nums.add("20")
    return nums


def build_policy_qa_fact_bundle(
    cards: list[KnowledgeCard],
    *,
    fallback_markdown: str,
    tax_year: int | None = None,
    has_dataset: bool = False,
    journey_phase: str | None = None,
    out_of_scope: bool = False,
) -> FactBundle:
    citations: list[PolicyCitation] = []
    for c in cards:
        citations.extend(c.citation_objects())
    seen: set[str] = set()
    deduped: list[PolicyCitation] = []
    for cit in citations:
        if cit.id in seen:
            continue
        seen.add(cit.id)
        deduped.append(cit)

    facts: dict[str, Any] = {
        "outOfScope": out_of_scope,
        "cards": [
            {
                "id": c.id,
                "title": c.title_zh,
                "answerT0": c.answer_t0,
                "citations": list(c.citations),
            }
            for c in cards
        ],
    }
    return FactBundle(
        profile="policy_qa",
        facts=facts,
        numerics=_collect_card_numerics(cards),
        citations=deduped,
        fallback_markdown=fallback_markdown,
        tier="T0",
        journey_phase=journey_phase,
        tax_year=tax_year,
        has_dataset=has_dataset,
    )


def try_policy_qa_fast_turn(message: str, ctx: Any) -> Any | None:
    from tax_agent.chat_orchestrator import ChatTurnResult
    from tax_agent.harness_plan import build_filing_turn_plan
    from tax_agent.session_turn_focus import revive_tax_session_focus

    sid = getattr(ctx, "session_id", None) or ""
    focus = revive_tax_session_focus(sid, message) if sid else None

    plan = build_filing_turn_plan(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(getattr(ctx, "dataset_id", None)),
        has_compute=bool(getattr(ctx, "last_run_id", None) or getattr(ctx, "last_summary", None)),
        episodic_profile=focus.focus_profile if focus else None,
    )
    if plan.profile != "policy_qa":
        return None

    cards = retrieve_top_cards(message, limit=2)
    out_of_scope = not cards
    if out_of_scope:
        reply = format_policy_kb_out_of_scope_zh()
        bundle = build_policy_qa_fact_bundle(
            [],
            fallback_markdown=reply,
            tax_year=plan.tax_year,
            has_dataset=bool(getattr(ctx, "dataset_id", None)),
            journey_phase=plan.journey_phase,
            out_of_scope=True,
        )
    else:
        reply = format_policy_kb_reply_zh(cards)
        bundle = build_policy_qa_fact_bundle(
            cards,
            fallback_markdown=reply,
            tax_year=plan.tax_year,
            has_dataset=bool(getattr(ctx, "dataset_id", None)),
            journey_phase=plan.journey_phase,
        )

    ctx.policy_kb_cards = [
        {"id": c.id, "title": c.title_zh, "answerT0": c.answer_t0} for c in cards
    ]
    return ChatTurnResult(reply=reply, action="none", fact_bundle=bundle)
