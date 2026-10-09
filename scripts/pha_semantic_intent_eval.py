#!/usr/bin/env python3
"""Stage 2 offline eval — proposer + gate on zero-entity utterances (live Ollama).

Corpus: Stage 1 ``reports/intent_synth/synth_*.json``.
  dev      — train utterances with zero direct token entities (tune here)
  holdout  — holdout utterances with zero direct token entities (report once)
  negatives are always included (feelings / symptoms without a metric).

Scores per labelled utterance:
  adopt_ok     expected metric adopted, nothing adopted outside its cluster
  adopt_wrong  adopted something else (or extra off-cluster metrics)
  clarify_hit  clarify offered the expected metric among candidates
  clarify_miss clarify without the expected metric
  none         no decision (falls through to today's behaviour)
Negatives: false_adopt / clarify / none.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_HEALTH_INTENT_CATALOG", "1")
os.environ["PHA_SEMANTIC_INTENT"] = "shadow"

from pha.semantic_intent import (  # noqa: E402
    gate_proposal,
    load_semantic_intent_spec,
    needs_semantic_proposal,
    propose,
    verify_decision,
)
from pha.wearable_metric_registry import cluster_of  # noqa: E402

OUT_DIR = ROOT / "reports" / "semantic_intent"


def _latest_synth() -> Path:
    files = sorted((ROOT / "reports" / "intent_synth").glob("synth_s1*.json"))
    if not files:
        raise SystemExit("no Stage 1 synth corpus")
    return files[-1]


def _corpus(synth: dict, split: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for mid, entry in (synth.get("metrics") or {}).items():
        for v in (entry.get("train" if split == "dev" else "holdout") or {}).values():
            utts = v.get("utterances") if isinstance(v, dict) else v
            rows.extend((mid, u) for u in utts or [])
    return [(mid, u) for mid, u in rows if needs_semantic_proposal("default", u)]


def _score(expected: str, decision) -> str:
    if decision.action == "adopt":
        cl = cluster_of(expected) or expected
        if expected in decision.metric_ids and all((cluster_of(m) or m) == cl for m in decision.metric_ids):
            return "adopt_ok"
        return "adopt_wrong"
    if decision.action == "clarify":
        return "clarify_hit" if expected in decision.candidates else "clarify_miss"
    return "none"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("dev", "holdout"), default="dev")
    ap.add_argument("--model")
    ap.add_argument("--sample", type=int, default=0, help="random sample of labelled rows (0 = all)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--synth")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    verify = bool(load_semantic_intent_spec().get("verify_adopt")) and not args.no_verify

    def decide(text: str):
        prop = propose(text, model=args.model)
        dec = gate_proposal(text, prop)
        if verify:
            dec = verify_decision(text, prop, dec, model=args.model)
        lat = prop.get("latency_ms", 0) + sum(v.get("latency_ms", 0) for v in prop.get("verify") or [])
        return prop, dec, lat

    synth = json.loads(Path(args.synth or _latest_synth()).read_text(encoding="utf-8"))
    rows = _corpus(synth, args.split)
    if args.sample and len(rows) > args.sample:
        rows = random.Random(args.seed).sample(rows, args.sample)
    negatives = [u for us in (synth.get("negatives") or {}).values() for u in us if needs_semantic_proposal("default", u)]

    counts: dict[str, int] = {}
    neg_counts: dict[str, int] = {}
    details: list[dict] = []
    latencies: list[int] = []
    for i, (mid, text) in enumerate(rows, 1):
        prop, dec, lat = decide(text)
        latencies.append(lat)
        verdict = _score(mid, dec)
        counts[verdict] = counts.get(verdict, 0) + 1
        details.append({"expected": mid, "text": text, "verdict": verdict, "proposal": prop, "decision": dec.as_report()})
        if i % 25 == 0:
            print(f"  {i}/{len(rows)} {counts}", flush=True)
    for text in negatives:
        prop, dec, lat = decide(text)
        latencies.append(lat)
        neg_counts[dec.action] = neg_counts.get(dec.action, 0) + 1
        details.append({"expected": None, "text": text, "verdict": f"neg_{dec.action}", "proposal": prop, "decision": dec.as_report()})

    n, nn = len(rows), len(negatives)
    lat = sorted(latencies) or [0]
    adopted = counts.get("adopt_ok", 0) + counts.get("adopt_wrong", 0)
    summary = {
        "split": args.split,
        "verify": verify,
        "model": details[0]["proposal"]["model"] if details else args.model,
        "labelled": n,
        "counts": counts,
        "adopt_rate": round(adopted / n, 4) if n else 0.0,
        "adopt_precision": round(counts.get("adopt_ok", 0) / adopted, 4) if adopted else 0.0,
        "recovered_rate": round(counts.get("adopt_ok", 0) / n, 4) if n else 0.0,
        "clarify_rate": round((counts.get("clarify_hit", 0) + counts.get("clarify_miss", 0)) / n, 4) if n else 0.0,
        "negatives": nn,
        "negative_counts": neg_counts,
        "negative_false_adopt_rate": round(neg_counts.get("adopt", 0) / nn, 4) if nn else 0.0,
        "latency_ms_p50": lat[len(lat) // 2],
        "latency_ms_p90": lat[int(len(lat) * 0.9) - 1 if len(lat) > 1 else 0],
    }
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_tag = (summary["model"] or "default").replace(":", "_").replace("/", "_")
    out = OUT_DIR / f"eval_{args.split}_{model_tag}_{tag}.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "details": details}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
