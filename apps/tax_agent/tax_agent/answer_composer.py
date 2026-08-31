"""GroundedAnswerComposer — T0 facts + LLM narration + audit + followUps (v2 C1)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterator

import yaml

from tax_agent.citation_audit import audit_policy_citations
from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.fact_bundle import FactBundle
from tax_agent.llm_model_resolver import resolve_tax_agent_model
from tax_agent.numerics_audit import audit_response_numerics
from tax_agent.ollama_memory import prepare_ollama_for_tax
from tax_agent.pha_llm import (
    chat_completion_messages,
    import_ollama_provider,
    iter_chat_completion_messages,
    ollama_base_url,
)

_STYLES_PATH = Path(__file__).resolve().parent.parent / "rules" / "narration_styles.yaml"

# C5 harness contract — external fallbackReason values only.
FALLBACK_REASONS = frozenset(
    {"timeout", "audit_numerics", "audit_citation", "llm_unavailable", "none"}
)
LONG_REPLY_PROFILES = frozenset({"filing_narrative", "guided_filing"})
DEFAULT_MAX_REPLY_CHARS = 500


class NarrationBudgetExceeded(Exception):
    """Raised when narration exceeds C5 time budget (stream path)."""

    def __init__(self, reason: str = "timeout") -> None:
        self.reason = reason
        super().__init__(reason)


def normalize_fallback_reason(raw: str | None, *, narrated: bool = False) -> str:
    """Map internal composer reasons to C5 harness enum."""
    if narrated:
        return "none"
    if not raw or raw == "none":
        return "none"
    if raw in FALLBACK_REASONS:
        return raw
    low = raw.lower()
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if raw in ("audit_numerics", "audit_citation"):
        return raw
    if raw in (
        "llm_unavailable",
        "composer_disabled",
        "no_bundle",
        "empty_narration",
        "template_style_rejected",
        "length_exceeded",
    ):
        return "llm_unavailable"
    if raw.startswith("narration_error"):
        return "timeout" if "timeout" in low else "llm_unavailable"
    return "llm_unavailable"


def long_reply_allowed(profile: str) -> bool:
    return profile in LONG_REPLY_PROFILES


def max_reply_chars_for_profile(profile: str, *, reply_verbosity: str = "normal") -> int:
    style = _profile_style(profile)
    base = int(style.get("max_chars") or 300)
    verb = (reply_verbosity or "normal").strip().lower()
    if verb == "brief":
        cap = int(base * 0.65)
        return min(cap, DEFAULT_MAX_REPLY_CHARS) if not long_reply_allowed(profile) else cap
    if verb == "detailed":
        if long_reply_allowed(profile):
            return int(base * 1.2)
        return min(int(base * 1.1), DEFAULT_MAX_REPLY_CHARS + 80)
    return base


def _reply_length_ok(drafted: str, profile: str, *, reply_verbosity: str = "normal") -> bool:
    limit = max_reply_chars_for_profile(profile, reply_verbosity=reply_verbosity)
    if long_reply_allowed(profile):
        return len(drafted) <= limit
    return len(drafted) <= min(limit, DEFAULT_MAX_REPLY_CHARS)


@dataclass
class ComposedReply:
    reply: str
    follow_ups: list[str]
    narrated: bool
    fallback_reason: str | None
    composer_meta: dict[str, Any]
    nba: str | None = None


def composer_enabled() -> bool:
    v = (os.environ.get("TAX_COMPOSER_ENABLED") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def narration_timeout_seconds() -> float:
    try:
        return float(os.environ.get("TAX_NARRATION_TIMEOUT_S", "45"))
    except ValueError:
        return 45.0


def narration_stream_first_token_s() -> float:
    try:
        return float(os.environ.get("TAX_NARRATION_STREAM_FIRST_TOKEN_S", "20"))
    except ValueError:
        return 20.0


def narration_stream_total_s() -> float:
    try:
        return float(os.environ.get("TAX_NARRATION_STREAM_TOTAL_S", "90"))
    except ValueError:
        return 90.0


def fact_bundle_fact_card(bundle: FactBundle) -> dict[str, Any]:
    card: dict[str, Any] = {
        "profile": bundle.profile,
        "tier": bundle.tier,
        "facts": bundle.facts,
        "citations": bundle.citations_dicts(),
        "numerics": sorted(bundle.merged_numerics()),
        "fallbackPreview": (bundle.fallback_markdown or "")[:400],
    }
    if bundle.profile == "insight_fast":
        facts = bundle.facts or {}
        ci = facts.get("classifiedIncome") or {}
        gt = facts.get("grandTotal") or {}
        highlights: list[dict[str, str]] = []
        if gt.get("netTaxDueCny"):
            highlights.append(
                {"label": "全税目应补", "value": str(gt["netTaxDueCny"]), "unit": "元"}
            )
        div = ci.get("dividend") or {}
        if div.get("netTaxDueCny"):
            highlights.append(
                {"label": "股息应补", "value": str(div["netTaxDueCny"]), "unit": "元"}
            )
        intr = ci.get("interest") or {}
        if intr.get("netTaxDueCny"):
            highlights.append(
                {"label": "利息应补", "value": str(intr["netTaxDueCny"]), "unit": "元"}
            )
        if highlights:
            card["highlights"] = highlights
    return card


@lru_cache(maxsize=1)
def load_narration_styles() -> dict[str, Any]:
    if not _STYLES_PATH.is_file():
        return {}
    return yaml.safe_load(_STYLES_PATH.read_text(encoding="utf-8")) or {}


def _profile_style(profile: str) -> dict[str, Any]:
    styles = load_narration_styles()
    profiles = styles.get("profiles") or {}
    return dict(profiles.get(profile) or profiles.get("policy_explain") or {})


def _disclaimer_text() -> str:
    styles = load_narration_styles()
    return str(styles.get("disclaimer") or "仅供参考，不构成税务意见。")


def _ensure_policy_citations(reply: str, bundle: FactBundle) -> str:
    """Deterministic T0 citation suffix for policy_qa when narration omitted labels."""
    if bundle.profile != "policy_qa":
        return reply
    cites = bundle.citations_dicts()
    if not cites:
        return reply
    from tax_agent.citation_audit import audit_policy_citations

    if audit_policy_citations(reply, cites).ok:
        return reply
    primary = str(cites[0].get("label") or "").strip()
    if not primary:
        return reply
    suffix = f"\n\n依据【{primary}】。"
    if suffix.strip() in (reply or ""):
        return reply
    return (reply or "").rstrip() + suffix


def _ensure_footer(reply: str, bundle: FactBundle) -> str:
    out = (reply or "").strip()
    disc = _disclaimer_text()
    if disc and disc not in out:
        out = f"{out}\n\n{disc}"
    style = _profile_style(bundle.profile)
    tier_footer = style.get("tier_footer_t0") or ""
    if bundle.tier == "T0" and tier_footer and tier_footer not in out:
        out = f"{out}\n\n{tier_footer}"
    elif bundle.tier == "T1" and "辅助口径" not in out:
        out = f"{out}\n\n（辅助口径，不计入申报）"
    return out


def build_follow_ups(bundle: FactBundle) -> list[str]:
    style = _profile_style(bundle.profile)
    templates = list(style.get("follow_ups") or [])
    year = bundle.tax_year or 0
    next_year = year + 1 if year else ""
    ctx = {
        "tax_year": year,
        "next_year": next_year,
        "has_dataset": bundle.has_dataset,
    }
    out: list[str] = []
    for tpl in templates:
        try:
            text = str(tpl).format(**ctx).strip()
        except (KeyError, ValueError):
            text = str(tpl).strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= 3:
            break
    while len(out) < 3:
        fillers = [
            f"测算 {year} 年税额" if year else "测算税额",
            "材料覆盖完整吗",
            "生成申报数据表",
        ]
        for f in fillers:
            if f not in out:
                out.append(f)
            if len(out) >= 3:
                break
    return out[:3]


def _build_narration_messages(
    bundle: FactBundle,
    *,
    user_message: str,
    episodic_block: str = "",
    reply_verbosity: str = "normal",
) -> list[dict[str, str]]:
    style = _profile_style(bundle.profile)
    instructions = (style.get("instructions") or "").strip()
    max_chars = max_reply_chars_for_profile(bundle.profile, reply_verbosity=reply_verbosity)
    facts_json = json.dumps(bundle.facts, ensure_ascii=False, indent=2)
    cites = json.dumps(bundle.citations_dicts(), ensure_ascii=False)
    user_parts = [
        f"用户问题：{user_message}",
        f"【事实 JSON】\n{facts_json}",
        f"【可引用法条 citations】\n{cites}",
        f"字数上限：{max_chars} 字",
    ]
    if bundle.profile == "policy_qa" and bundle.citations:
        labels = [c.label for c in bundle.citations if c.label]
        if labels:
            user_parts.append(
                "必须在正文中写出至少一条依据，格式：依据【"
                + labels[0]
                + "】（使用 citations 中 label 原文，勿改字）。"
            )
    if episodic_block:
        user_parts.insert(1, episodic_block.strip())
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def iter_narrate_with_llm(
    bundle: FactBundle,
    *,
    user_message: str,
    episodic_block: str = "",
    model_override: str | None = None,
    reply_verbosity: str = "normal",
) -> Iterator[str]:
    resolution = resolve_tax_agent_model(override=model_override)
    if not resolution.model:
        return
    prepare_ollama_for_tax(keep_model=resolution.model)
    OllamaProvider = import_ollama_provider()
    provider = OllamaProvider(
        base_url=ollama_base_url(),
        model=resolution.model,
        timeout_seconds=narration_stream_total_s(),
    )
    messages = _build_narration_messages(
        bundle,
        user_message=user_message,
        episodic_block=episodic_block,
        reply_verbosity=reply_verbosity,
    )
    started = time.monotonic()
    first_token_deadline = started + narration_stream_first_token_s()
    got_token = False
    for delta in iter_chat_completion_messages(provider, messages=messages):
        if not got_token:
            if time.monotonic() > first_token_deadline:
                raise NarrationBudgetExceeded("timeout")
            got_token = True
        if time.monotonic() - started > narration_stream_total_s():
            raise NarrationBudgetExceeded("timeout")
        if delta:
            yield delta


def narrate_with_llm(
    bundle: FactBundle,
    *,
    user_message: str,
    episodic_block: str = "",
    model_override: str | None = None,
    reply_verbosity: str = "normal",
) -> tuple[str | None, str]:
    """Returns (text, reason_if_failed)."""
    resolution = resolve_tax_agent_model(override=model_override)
    if not resolution.model:
        return None, "llm_unavailable"
    try:
        prepare_ollama_for_tax(keep_model=resolution.model)
        OllamaProvider = import_ollama_provider()
        provider = OllamaProvider(
            base_url=ollama_base_url(),
            model=resolution.model,
            timeout_seconds=narration_timeout_seconds(),
        )
        raw = chat_completion_messages(
            provider,
            messages=_build_narration_messages(
                bundle,
                user_message=user_message,
                episodic_block=episodic_block,
                reply_verbosity=reply_verbosity,
            ),
            json_mode=False,
        )
        text = (raw or "").strip()
        if not text:
            return None, "empty_narration"
        if text.startswith("##"):
            return None, "template_style_rejected"
        return text, ""
    except Exception as exc:
        low = str(exc).lower()
        if "timeout" in low or "timed out" in low:
            return None, "timeout"
        return None, f"narration_error:{exc}"


def compose_grounded_reply(
    bundle: FactBundle,
    *,
    user_message: str,
    episodic_block: str = "",
    llm_on: bool = True,
    model_override: str | None = None,
    narrate_fn: Callable[..., tuple[str | None, str]] | None = None,
    reply_verbosity: str = "normal",
) -> ComposedReply:
    """L1 narration → L2 audit → L3 fallback → L4 followUps."""
    t0 = time.monotonic()
    follow_ups = build_follow_ups(bundle)
    fallback = bundle.fallback_markdown or ""
    meta: dict[str, Any] = {"profile": bundle.profile, "replyVerbosity": reply_verbosity}

    if not composer_enabled() or not llm_on:
        reason = "llm_unavailable"
        meta["fallbackReason"] = reason
        return ComposedReply(
            reply=fallback,
            follow_ups=follow_ups,
            narrated=False,
            fallback_reason=reason,
            composer_meta=meta,
        )

    narrate = narrate_fn or narrate_with_llm
    drafted, fail_reason = narrate(
        bundle,
        user_message=user_message,
        episodic_block=episodic_block,
        model_override=model_override,
        reply_verbosity=reply_verbosity,
    )
    if not drafted:
        reason = normalize_fallback_reason(fail_reason or "llm_unavailable")
        meta["fallbackReason"] = reason
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        return ComposedReply(
            reply=fallback,
            follow_ups=follow_ups,
            narrated=False,
            fallback_reason=reason,
            composer_meta=meta,
        )

    drafted = _ensure_policy_citations(drafted, bundle)

    if not _reply_length_ok(drafted, bundle.profile, reply_verbosity=reply_verbosity):
        meta["fallbackReason"] = "llm_unavailable"
        meta["lengthExceeded"] = True
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        return ComposedReply(
            reply=fallback,
            follow_ups=follow_ups,
            narrated=False,
            fallback_reason="llm_unavailable",
            composer_meta=meta,
        )

    manifest = bundle.merged_numerics()
    num_audit = audit_response_numerics(drafted, manifest, strict=True)
    cite_audit = audit_policy_citations(drafted, bundle.citations_dicts())

    if not num_audit.ok and cite_audit.ok and bundle.profile in ("policy_explain", "insight_fast"):
        retry_msg = f"{user_message}\n（仅使用事实 JSON 中的数字，不要写月日或额外年份。）"
        drafted2, _ = narrate(
            bundle,
            user_message=retry_msg,
            episodic_block=episodic_block,
            model_override=model_override,
            reply_verbosity=reply_verbosity,
        )
        if drafted2 and not drafted2.startswith("##"):
            drafted2 = _ensure_policy_citations(drafted2.strip(), bundle)
            if _reply_length_ok(drafted2, bundle.profile, reply_verbosity=reply_verbosity):
                na2 = audit_response_numerics(drafted2, manifest, strict=True)
                ca2 = audit_policy_citations(drafted2, bundle.citations_dicts())
                if na2.ok and ca2.ok:
                    drafted = drafted2
                    num_audit, cite_audit = na2, ca2
                    meta["numericsRetried"] = True

    meta["numericsAudit"] = num_audit.to_dict()
    meta["citationAudit"] = cite_audit.to_dict()

    if not num_audit.ok or not cite_audit.ok:
        reason = "audit_numerics" if not num_audit.ok else "audit_citation"
        meta["fallbackReason"] = reason
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        return ComposedReply(
            reply=fallback,
            follow_ups=follow_ups,
            narrated=False,
            fallback_reason=reason,
            composer_meta=meta,
        )

    final = _ensure_footer(drafted, bundle)
    meta.update({"narrated": True, "fallbackReason": "none", "auditMs": int((time.monotonic() - t0) * 1000)})
    return ComposedReply(
        reply=final,
        follow_ups=follow_ups,
        narrated=True,
        fallback_reason=None,
        composer_meta=meta,
    )


def stream_compose_grounded_reply(
    bundle: FactBundle,
    *,
    user_message: str,
    episodic_block: str = "",
    llm_on: bool = True,
    model_override: str | None = None,
    stream_fn: Callable[..., Iterator[str]] | None = None,
    reply_verbosity: str = "normal",
) -> Iterator[tuple[str, Any]]:
    """Yield ('delta', str) then ('final', ComposedReply)."""
    t0 = time.monotonic()
    follow_ups = build_follow_ups(bundle)
    fallback = bundle.fallback_markdown or ""
    meta: dict[str, Any] = {"profile": bundle.profile, "replyVerbosity": reply_verbosity}

    if not composer_enabled() or not llm_on:
        reason = "llm_unavailable"
        meta["fallbackReason"] = reason
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason=reason,
                composer_meta=meta,
            ),
        )
        return

    streamer = stream_fn or iter_narrate_with_llm
    accumulated = ""
    try:
        for delta in streamer(
            bundle,
            user_message=user_message,
            episodic_block=episodic_block,
            model_override=model_override,
            reply_verbosity=reply_verbosity,
        ):
            accumulated += delta
            yield ("delta", delta)
    except NarrationBudgetExceeded as exc:
        reason = normalize_fallback_reason(exc.reason)
        meta["fallbackReason"] = reason
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason=reason,
                composer_meta=meta,
            ),
        )
        return
    except Exception as exc:
        reason = normalize_fallback_reason(f"narration_error:{exc}")
        meta["fallbackReason"] = reason
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason=reason,
                composer_meta=meta,
            ),
        )
        return

    if not accumulated.strip():
        meta["fallbackReason"] = "llm_unavailable"
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason="llm_unavailable",
                composer_meta=meta,
            ),
        )
        return

    drafted = _ensure_policy_citations(accumulated.strip(), bundle)
    if not _reply_length_ok(drafted, bundle.profile, reply_verbosity=reply_verbosity):
        meta["fallbackReason"] = "llm_unavailable"
        meta["lengthExceeded"] = True
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason="llm_unavailable",
                composer_meta=meta,
            ),
        )
        return

    if drafted.startswith("##"):
        meta["fallbackReason"] = "llm_unavailable"
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason="llm_unavailable",
                composer_meta=meta,
            ),
        )
        return

    manifest = bundle.merged_numerics()
    num_audit = audit_response_numerics(drafted, manifest, strict=True)
    cite_audit = audit_policy_citations(drafted, bundle.citations_dicts())
    meta["numericsAudit"] = num_audit.to_dict()
    meta["citationAudit"] = cite_audit.to_dict()

    if not num_audit.ok or not cite_audit.ok:
        reason = "audit_numerics" if not num_audit.ok else "audit_citation"
        meta["fallbackReason"] = reason
        meta["auditMs"] = int((time.monotonic() - t0) * 1000)
        yield (
            "final",
            ComposedReply(
                reply=fallback,
                follow_ups=follow_ups,
                narrated=False,
                fallback_reason=reason,
                composer_meta=meta,
            ),
        )
        return

    final = _ensure_footer(drafted, bundle)
    meta.update({"narrated": True, "fallbackReason": "none", "auditMs": int((time.monotonic() - t0) * 1000)})
    yield (
        "final",
        ComposedReply(
            reply=final,
            follow_ups=follow_ups,
            narrated=True,
            fallback_reason=None,
            composer_meta=meta,
        ),
    )


def finalize_turn_with_composer(
    turn: ChatTurnResult,
    *,
    user_message: str,
    episodic_block: str = "",
    llm_on: bool = True,
    model_override: str | None = None,
    narrate_fn: Callable[..., tuple[str | None, str]] | None = None,
    nba: str | None = None,
    reply_verbosity: str = "normal",
) -> tuple[ChatTurnResult, dict[str, Any]]:
    """Apply composer when turn carries a FactBundle; otherwise pass through."""
    if turn.fact_bundle is None:
        return turn, {"composer": {"narrated": False, "fallbackReason": "no_bundle"}}

    composed = compose_grounded_reply(
        turn.fact_bundle,
        user_message=user_message,
        episodic_block=episodic_block,
        llm_on=llm_on,
        model_override=model_override,
        narrate_fn=narrate_fn,
        reply_verbosity=reply_verbosity,
    )
    composed_nba = nba
    new_turn = ChatTurnResult(
        reply=composed.reply,
        action=turn.action,
        compute_params=turn.compute_params,
        fact_bundle=turn.fact_bundle,
        follow_ups=composed.follow_ups,
    )
    fb = normalize_fallback_reason(composed.fallback_reason, narrated=composed.narrated)
    composer_meta = {
        "narrated": composed.narrated,
        "fallbackReason": fb,
        **composed.composer_meta,
    }
    composer_meta["fallbackReason"] = fb
    if composed_nba:
        composer_meta["nba"] = composed_nba
    return new_turn, {"composer": composer_meta, "nba": composed_nba}
