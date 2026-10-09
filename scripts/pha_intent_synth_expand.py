#!/usr/bin/env python3
"""Stage 1 — offline synthetic alias expansion for wearable intent recall.

Subcommands (run in order; every step writes under ``reports/intent_synth/``):

  synth  — local Qwen generates per-metric train utterances + candidate cores,
           holdout utterances (no official names) and negative utterances
           (feelings / symptoms without a metric). Spec: rules/intent_synth_spec.json
  gate   — admission gates on candidate cores: 1E-a/b/c/d via
           ``classify_alias_phrase``, live-resolver cross-hit, cross-metric
           utterance hijack, negative-corpus hit, batch dup,
           ``validate_alias_proposals`` (catalog + schema layers).
  eval   — recall on holdout / train utterances and false-bind rate on
           negatives, using the real resolvers on current disk state.
  apply  — append cores that are both gate-accepted and listed in the human
           ``--review`` file to registry ``intent_hints`` and catalog
           ``metric_aliases`` (plus catalog lists that already mirror that key's
           aliases), regenerate wearable_bundle schema, run keyword-conflict
           detection; roll back on hard conflict.
  regress — freeze holdout direct hits + unbound negatives into
           ``rules/intent_synth_regression.json`` (guarded by the selfcheck).

No online path change: runtime still matches declarative catalog/registry tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_HEALTH_INTENT_CATALOG", "1")

SPEC_PATH = ROOT / "rules" / "intent_synth_spec.json"
CATALOG_PATH = ROOT / "rules" / "health_intent_catalog.json"
REGISTRY_PATH = ROOT / "storage" / "registry" / "wearable_metric_registry.json"
SCHEMA_PATH = ROOT / "storage" / "schemas" / "wearable_bundle.schema.json"
OUT_DIR = ROOT / "reports" / "intent_synth"

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_EDGE_PUNCT_RE = re.compile(r"^[\s\"'“”‘’。，、？！?!.,:;：；()（）\[\]]+|[\s\"'“”‘’。，、？！?!.,:;：；()（）\[\]]+$")


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_spec() -> dict[str, Any]:
    return _load_json(SPEC_PATH)


def _norm(text: str) -> str:
    return _EDGE_PUNCT_RE.sub("", (text or "").strip()).lower()


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", _norm(text))


def _is_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _contains(token: str, message: str) -> bool:
    t = (token or "").strip()
    if not t or not message:
        return False
    if _is_cjk(t):
        return t in message
    return t.lower() in message.lower()


# --------------------------------------------------------------------------- registry view


def eligible_metrics() -> list[dict[str, Any]]:
    """Non-hidden registry metrics with a catalog key (the chat-resolvable set)."""
    doc = _load_json(REGISTRY_PATH)
    out: list[dict[str, Any]] = []
    for m in doc.get("metrics") or []:
        if not isinstance(m, dict) or not m.get("metric_id"):
            continue
        cat = m.get("catalog") or {}
        if cat.get("hidden") or not str(cat.get("key") or "").strip():
            continue
        ui = m.get("ui") or {}
        fc = m.get("fact_card") or {}
        snap = m.get("snapshot") or {}
        out.append(
            {
                "metric_id": str(m["metric_id"]),
                "key": str(cat["key"]),
                "cluster": str(cat.get("cluster") or m["metric_id"]),
                "label_zh": str(ui.get("label_zh") or cat.get("label_zh") or ""),
                "label_en": str(ui.get("label_en") or cat.get("label_en") or ""),
                "group_zh": str(ui.get("group_zh") or ""),
                "unit": str(fc.get("unit") or snap.get("unit") or ""),
                "hints": [str(h) for h in (m.get("intent_hints") or []) if str(h).strip()],
            }
        )
    return out


# --------------------------------------------------------------------------- synth (LLM)


def _ollama_chat_json(
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    temperature: float,
    timeout: float,
) -> dict[str, Any]:
    import httpx

    from pha.ollama_payload import apply_ollama_options

    os.environ.setdefault("OLLAMA_THINK", "false")
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    body = apply_ollama_options(
        {
            "model": model,
            "stream": False,
            "format": schema,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    )
    resp = httpx.post(f"{base}/api/chat", json=body, timeout=timeout)
    resp.raise_for_status()
    content = ((resp.json() or {}).get("message") or {}).get("content") or ""
    return json.loads(content)


_UTTER_SCHEMA = {
    "type": "object",
    "properties": {
        "utterances": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["utterances"],
}

_TRAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "utterances": {"type": "array", "items": {"type": "string"}},
        "cores": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["utterances", "cores"],
}

_SYSTEM = (
    "You generate evaluation data for a personal health app intent router. "
    "Output only the requested JSON. Write natural, varied phrasing; no numbering, no duplicates."
)


def _locale_label(locale: str) -> str:
    return "Simplified Chinese" if locale == "zh" else "English"


def _metric_brief(metric: dict[str, Any], siblings: list[dict[str, Any]]) -> str:
    sib = "; ".join(f"{s['label_zh']} / {s['label_en']}" for s in siblings if s["metric_id"] != metric["metric_id"])
    return (
        f"Metric: {metric['label_zh']} / {metric['label_en']}"
        + (f" (group: {metric['group_zh']})" if metric["group_zh"] else "")
        + (f", unit {metric['unit']}" if metric["unit"] else "")
        + f"\nExisting hints (already handled, do not repeat): {', '.join(metric['hints'])}"
        + f"\nSibling metrics in the same app (cores must NOT be ambiguous with these): {sib}"
    )


def cmd_synth(args: argparse.Namespace) -> int:
    spec = load_spec()
    model = args.model or spec["model"]
    temp = float(spec.get("temperature") or 0.8)
    timeout = float(spec.get("timeout_seconds") or 300)
    metrics = eligible_metrics()
    if args.only:
        wanted = set(args.only.split(","))
        metrics = [m for m in metrics if m["metric_id"] in wanted]
    all_metrics = eligible_metrics()
    tag = args.tag or _now_tag()
    out_path = OUT_DIR / f"synth_{tag}.json"
    doc: dict[str, Any] = (
        _load_json(out_path)
        if out_path.is_file()
        else {"schema": "pha.intent_synth/v1", "tag": tag, "model": model, "metrics": {}, "negatives": {}}
    )
    t0 = time.time()

    for locale in spec["locales"]:
        if doc["negatives"].get(locale):
            continue
        neg = spec["negatives"]
        user = (
            f"{neg['instruction']}\nLanguage: {_locale_label(locale)}.\n"
            f"Return JSON {{\"utterances\": [...]}} with {neg['utterances_per_locale']} items."
        )
        try:
            res = _ollama_chat_json(model=model, system=_SYSTEM, user=user, schema=_UTTER_SCHEMA, temperature=temp, timeout=timeout)
            doc["negatives"][locale] = [str(u).strip() for u in res.get("utterances") or [] if str(u).strip()]
        except Exception as exc:  # noqa: BLE001
            print(f"WARN negatives {locale}: {exc}")
        _dump_json(out_path, doc)
        print(f"[{time.time() - t0:6.0f}s] negatives {locale}: {len(doc['negatives'].get(locale) or [])}")

    for metric in metrics:
        mid = metric["metric_id"]
        entry = doc["metrics"].setdefault(mid, {"key": metric["key"], "cluster": metric["cluster"], "train": {}, "holdout": {}})
        brief = _metric_brief(metric, all_metrics)
        for locale in spec["locales"]:
            if not entry["train"].get(locale):
                tr = spec["train"]
                user = (
                    f"{brief}\n\n{tr['instruction']}\n{spec['core_rules']}\nLanguage: {_locale_label(locale)}.\n"
                    f"Return JSON with {tr['utterances_per_locale']} utterances and {tr['cores_per_locale']} cores."
                )
                try:
                    res = _ollama_chat_json(model=model, system=_SYSTEM, user=user, schema=_TRAIN_SCHEMA, temperature=temp, timeout=timeout)
                    entry["train"][locale] = {
                        "utterances": [str(u).strip() for u in res.get("utterances") or [] if str(u).strip()],
                        "cores": [str(c).strip() for c in res.get("cores") or [] if str(c).strip()],
                    }
                except Exception as exc:  # noqa: BLE001
                    print(f"WARN train {mid} {locale}: {exc}")
                _dump_json(out_path, doc)
            if not entry["holdout"].get(locale):
                ho = spec["holdout"]
                user = (
                    f"{brief}\n\n{ho['instruction']}\nLanguage: {_locale_label(locale)}.\n"
                    f"Return JSON {{\"utterances\": [...]}} with {ho['utterances_per_locale']} items."
                )
                try:
                    res = _ollama_chat_json(model=model, system=_SYSTEM, user=user, schema=_UTTER_SCHEMA, temperature=temp, timeout=timeout)
                    entry["holdout"][locale] = [str(u).strip() for u in res.get("utterances") or [] if str(u).strip()]
                except Exception as exc:  # noqa: BLE001
                    print(f"WARN holdout {mid} {locale}: {exc}")
                _dump_json(out_path, doc)
        print(f"[{time.time() - t0:6.0f}s] {mid} done")

    print(f"Wrote {out_path}")
    return 0


# --------------------------------------------------------------------------- resolvers


def _reset_runtime_caches() -> None:
    from pha.health_intent_catalog import load_health_intent_catalog
    from pha.universal_catalog_manager import reload_catalog_manager
    from pha.wearable_metric_registry import clear_registry_cache

    load_health_intent_catalog.cache_clear()
    clear_registry_cache()
    reload_catalog_manager()


def resolve_ids(text: str, *, expand: bool = True) -> list[str]:
    """Runtime resolver: ``infer_wearable_metric_ids`` (core-bundle fallback + cluster expansion).

    ``expand=False`` returns direct token hits only (registry hints ∪ schema-trigger
    catalog keys), i.e. what the utterance itself names, without fallback/expansion.
    """
    if expand:
        from pha.intent_gates import infer_wearable_metric_ids

        return list(infer_wearable_metric_ids(text))

    from pha.catalog_dch import scan_trigger_keywords
    from pha.health_intent_catalog import message_names_unpromoted_metric
    from pha.universal_catalog_manager import get_catalog_manager
    from pha.wearable_metric_registry import cluster_of, hint_match_metric_ids, primary_metric_id_for_catalog_key

    if not text or message_names_unpromoted_metric(text):
        return []
    out: list[str] = list(hint_match_metric_ids(text))
    hinted = {cluster_of(m) for m in out if cluster_of(m)}
    doc = get_catalog_manager().get_asset("wearable_bundle") or {}
    _, keys = scan_trigger_keywords(text, doc.get("catalog") or {})
    for k in keys:
        primary = primary_metric_id_for_catalog_key(k)
        if primary and primary not in out and cluster_of(primary) not in hinted:
            out.append(primary)
    return out


def resolve_keys(text: str) -> list[str]:
    from pha.health_intent_catalog import infer_metrics_from_message

    return list(infer_metrics_from_message(text))


# --------------------------------------------------------------------------- gate


def _latest(prefix: str) -> Path | None:
    files = sorted(OUT_DIR.glob(f"{prefix}_*.json"))
    return files[-1] if files else None


def _core_shape_ok(core: str, spec: dict[str, Any]) -> str | None:
    if _is_cjk(core):
        if len(core) < 2:
            return "too_short"
        if len(core) > int(spec.get("core_max_len_cjk") or 6):
            return "too_long"
        return None
    if len(core) < int(spec.get("core_min_len_en") or 4):
        return "too_short"
    if len(core.split()) > int(spec.get("core_max_words_en") or 4):
        return "too_long"
    return None


def gate_candidates(
    synth: dict[str, Any],
    spec: dict[str, Any] | None = None,
    *,
    extra: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Run all admission gates over synth cores (+ reviewer ``extra``); each gets status + decision."""
    from pha.loop_keyword_conflicts import AliasProposal, classify_alias_phrase, validate_alias_proposals

    spec = spec or load_spec()
    gspec = spec.get("gate") or {}
    _reset_runtime_caches()
    metrics = {m["metric_id"]: m for m in eligible_metrics()}

    train_utts: list[tuple[str, str]] = []
    for mid, entry in (synth.get("metrics") or {}).items():
        for loc_doc in (entry.get("train") or {}).values():
            for u in loc_doc.get("utterances") or []:
                train_utts.append((mid, u))
    negatives = [u for us in (synth.get("negatives") or {}).values() for u in us]

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for mid, entry in (synth.get("metrics") or {}).items():
        if mid not in metrics:
            continue
        for locale, loc_doc in (entry.get("train") or {}).items():
            for raw in loc_doc.get("cores") or []:
                core = _EDGE_PUNCT_RE.sub("", str(raw).strip())
                if not core or (mid, core.lower()) in seen:
                    continue
                seen.add((mid, core.lower()))
                candidates.append({"metric_id": mid, "key": metrics[mid]["key"], "cluster": metrics[mid]["cluster"], "locale": locale, "source": "synth", "raw": raw, "core": core, "reasons": [], "warnings": []})
    for row in extra or []:
        mid, core = str(row.get("metric_id") or ""), _EDGE_PUNCT_RE.sub("", str(row.get("core") or "").strip())
        if mid not in metrics or not core or (mid, core.lower()) in seen:
            continue
        seen.add((mid, core.lower()))
        locale = "zh" if _is_cjk(core) else "en"
        candidates.append({"metric_id": mid, "key": metrics[mid]["key"], "cluster": metrics[mid]["cluster"], "locale": locale, "source": "reviewer", "raw": core, "core": core, "reasons": [], "warnings": []})

    for c in candidates:
        mid, key, core = c["metric_id"], c["key"], c["core"]
        shape = _core_shape_ok(core, spec)
        if shape:
            c["reasons"].append(f"shape:{shape}")
            continue
        live = resolve_ids(core, expand=False)
        if mid in live:
            c["status"] = "covered"
            continue
        foreign = [x for x in live if x != mid]
        if foreign:
            c["reasons"].append(f"core_cross_hit:{','.join(foreign)}")
        tier = classify_alias_phrase(core, metric_id=key)
        if tier.tier != "catalog" or _squash(tier.core_alias) != _squash(core):
            c["reasons"].append(f"tier:{tier.tier}:{';'.join(tier.reject_reasons)[:160]}")
        for other_mid, other in metrics.items():
            if other_mid != mid and any(_norm(h) == _norm(core) for h in other["hints"]):
                c["reasons"].append(f"registry_dup:{other_mid}")
        neg_hits = [u for u in negatives if _contains(core, u)]
        if neg_hits and gspec.get("reject_on_negative_hit", True):
            c["reasons"].append(f"negative_hit:{neg_hits[0][:40]}")
        own_support = sum(1 for umid, u in train_utts if umid == mid and _contains(core, u))
        min_support = int(gspec.get("min_own_train_support_cjk" if _is_cjk(core) else "min_own_train_support_en", 0))
        if own_support < min_support:
            c["reasons"].append(f"own_support:{own_support}<{min_support}")
        cross_cluster, same_cluster = [], []
        for umid, u in train_utts:
            if umid == mid or not _contains(core, u):
                continue
            ucl = metrics.get(umid, {}).get("cluster")
            (same_cluster if ucl == c["cluster"] else cross_cluster).append(f"{umid}:{u[:40]}")
        if cross_cluster and gspec.get("reject_on_cross_cluster_utterance_hit", True):
            c["reasons"].append(f"cross_cluster_utterance:{cross_cluster[0]}")
        if len(same_cluster) > int(gspec.get("max_same_cluster_utterance_hits", 1)):
            c["reasons"].append(f"same_cluster_utterance:{len(same_cluster)}:{same_cluster[0]}")
        elif same_cluster:
            c["warnings"].append(f"same_cluster_utterance:{same_cluster[0]}")

    live_cands = [c for c in candidates if c.get("status") != "covered" and not c["reasons"]]
    owners: dict[str, set[str]] = {}
    for c in live_cands:
        owners.setdefault(_norm(c["core"]), set()).add(c["metric_id"])
    for c in live_cands:
        if len(owners[_norm(c["core"])]) > 1:
            c["reasons"].append(f"batch_dup:{','.join(sorted(owners[_norm(c['core'])]))}")

    # validate_alias_proposals: iterate until the surviving batch is clean.
    for _ in range(5):
        survivors = [c for c in candidates if c.get("status") != "covered" and not c["reasons"]]
        props = []
        for c in survivors:
            props.append(AliasProposal(layer="catalog", target=c["key"], alias=c["core"], metric_id=c["key"]))
            props.append(AliasProposal(layer="schema", target="wearable_bundle", alias=c["core"], metric_id=c["key"]))
        report = validate_alias_proposals(props)
        if report.ok:
            break
        bad = {_norm(k.token): k.as_error() for k in report.conflicts}
        hit = False
        for c in survivors:
            if _norm(c["core"]) in bad:
                c["reasons"].append(f"validate:{bad[_norm(c['core'])][:160]}")
                hit = True
        if not hit:
            break

    for c in candidates:
        if c.get("status") == "covered":
            c["decision"] = "skip"
        elif c["reasons"]:
            c["status"] = "rejected"
            c["decision"] = "reject"
        else:
            c["status"] = "accepted"
            c["decision"] = "accept"
    return candidates


