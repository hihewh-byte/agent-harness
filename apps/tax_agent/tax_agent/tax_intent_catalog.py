"""Schema-driven tax chat intent catalog (PHA schema_intent_router 报税版)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "rules" / "tax_intent_catalog.yaml"

_CASUAL_SUFFIX_RE = re.compile(r"[\s!！。.?？~]*$", re.I)


def token_in_message(token: str, user_message: str, *, case_insensitive: bool = True) -> bool:
    t = (token or "").strip()
    msg = user_message or ""
    if not t or not msg:
        return False
    if case_insensitive and t.isascii():
        return t.lower() in msg.lower()
    return t in msg


@lru_cache(maxsize=1)
def load_tax_intent_catalog() -> dict[str, Any]:
    data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    return data


def catalog_multi_scope_tokens() -> list[str]:
    cat = load_tax_intent_catalog()
    return list((cat.get("multi_scope") or {}).get("tokens") or [])


def catalog_anaphora_tokens() -> list[str]:
    cat = load_tax_intent_catalog()
    return list((cat.get("anaphora") or {}).get("tokens") or [])


def catalog_topic_markers(topic: str) -> list[str]:
    cat = load_tax_intent_catalog()
    markers = (cat.get("topic_markers") or {}).get(topic) or []
    return [str(m) for m in markers]


def matches_multi_scope(message: str) -> bool:
    msg = (message or "").strip()
    for tok in catalog_multi_scope_tokens():
        if token_in_message(tok, msg):
            return True
    return False


def matches_anaphora(message: str) -> bool:
    msg = (message or "").strip()
    for tok in catalog_anaphora_tokens():
        if token_in_message(tok, msg):
            return True
    return False


def _score_triggers(message: str, triggers: list[dict[str, Any]]) -> float:
    score = 0.0
    for rule in triggers or []:
        if not isinstance(rule, dict):
            continue
        token = str(rule.get("token") or "").strip()
        if token and token_in_message(token, message):
            score += float(rule.get("weight") or 1.0)
    return score


def _score_trigger_groups(message: str, groups: dict[str, list]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, rules in (groups or {}).items():
        out[name] = _score_triggers(message, rules if isinstance(rules, list) else [])
    return out


def _is_casual(message: str, profile_def: dict[str, Any]) -> bool:
    text = (message or "").strip()
    if not text or len(text) > 40:
        return False
    for raw in profile_def.get("exact_triggers") or []:
        tok = str(raw).strip()
        if not tok:
            continue
        pat = re.compile(
            rf"^{re.escape(tok)}{_CASUAL_SUFFIX_RE.pattern}",
            re.I,
        )
        if pat.match(text):
            return True
    return False


def score_profile(
    message: str,
    profile_id: str,
    profile_def: dict[str, Any],
    *,
    has_dataset: bool,
    episodic_profile: str | None = None,
) -> float:
    if profile_id == "casual":
        return 100.0 if _is_casual(message, profile_def) else -1.0

    if profile_id == "policy_qa":
        from tax_agent.policy_kb import policy_question_off_kb_score, score_knowledge_cards

        kb_score, _ = score_knowledge_cards(message)
        if kb_score > 0:
            return kb_score
        off_kb = policy_question_off_kb_score(message)
        if off_kb > 0:
            return off_kb
        return -1.0

    if profile_def.get("requires_no_dataset") and has_dataset:
        return -1.0

    if profile_def.get("requires_dataset") and not has_dataset:
        return -1.0

    score = _score_triggers(message, profile_def.get("triggers") or [])

    groups = profile_def.get("trigger_groups")
    if groups:
        gs = _score_trigger_groups(message, groups)
        any_group = profile_def.get("match_any_group")
        if any_group and gs.get(any_group, 0) > 0:
            score += gs[any_group]
            for sub in profile_def.get("also_match_substrings") or []:
                if str(sub) in message:
                    score += 1.0

    requires_all = profile_def.get("requires_all_groups")
    if requires_all and groups:
        gs = _score_trigger_groups(message, groups)
        if all(gs.get(g, 0) > 0 for g in requires_all):
            score = sum(gs.get(g, 0) for g in requires_all) + 5.0
        else:
            return -1.0

    if profile_def.get("episodic_continue") and episodic_profile == profile_id:
        if matches_anaphora(message):
            score += 10.0

    if profile_id == "general":
        return 0.0

    return score


def _episodic_inherits_topic(message: str, episodic_profile: str | None) -> bool:
    if not episodic_profile:
        return False
    if matches_anaphora(message):
        return True
    from tax_agent.tax_turn_resolver import anaphora_shift_year

    if anaphora_shift_year(message, [2020]):
        return True
    return False


def resolve_profile_from_catalog(
    message: str,
    *,
    has_dataset: bool = False,
    episodic_profile: str | None = None,
) -> tuple[str, float, dict[str, float]]:
    """Return (profile_id, winning_score, all_scores)."""
    if _episodic_inherits_topic(message, episodic_profile):
        return episodic_profile or "general", 100.0, {episodic_profile or "general": 100.0}

    cat = load_tax_intent_catalog()
    profiles: dict[str, Any] = cat.get("profiles") or {}
    scores: dict[str, float] = {}
    for pid, pdef in profiles.items():
        if not isinstance(pdef, dict):
            continue
        scores[pid] = score_profile(
            message,
            pid,
            pdef,
            has_dataset=has_dataset,
            episodic_profile=episodic_profile,
        )

    ranked = sorted(
        ((pid, sc) for pid, sc in scores.items() if sc > 0),
        key=lambda x: (
            -x[1],
            int((profiles.get(x[0]) or {}).get("priority") or 999),
        ),
    )
    if not ranked:
        return "general", 0.0, scores
    return ranked[0][0], ranked[0][1], scores


def profile_catalog_meta(profile_id: str) -> dict[str, Any]:
    cat = load_tax_intent_catalog()
    return dict((cat.get("profiles") or {}).get(profile_id) or {})
