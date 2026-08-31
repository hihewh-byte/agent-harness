#!/usr/bin/env python3
"""Tax harness profile registry selfcheck + optional manifest generate (local P1).

Usage::

    python scripts/run_tax_harness_profile_registry_selfcheck.py
    python scripts/run_tax_harness_profile_registry_selfcheck.py --generate
    python scripts/run_tax_harness_profile_registry_selfcheck.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.harness_profile_registry import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    generate_profile_registry_manifest,
    introspect_profile_contracts,
    validate_harness_profile_registry,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true", help="Write generated JSON manifest")
    ap.add_argument(
        "--check",
        action="store_true",
        help="Validate + ensure generated manifest matches introspection",
    )
    args = ap.parse_args()

    result = validate_harness_profile_registry()
    if not result.ok:
        print("FAIL registry validation:")
        for e in result.errors:
            print(" ", e)
        return 1
    print(f"PASS validate_harness_profile_registry ({len(result.errors)} errors)")

    snap = introspect_profile_contracts()
    print(f"PASS introspect profile_count={snap['profile_count']}")

    if args.generate or args.check:
        path = generate_profile_registry_manifest()
        print(f"PASS wrote manifest → {path}")

    if args.check:
        on_disk = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
        live = introspect_profile_contracts()
        # Compare profile contracts (ignore validation_* stamped at write time)
        if on_disk.get("profiles") != live.get("profiles"):
            print("FAIL: generated manifest profiles drift from live contracts")
            return 1
        if not on_disk.get("validation_ok", False):
            print("FAIL: manifest validation_ok is false")
            return 1
        print("PASS --check manifest matches live contracts")

    print("run_tax_harness_profile_registry_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