def cmd_gate(args: argparse.Namespace) -> int:
    synth_path = Path(args.synth).resolve() if args.synth else _latest("synth")
    if not synth_path or not synth_path.is_file():
        print("FAIL no synth file")
        return 1
    synth = _load_json(synth_path)
    extra = _load_json(Path(args.extra).resolve()) if args.extra else None
    candidates = gate_candidates(synth, extra=extra)

    tag = synth.get("tag") or _now_tag()
    out = {
        "schema": "pha.intent_synth_proposal/v1",
        "tag": tag,
        "synth": str(synth_path.relative_to(ROOT)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "candidates": len(candidates),
            "covered": sum(1 for c in candidates if c["status"] == "covered"),
            "accepted": sum(1 for c in candidates if c["status"] == "accepted"),
            "rejected": sum(1 for c in candidates if c["status"] == "rejected"),
        },
        "review_note": "Edit decision accept|reject before `apply`. Only decision=accept is written.",
        "candidates": candidates,
    }
    out_path = Path(args.out) if args.out else OUT_DIR / f"proposal_{tag}.json"
    _dump_json(out_path, out)
    print(json.dumps(out["summary"], ensure_ascii=False))
    for c in candidates:
        if c["status"] == "accepted":
            warn = f"  WARN {c['warnings'][0]}" if c["warnings"] else ""
            print(f"  ACCEPT {c['metric_id']:<28} {c['core']}{warn}")
    print(f"Wrote {out_path}")
    return 0


