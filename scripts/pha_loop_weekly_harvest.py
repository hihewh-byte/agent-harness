#!/usr/bin/env python3
"""Weekly Loop harvest + multi-channel notify (proposal-only; no catalog write).

Example (dry-run notify)::

  PYTHONPATH=. python3 scripts/pha_loop_weekly_harvest.py --e2e-jsonl path.jsonl

Apply notifications (Mac / email / webhook / PHA inbox)::

  PYTHONPATH=. python3 scripts/pha_loop_weekly_harvest.py --e2e-jsonl path.jsonl --notify-apply

Iron rule: never auto-merges catalog. Creates a pending approval for human consent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.loop_weekly import weekly_harvest_and_notify  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly Loop harvest + notify (no catalog merge)")
    ap.add_argument("--e2e-jsonl", default=os.environ.get("PHA_E2E_JSONL", ""), help="failure/e2e JSONL")
    ap.add_argument(
        "--notify-apply",
        action="store_true",
        help="actually send Mac/email/webhook (default dry-run channels)",
    )
    ap.add_argument(
        "--force-empty",
        action="store_true",
        help="create approval even when accepted_catalog is empty (debug)",
    )
    ap.add_argument("--json", action="store_true", help="print full result JSON")
    args = ap.parse_args()

    apply = bool(args.notify_apply or (os.environ.get("PHA_LOOP_NOTIFY_APPLY") or "").strip() in ("1", "true", "yes"))
    result = weekly_harvest_and_notify(
        e2e_jsonl=args.e2e_jsonl,
        notify_apply=apply,
        force_empty=args.force_empty,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("harvest_ok:", (result.get("harvest") or {}).get("ok"))
        if result.get("skipped"):
            print("SKIP:", result.get("skip_reason"), "proposal:", result.get("proposal_path"))
            return 0
        pending = result.get("pending") or {}
        print("approval_id:", pending.get("approval_id"))
        print("approve_url:", pending.get("approve_url"))
        print("aliases:", pending.get("accepted_catalog_n"), pending.get("aliases"))
        print("notify_apply:", apply)
        for row in result.get("notify") or []:
            print(" ", row.get("channel"), "ok=", row.get("ok"), "dry_run=", row.get("dry_run"), row.get("error") or row.get("skipped") or "")
        print("Next: open approve_url or:")
        print("  python3 scripts/pha_loop_weekly_approve.py --id", pending.get("approval_id"), "--approve --confirm YES")
    return 0 if (result.get("harvest") or {}).get("ok") or result.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
