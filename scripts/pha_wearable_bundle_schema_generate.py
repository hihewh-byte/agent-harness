#!/usr/bin/env python3
"""Generate or verify wearable_bundle.schema.json catalog fields from the metric registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.wearable_metric_registry import (  # noqa: E402
    bundle_core_hint_keywords,
    bundle_trigger_keywords,
    catalog_keys_canonical,
    catalog_keys_core,
    clear_registry_cache,
)

SCHEMA_PATH = ROOT / "storage" / "schemas" / "wearable_bundle.schema.json"
_REWRITE_FIELDS = ("trigger_keywords", "core_hint_keywords")
_METRICS_REWRITE = ("canonical", "core")


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def _apply_registry_fields(doc: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(doc))
    catalog = dict(out.get("catalog") or {})
    catalog["trigger_keywords"] = bundle_trigger_keywords()
    catalog["core_hint_keywords"] = bundle_core_hint_keywords()
    out["catalog"] = catalog
    metrics = dict(out.get("metrics") or {})
    metrics["canonical"] = list(catalog_keys_canonical())
    metrics["core"] = list(catalog_keys_core())
    out["metrics"] = metrics
    return out


def _bump_patch(version: str) -> str:
    parts = str(version or "1.2.0").split(".")
    if len(parts) == 3:
        try:
            return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
        except ValueError:
            return "1.2.1"
    return "1.2.1"


def build_generated_schema(base: dict[str, Any] | None = None, *, bump: bool = False) -> dict[str, Any]:
    clear_registry_cache()
    current = base or _load_schema()
    doc = _apply_registry_fields(current)
    if bump and _comparable_payload(current) != _comparable_payload(doc):
        doc["schema_version"] = _bump_patch(str(current.get("schema_version") or "1.2.0"))
        contract = dict(doc.get("contract") or {})
        contract["revision"] = "2026-09-09"
        doc["contract"] = contract
    return doc


def _comparable_payload(doc: dict[str, Any]) -> dict[str, Any]:
    catalog = doc.get("catalog") or {}
    metrics = doc.get("metrics") or {}
    return {
        "trigger_keywords": catalog.get("trigger_keywords"),
        "core_hint_keywords": catalog.get("core_hint_keywords"),
        "canonical": metrics.get("canonical"),
        "core": metrics.get("core"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = _load_schema()
    if args.write:
        generated = build_generated_schema(current, bump=True)
        SCHEMA_PATH.write_text(_dump(generated), encoding="utf-8")
        print(f"Wrote {SCHEMA_PATH}")
        return 0
    do_check = args.check or not args.write
    if do_check:
        generated = build_generated_schema(current, bump=False)
        if _comparable_payload(current) != _comparable_payload(generated):
            print("FAIL  wearable_bundle.schema.json catalog fields drifted from registry")
            print("Hint: python scripts/pha_wearable_bundle_schema_generate.py --write")
            return 1
        print("OK wearable_bundle.schema.json catalog fields match registry")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