# --------------------------------------------------------------------------- eval


def evaluate(synth: dict[str, Any]) -> dict[str, Any]:
    _reset_runtime_caches()
    per_metric: dict[str, Any] = {}
    fields = ("precise_hit", "runtime_hit", "precise_misbind", "fallback_only", "catalog_key_hit", "total")
    agg = {split: dict.fromkeys(fields, 0) for split in ("holdout", "train")}
    misses: list[dict[str, str]] = []
    for mid, entry in (synth.get("metrics") or {}).items():
        row: dict[str, Any] = {}
        key = entry.get("key")
        for split in ("holdout", "train"):
            utts: list[str] = []
            for v in (entry.get(split) or {}).values():
                utts.extend(v if isinstance(v, list) else (v.get("utterances") or []))
            r = dict.fromkeys(fields, 0)
            for u in utts:
                precise = resolve_ids(u, expand=False)
                runtime = resolve_ids(u, expand=True)
                r["total"] += 1
                if mid in precise:
                    r["precise_hit"] += 1
                else:
                    if precise:
                        r["precise_misbind"] += 1
                    if split == "holdout":
                        misses.append({"metric_id": mid, "text": u, "precise": ",".join(precise), "runtime": ",".join(runtime)})
                if mid in runtime:
                    r["runtime_hit"] += 1
                if runtime and not precise:
                    r["fallback_only"] += 1
                if key in resolve_keys(u):
                    r["catalog_key_hit"] += 1
            row[split] = r
            for f in fields:
                agg[split][f] += r[f]
        per_metric[mid] = row
    negatives = [u for us in (synth.get("negatives") or {}).values() for u in us]
    neg_bound = []
    for u in negatives:
        got = resolve_ids(u, expand=False)
        if got:
            neg_bound.append({"text": u, "got": ",".join(got)})

    def _rate(a: int, b: int) -> float:
        return round(a / b, 4) if b else 0.0

    summary: dict[str, Any] = {
        split: {
            "precise_recall": _rate(a["precise_hit"], a["total"]),
            "runtime_recall": _rate(a["runtime_hit"], a["total"]),
            "precise_misbind_rate": _rate(a["precise_misbind"], a["total"]),
            "fallback_only_rate": _rate(a["fallback_only"], a["total"]),
            "catalog_key_recall": _rate(a["catalog_key_hit"], a["total"]),
            "total": a["total"],
        }
        for split, a in agg.items()
    }
    summary["negatives"] = {"false_bind_rate": _rate(len(neg_bound), len(negatives)), "bound": len(neg_bound), "total": len(negatives)}
    return {
        "summary": summary,
        "per_metric": per_metric,
        "negatives_bound": neg_bound,
        "holdout_misses": misses,
    }


