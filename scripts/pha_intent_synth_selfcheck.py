#!/usr/bin/env python3
"""Stage 1 intent synth selfcheck (no LLM).

A. Gate fixtures: time anchor / existing alias / same-cluster broad word /
   cross-metric batch dup / negative-corpus hit / novel probe.
B. Regression corpus ``rules/intent_synth_regression.json``: recorded holdout
   utterances still resolve (direct hit) to their metric; recorded negatives
   stay unbound.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PHA_HEALTH_INTENT_CATALOG", "1")

from scripts.pha_intent_synth_expand import gate_candidates, load_spec, resolve_ids  # noqa: E402

REGRESSION_PATH = ROOT / "rules" / "intent_synth_regression.json"
_PROBE = "测试探针词"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _fixture() -> dict:
    return {
        "tag": "selfcheck",
        "negatives": {"zh": ["最近总觉得提不起精神，好像有点负面探针"]},
        "metrics": {
            "sleep_deep": {
                "key": "sleep",
                "cluster": "sleep",
                "train": {
                    "zh": {
                        "utterances": ["最近深睡够不够"],
                        "cores": ["深睡", "今晚探针乙", "睡眠质量", "重复探针", "负面探针"],
                    }
                },
            },
            "sleep_awake": {
                "key": "sleep",
                "cluster": "sleep",
                "train": {"zh": {"utterances": ["夜里老醒"], "cores": ["重复探针", _PROBE]}},
            },
        },
    }


def check_gates() -> None:
    spec = load_spec()
    by_core: dict[tuple[str, str], dict] = {
        (c["metric_id"], c["core"]): c for c in gate_candidates(_fixture(), spec)
    }

    def status(mid: str, core: str) -> str:
        return by_core[(mid, core)]["status"]

    def reasons(mid: str, core: str) -> str:
        return " ".join(by_core[(mid, core)]["reasons"])

    _assert(status("sleep_deep", "深睡") == "covered", "existing alias must be covered")
    _assert(status("sleep_deep", "今晚探针乙") == "rejected", "time anchor must be rejected")
    _assert(status("sleep_deep", "睡眠质量") == "rejected", "broad same-cluster word must be rejected")
    _assert("core_cross_hit" in reasons("sleep_deep", "睡眠质量"), reasons("sleep_deep", "睡眠质量"))
    _assert("batch_dup" in reasons("sleep_deep", "重复探针"), "cross-metric dup must be rejected")
    _assert("batch_dup" in reasons("sleep_awake", "重复探针"), "cross-metric dup must be rejected")
    _assert("negative_hit" in reasons("sleep_deep", "负面探针"), "negative corpus hit must be rejected")
    _assert(status("sleep_awake", _PROBE) == "accepted", f"novel probe should pass: {reasons('sleep_awake', _PROBE)}")
    print("OK gate fixtures")


def check_regression() -> None:
    if not REGRESSION_PATH.is_file():
        print("SKIP regression corpus (not generated)")
        return
    doc = json.loads(REGRESSION_PATH.read_text(encoding="utf-8"))
    fails: list[str] = []
    for row in doc.get("positives") or []:
        got = resolve_ids(row["text"], expand=False)
        if row["metric_id"] not in got:
            fails.append(f"positive {row['metric_id']}: {row['text']!r} -> {got}")
    for text in doc.get("negatives") or []:
        got = resolve_ids(text, expand=False)
        if got:
            fails.append(f"negative bound: {text!r} -> {got}")
    _assert(not fails, "regression drift:\n  " + "\n  ".join(fails[:20]))
    print(f"OK regression corpus positives={len(doc.get('positives') or [])} negatives={len(doc.get('negatives') or [])}")


def main() -> int:
    try:
        check_gates()
        check_regression()
    except AssertionError as exc:
        print(f"FAIL {exc}")
        return 1
    print("PASS pha_intent_synth_selfcheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
