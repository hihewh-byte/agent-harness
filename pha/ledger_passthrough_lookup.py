"""Runtime L0 lookup for unregistered zip-passthrough HK quantity types.

Chat path: catalog first; else unique match against stored ``HKQuantityTypeIdentifier*``
rows; cite via this-turn Numerics Manifest; else fail-closed. No Python metric-name
table. Promotion (daily / fact card / Shortcut) remains a separate registry card.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from pha.catalog_dch import token_in_message

_HK_QUANTITY_PREFIX = "HKQuantityTypeIdentifier"
_CAMEL_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]+|[0-9]+")
_WAREHOUSE_HINT_RE = re.compile(r"库里|warehouse|HKQuantityTypeIdentifier", re.I)
_CAMEL_IN_MSG_RE = re.compile(r"[A-Z][a-z]{2,}[A-Z][a-zA-Z]+")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{6,}")
_BOILERPLATE_RE = re.compile(
    r"查询|请问|一下|可穿戴|穿戴|库里|数据|样本|记录|怎么样|如何|多少|"
    r"最近|今日|昨天|今天|今晚|这周|本周|上周|近窗|近\s*\d+\s*天|"
    r"warehouse|wearable|please|query|check|look(?:ing)? at|look(?:ing)?|"
    r"what(?:'s| is)|tell me|recent|today|yesterday|last|week|month|"
    r"\bthe\b|\bmy\b|\bin\b|\bof\b|\bfor\b|\bi\b|"
    r"我|你|您",
    re.I,
)
_PUNCT_RE = re.compile(r"[的了吗呢啊呀？?。,.!！、]+")
_MIN_SINGLE_NEEDLE_LEN = 16


@dataclass(frozen=True)
class TurnWearableScope:
    """Resolved wearable fetch for this turn. Registry wins over ledger.

    ``unresolved_residue`` is telemetry / disclosure only: non-empty leftover
    after boilerplate strip when a metric entity already closed. It never
    alone triggers ``fail_closed_named`` (entity-first gate).
    """

    registry_ids: tuple[str, ...]
    ledger_types: tuple[str, ...]
    fail_closed_named: bool
    unresolved_residue: str = ""


@dataclass(frozen=True)
class LedgerSample:
    metric_type: str
    label: str
    value: float
    day: date


def hk_quantity_suffix(metric_type: str) -> str:
    raw = (metric_type or "").strip()
    if raw.startswith(_HK_QUANTITY_PREFIX):
        return raw[len(_HK_QUANTITY_PREFIX) :]
    return raw


def hk_quantity_camel_tokens(metric_type: str) -> tuple[str, ...]:
    suffix = hk_quantity_suffix(metric_type)
    return tuple(_CAMEL_TOKEN_RE.findall(suffix))


def hk_quantity_display_label(metric_type: str) -> str:
    tokens = hk_quantity_camel_tokens(metric_type)
    if tokens:
        return " ".join(tokens)
    suffix = hk_quantity_suffix(metric_type)
    return suffix or (metric_type or "").strip() or "wearable"


def hk_quantity_needles(metric_type: str) -> tuple[str, ...]:
    """Human-facing needles derived from the stored HK id. Longest-first unique match."""
    raw = (metric_type or "").strip()
    if not raw.startswith(_HK_QUANTITY_PREFIX):
        return ()
    tokens = hk_quantity_camel_tokens(raw)
    out: list[str] = []
    seen: set[str] = set()

    def _add(needle: str) -> None:
        n = (needle or "").strip()
        if not n:
            return
        key = n.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(n)

    _add(raw)
    if tokens:
        _add(" ".join(tokens))
        compact = "".join(tokens)
        if len(compact) >= _MIN_SINGLE_NEEDLE_LEN:
            _add(compact)
        n = len(tokens)
        for width in range(n, 1, -1):
            for i in range(0, n - width + 1):
                _add(" ".join(tokens[i : i + width]))
        for tok in tokens:
            if len(tok) >= _MIN_SINGLE_NEEDLE_LEN:
                _add(tok)
    return tuple(out)


def looks_like_specific_metric_utterance(message: str) -> bool:
    """Named-metric ask that must not fall back to core HRV/VO2max padding."""
    msg = (message or "").strip()
    if not msg:
        return False
    if _WAREHOUSE_HINT_RE.search(msg):
        return True
    if _CAMEL_IN_MSG_RE.search(msg):
        return True
    return len(_LATIN_WORD_RE.findall(msg)) >= 2


def utterance_residue(message: str) -> str:
    """Ask text with wearable/warehouse boilerplate stripped; leftover is the named span."""
    s = _BOILERPLATE_RE.sub(" ", message or "")
    s = _PUNCT_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _catalog_named_best_len(message: str) -> int:
    from pha.health_intent_catalog import catalog_all_metric_keys, catalog_metric_aliases
    from pha.wearable_metric_registry import metric_mention_hints

    msg = (message or "").strip()
    best = 0
    if not msg:
        return 0
    for key in catalog_all_metric_keys():
        for alias in catalog_metric_aliases(key):
            tok = str(alias or "").strip()
            if tok and token_in_message(tok, msg, case_insensitive=True):
                best = max(best, len(tok))
    for _mid, hints in metric_mention_hints().items():
        for h in hints:
            tok = (h or "").strip()
            if tok and token_in_message(tok, msg, case_insensitive=True):
                best = max(best, len(tok))
    return best


def _registered_zip_types() -> set[str]:
    from pha.wearable_metric_registry import zip_passthrough_rollups

    return set(zip_passthrough_rollups().keys())


def _score_ledger_types(user_id: str, message: str) -> tuple[int, tuple[str, ...]]:
    msg = (message or "").strip()
    if not msg:
        return 0, ()
    from pha.sqlite_storage import list_distinct_wearable_metric_types

    registered = _registered_zip_types()
    stored = [
        t
        for t in list_distinct_wearable_metric_types(user_id)
        if t.startswith(_HK_QUANTITY_PREFIX) and t not in registered
    ]
    if not stored:
        return 0, ()
    scored: list[tuple[int, str]] = []
    for hk in stored:
        best = 0
        for needle in hk_quantity_needles(hk):
            if token_in_message(needle, msg, case_insensitive=True):
                best = max(best, len(needle))
        if best:
            scored.append((best, hk))
    if not scored:
        return 0, ()
    max_len = max(n for n, _hk in scored)
    winners = tuple(hk for n, hk in scored if n == max_len)
    if len(winners) != 1:
        return max_len, ()
    return max_len, winners


def match_ledger_passthrough_types(user_id: str, message: str) -> tuple[str, ...]:
    """Unique stored unregistered HK quantity type whose derived needle hits the message."""
    _score, winners = _score_ledger_types(user_id, message)
    return winners


def _named_registry_metric_ids(message: str) -> tuple[str, ...]:
    """Catalog/hint/schema keyword hits only — never the 穿戴 default core dump."""
    from pha.catalog_dch import infer_wearable_metrics_from_schema
    from pha.health_intent_catalog import infer_metrics_from_message, message_names_unpromoted_metric
    from pha.universal_catalog_manager import get_catalog_manager
    from pha.wearable_metric_registry import (
        cluster_expand_enabled,
        cluster_members,
        cluster_of,
        cluster_primary_metric_id,
        hint_match_metric_ids,
        metric_entry,
        metric_ids_for_catalog_key,
        primary_metric_id_for_catalog_key,
    )

    msg = (message or "").strip()
    if not msg or message_names_unpromoted_metric(msg):
        return ()
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(mid: str) -> None:
        if mid and mid not in seen and metric_entry(mid):
            seen.add(mid)
            ordered.append(mid)

    for mid in hint_match_metric_ids(msg):
        _add(mid)
    hinted_clusters = {cluster_of(mid) for mid in ordered if cluster_of(mid)}
    keys: list[str] = list(infer_metrics_from_message(msg))
    doc = get_catalog_manager().get_asset("wearable_bundle") or {}
    keys.extend(
        infer_wearable_metrics_from_schema(
            msg,
            doc,
            default_if_wearable_query=False,
            has_lab_only=False,
        )
    )
    for key in keys:
        primary = primary_metric_id_for_catalog_key(key)
        key_cluster = cluster_of(primary) if primary else None
        if primary and key_cluster and key_cluster in hinted_clusters and primary not in seen:
            continue
        if primary:
            _add(primary)
        else:
            for mid in metric_ids_for_catalog_key(key):
                _add(mid)
    if cluster_expand_enabled():
        extra: list[str] = []
        for mid in list(ordered):
            cid = cluster_of(mid)
            if not cid:
                continue
            primary = cluster_primary_metric_id(cid)
            if primary and primary in seen:
                extra.extend(cluster_members(cid, expand_only=True))
        for mid in extra:
            _add(mid)
    return tuple(ordered)


def resolve_turn_wearable_scope(user_id: str, message: str) -> TurnWearableScope:
    """Entity-first scope: closed metric slots beat leftover natural-language residue.

    Fail-closed only when no catalog/ledger entity resolved and residue is
    non-empty (named-unknown / P21c anti-padding). Compare/aspect leftovers
    like 「跟昨天比」「有什么变化」 do not veto a resolved ``hrv_sdnn_ms``.
    """
    msg = (message or "").strip()
    if not msg:
        return TurnWearableScope((), (), False)
    cat_len = _catalog_named_best_len(msg)
    led_len, ledger = _score_ledger_types(user_id, msg)
    residue = utterance_residue(msg)
    leftover = residue if residue else ""
    # Longer unique HK needle wins over a shorter catalog alias (zip L0).
    if led_len > cat_len and ledger:
        return TurnWearableScope((), ledger, False, leftover)
    named = _named_registry_metric_ids(msg)
    if named:
        return TurnWearableScope(named, (), False, leftover)
    if ledger:
        return TurnWearableScope((), ledger, False, leftover)
    if residue:
        return TurnWearableScope((), (), True)
    return TurnWearableScope((), (), False)


def core_fallback_metric_ids() -> list[str]:
    from pha.wearable_metric_registry import catalog_keys_core, primary_metric_id_for_catalog_key

    return [
        mid
        for key in catalog_keys_core()[:2]
        if (mid := primary_metric_id_for_catalog_key(key))
    ]


def registry_metric_ids_for_turn(user_id: str, message: str) -> list[str]:
    """Ids to fetch from daily/health_data. Empty when ledger-only or named fail-closed."""
    scope = resolve_turn_wearable_scope(user_id, message)
    if scope.ledger_types or scope.fail_closed_named:
        return []
    if scope.registry_ids:
        return list(scope.registry_ids)
    return core_fallback_metric_ids()


def fold_ledger_samples(
    user_id: str,
    hk_types: Sequence[str],
    *,
    win_start: date,
    win_end: date,
    named_days: Sequence[date] = (),
    latest_fallback: bool = False,
) -> list[LedgerSample]:
    from pha.sqlite_storage import query_latest_wearable_sample, query_wearable_data_range

    uid = (user_id or "default").strip() or "default"
    out: list[LedgerSample] = []
    for hk in hk_types:
        label = hk_quantity_display_label(hk)
        if named_days:
            for day in named_days:
                rows = query_wearable_data_range(uid, hk, day, day)
                if not rows:
                    continue
                _d, val = rows[-1]
                out.append(LedgerSample(hk, label, float(val), day))
            continue
        rows = query_wearable_data_range(uid, hk, win_start, win_end)
        if rows:
            day, val = rows[-1]
            out.append(LedgerSample(hk, label, float(val), day))
            continue
        if not latest_fallback:
            continue
        latest = query_latest_wearable_sample(uid, hk)
        if latest is None:
            continue
        ts, val = latest
        from pha.date_parser import safe_parse_date

        day = safe_parse_date(ts) or win_end
        out.append(LedgerSample(hk, label, float(val), day))
    return out


__all__ = [
    "LedgerSample",
    "TurnWearableScope",
    "core_fallback_metric_ids",
    "fold_ledger_samples",
    "hk_quantity_camel_tokens",
    "hk_quantity_display_label",
    "hk_quantity_needles",
    "hk_quantity_suffix",
    "looks_like_specific_metric_utterance",
    "match_ledger_passthrough_types",
    "registry_metric_ids_for_turn",
    "resolve_turn_wearable_scope",
    "utterance_residue",
]