def cmd_eval(args: argparse.Namespace) -> int:
    synth_path = Path(args.synth).resolve() if args.synth else _latest("synth")
    if not synth_path or not synth_path.is_file():
        print("FAIL no synth file")
        return 1
    synth = _load_json(synth_path)
    report = evaluate(synth)
    report["synth"] = str(synth_path.relative_to(ROOT))
    report["label"] = args.label
    out_path = OUT_DIR / f"eval_{synth.get('tag')}_{args.label}.json"
    _dump_json(out_path, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")
    return 0


REGRESSION_PATH = ROOT / "rules" / "intent_synth_regression.json"


def cmd_regress(args: argparse.Namespace) -> int:
    """Freeze current holdout direct hits + unbound negatives as a regression corpus."""
    synth_path = Path(args.synth).resolve() if args.synth else _latest("synth")
    if not synth_path or not synth_path.is_file():
        print("FAIL no synth file")
        return 1
    synth = _load_json(synth_path)
    _reset_runtime_caches()
    positives: list[dict[str, str]] = []
    for mid, entry in (synth.get("metrics") or {}).items():
        for utts in (entry.get("holdout") or {}).values():
            for u in utts:
                if mid in resolve_ids(u, expand=False):
                    positives.append({"metric_id": mid, "text": u})
    negatives = [u for us in (synth.get("negatives") or {}).values() for u in us if not resolve_ids(u, expand=False)]
    doc = {
        "schema": "pha.intent_synth_regression/v1",
        "source": str(synth_path.relative_to(ROOT)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Holdout utterances that resolve by direct token hit, and negatives that bind no metric. Regenerate with `regress` after intentional alias changes.",
        "positives": positives,
        "negatives": negatives,
    }
    _dump_json(REGRESSION_PATH, doc)
    print(f"Wrote {REGRESSION_PATH} positives={len(positives)} negatives={len(negatives)}")
    return 0


# --------------------------------------------------------------------------- apply


def _bump_minor(version: str) -> str:
    parts = str(version or "1.0").split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except ValueError:
        parts.append("1")
    return ".".join(parts)


def _mirror_lists(catalog: dict[str, Any]) -> list[list[Any]]:
    """Catalog token lists that mirror metric aliases per key (readiness anti-tokens, exclusive outline)."""
    out: list[list[Any]] = []
    readiness = ((catalog.get("goal_markers") or {}).get("daily_readiness") or {}).get("anti_tokens")
    if isinstance(readiness, list):
        out.append(readiness)
    exclusive = (((catalog.get("assessment_outline") or {}).get("modes") or {}).get("exclusive") or {}).get("tokens")
    if isinstance(exclusive, list):
        out.append(exclusive)
    return out


def _mirrored_keys(catalog: dict[str, Any], tokens: list[Any]) -> set[str]:
    """Keys whose every existing catalog alias already sits in ``tokens``."""
    have = {_norm(str(t)) for t in tokens}
    return {
        str(k)
        for k, v in (catalog.get("metric_aliases") or {}).items()
        if isinstance(v, list) and v and all(_norm(str(a)) in have for a in v)
    }


def cmd_apply(args: argparse.Namespace) -> int:
    proposal_path = Path(args.proposal).resolve() if args.proposal else _latest("proposal")
    if not proposal_path or not proposal_path.is_file():
        print("FAIL no proposal file")
        return 1
    proposal = _load_json(proposal_path)
    review = _load_json(Path(args.review).resolve())
    approved = {(str(r["metric_id"]), _norm(str(r["core"]))) for r in review.get("accept") or []}
    accepted = [
        c
        for c in proposal.get("candidates") or []
        if c.get("decision") == "accept" and (c["metric_id"], _norm(c["core"])) in approved
    ]
    not_gated = approved - {(c["metric_id"], _norm(c["core"])) for c in accepted}
    if not_gated:
        print(f"FAIL review accepts cores the gate did not pass: {sorted(not_gated)}")
        return 1
    if not accepted:
        print("Nothing to apply")
        return 0

    backup_dir = OUT_DIR / f"backup_{_now_tag()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for p in (CATALOG_PATH, REGISTRY_PATH, SCHEMA_PATH):
        shutil.copy2(p, backup_dir / p.name)

    registry = _load_json(REGISTRY_PATH)
    catalog = _load_json(CATALOG_PATH)
    by_id = {m.get("metric_id"): m for m in registry.get("metrics") or [] if isinstance(m, dict)}
    aliases = catalog.setdefault("metric_aliases", {})
    mirrors = [(lst, _mirrored_keys(catalog, lst)) for lst in _mirror_lists(catalog)]
    added: list[dict[str, str]] = []
    for c in accepted:
        for lst, keys in mirrors:
            if c["key"] in keys and not any(_norm(str(t)) == _norm(c["core"]) for t in lst):
                lst.append(c["core"])
        m = by_id.get(c["metric_id"])
        if m is None:
            continue
        hints = m.setdefault("intent_hints", [])
        if not any(_norm(h) == _norm(c["core"]) for h in hints):
            hints.append(c["core"])
        # Catalog-level keys are curated; never open a new key from synth (registry/schema still get the core).
        bucket = aliases.get(c["key"])
        if isinstance(bucket, list) and not any(_norm(a) == _norm(c["core"]) for a in bucket):
            bucket.append(c["core"])
        added.append({"metric_id": c["metric_id"], "key": c["key"], "core": c["core"], "catalog": isinstance(bucket, list)})
    registry["version"] = _bump_minor(str(registry.get("version") or "1.0"))
    catalog["version"] = _bump_minor(str(catalog.get("version") or "1.0"))
    _dump_json(REGISTRY_PATH, registry)
    _dump_json(CATALOG_PATH, catalog)

    from scripts.pha_wearable_bundle_schema_generate import _dump, _load_schema, build_generated_schema

    SCHEMA_PATH.write_text(_dump(build_generated_schema(_load_schema(), bump=True)), encoding="utf-8")
    _reset_runtime_caches()

    from pha.loop_keyword_conflicts import detect_all_keyword_conflicts

    report = detect_all_keyword_conflicts()
    hard = [k for k in report.conflicts if k.kind != "substring_pollution"]
    if hard:
        for p in (CATALOG_PATH, REGISTRY_PATH, SCHEMA_PATH):
            shutil.copy2(backup_dir / p.name, p)
        print("FAIL keyword conflicts after apply — rolled back:")
        for k in hard:
            print("  ", k.as_error())
        return 1

    log = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "proposal": str(proposal_path.relative_to(ROOT)),
        "backup": str(backup_dir.relative_to(ROOT)),
        "added": added,
    }
    _dump_json(OUT_DIR / f"applied_{proposal.get('tag')}.json", log)
    print(f"Applied {len(added)} cores; backup {backup_dir.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth")
    s.add_argument("--tag")
    s.add_argument("--model")
    s.add_argument("--only", help="comma-separated metric_ids")
    g = sub.add_parser("gate")
    g.add_argument("--synth")
    g.add_argument("--out")
    g.add_argument("--extra", help='JSON list of reviewer candidates [{"metric_id","core"}], gated identically')
    e = sub.add_parser("eval")
    e.add_argument("--synth")
    e.add_argument("--label", default="baseline")
    a = sub.add_parser("apply")
    a.add_argument("--proposal")
    a.add_argument("--review", required=True, help='JSON {"accept": [{"metric_id","core"}]} — human-approved subset of gate-accepted cores')
    r = sub.add_parser("regress")
    r.add_argument("--synth")
    args = ap.parse_args()
    handlers = {"synth": cmd_synth, "gate": cmd_gate, "eval": cmd_eval, "apply": cmd_apply, "regress": cmd_regress}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
