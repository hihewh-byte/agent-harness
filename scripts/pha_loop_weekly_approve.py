#!/usr/bin/env python3
"""Approve / reject a weekly Loop pending approval (human gate).

Path B: Approve applies aliases to data/loop_local_aliases.json on this Mac.
Never edits rules/health_intent_catalog.json. Optional --full-veto / Draft PR
are maintainer extras.

  PYTHONPATH=. python3 scripts/pha_loop_weekly_approve.py --list
  PYTHONPATH=. python3 scripts/pha_loop_weekly_approve.py --id loopapr_… --approve --confirm YES
  PYTHONPATH=. python3 scripts/pha_loop_weekly_approve.py --id loopapr_… --reject
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.loop_weekly import (  # noqa: E402
    approve_and_execute,
    get_approval,
    list_pending_approvals,
    reject_approval,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Approve/reject Loop weekly approval")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--id", default="", help="approval_id")
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--reject", action="store_true")
    ap.add_argument("--confirm", default="", help="must be YES to approve")
    ap.add_argument("--reason", default="rejected_by_operator")
    ap.add_argument(
        "--draft-pr",
        action="store_true",
        help="also attempt Draft PR when PHA_LOOP_WEEKLY_DRAFT_PR=1",
    )
    ap.add_argument(
        "--full-veto",
        action="store_true",
        help="also run full-veto (or set PHA_LOOP_APPROVE_FULL_VETO=1)",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.list:
        rows = list_pending_approvals()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(f"pending: {len(rows)}")
            for r in rows:
                print(r.get("approval_id"), r.get("accepted_catalog_n"), r.get("approve_url"))
        return 0

    aid = (args.id or "").strip()
    if not aid:
        print("FAIL: --id required (or --list)", file=sys.stderr)
        return 2
    if args.approve and args.reject:
        print("FAIL: choose one of --approve / --reject", file=sys.stderr)
        return 2
    if args.approve:
        result = approve_and_execute(
            aid,
            confirm=args.confirm,
            run_draft_pr=bool(args.draft_pr),
            enable_full_veto=True if args.full_veto else None,
        )
    elif args.reject:
        result = reject_approval(aid, reason=args.reason)
    else:
        doc = get_approval(aid)
        result = {"ok": bool(doc), "approval": doc}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
