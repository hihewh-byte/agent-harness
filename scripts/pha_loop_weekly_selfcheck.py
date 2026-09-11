#!/usr/bin/env python3
"""Offline selfcheck: weekly Loop approval notify + Path B local aliases (no network)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["PHA_LOOP_APPROVE_TOKEN"] = "test-loop-token-selfcheck"
os.environ["PHA_LOOP_BASE_URL"] = "http://127.0.0.1:8788"
os.environ["PHA_LOOP_WEEKLY_CHANNELS"] = "pha_inbox,mac"
os.environ.pop("LOOP_NOTIFY_WEBHOOK_URL", None)
os.environ.pop("PHA_LOOP_SMTP_HOST", None)
os.environ["PHA_LOOP_APPROVE_FULL_VETO"] = "0"

from pha import loop_weekly as lw  # noqa: E402
from pha.health_intent_catalog import catalog_metric_aliases, infer_metrics_from_message  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Redirect artifact dirs
        lw.PENDING_DIR = td_path / "pending"
        lw.DONE_DIR = td_path / "done"
        lw.INBOX_DIR = td_path / "inbox"
        lw.REPORTS_LOOP = td_path / "reports_loop"
        lw.ensure_dirs()

        alias_path = td_path / "loop_local_aliases.json"
        os.environ["PHA_LOOP_LOCAL_ALIASES_PATH"] = str(alias_path)

        unique_alias = "日均走了几步儿_selfcheck"
        proposal = td_path / "alias_proposal_test.json"
        proposal.write_text(
            json.dumps(
                {
                    "schema": "pha.loop_proposal/v2",
                    "accepted_catalog": [
                        {
                            "metric_id": "steps",
                            "alias": unique_alias,
                            "source_message": "日均走了几步儿",
                        },
                    ],
                    "patch_ops": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        pending = lw.create_pending_approval(proposal_path=proposal, source="selfcheck")
        if pending.get("status") != "pending":
            print("FAIL pending status", pending)
            return 1
        if "approve_url" not in pending or pending["approval_id"] not in pending["approve_url"]:
            print("FAIL approve_url", pending)
            return 1

        notes = lw.dispatch_notifications(pending, apply=False)
        channels = {r.get("channel") for r in notes}
        if "pha_inbox" not in channels or "mac" not in channels:
            print("FAIL channels", notes)
            return 1
        if not all(r.get("dry_run") or r.get("skipped") for r in notes):
            if not all(r.get("ok") for r in notes):
                print("FAIL notify not ok", notes)
                return 1

        if not lw.verify_approve_token("test-loop-token-selfcheck"):
            print("FAIL token verify")
            return 1
        if lw.verify_approve_token("wrong"):
            print("FAIL token should reject")
            return 1

        # Reject path
        rej = lw.reject_approval(pending["approval_id"], reason="selfcheck")
        if not rej.get("ok") or rej.get("status") != "rejected":
            print("FAIL reject", rej)
            return 1

        # Approve without YES
        pending2 = lw.create_pending_approval(proposal_path=proposal, source="selfcheck2")
        bad = lw.approve_and_execute(pending2["approval_id"], confirm="no")
        if bad.get("ok") or bad.get("error") != "confirm_must_be_YES":
            print("FAIL confirm gate", bad)
            return 1

        # Path B: approve applies local aliases
        pending_b = lw.create_pending_approval(proposal_path=proposal, source="selfcheck_b")
        ok = lw.approve_and_execute(pending_b["approval_id"], confirm="YES")
        if not ok.get("ok") or not ok.get("local_effect"):
            print("FAIL path B approve", ok)
            return 1
        if int(ok.get("added_n") or 0) < 1:
            print("FAIL expected added alias", ok)
            return 1
        if ok.get("catalog_merged"):
            print("FAIL must not merge catalog", ok)
            return 1
        if not alias_path.is_file():
            print("FAIL local aliases file missing", alias_path)
            return 1
        if unique_alias not in catalog_metric_aliases("steps"):
            print("FAIL catalog_metric_aliases missing local", catalog_metric_aliases("steps"))
            return 1
        inferred = infer_metrics_from_message(f"今天{unique_alias}")
        if "steps" not in inferred:
            print("FAIL infer_metrics_from_message", inferred)
            return 1
        print("OK loop weekly approval + Path B local aliases")

        # Fact-card attachment
        from pha.fact_card_html import render_fact_card_html

        card = {
            "facts": {
                "calendar_day": "2026-09-11",
                "as_of": "2026-09-11",
                "stale": False,
                "metrics": [],
                "healthkit": {"reached": False},
            },
            "assessment": {"summary": {"coverage_present": 0, "coverage_total": 0, "advice": ""}},
            "notification": {"title": "t", "body": "base body", "open_path": "/x"},
            "interpretation": None,
        }
        pending3 = lw.create_pending_approval(proposal_path=proposal, source="selfcheck3")
        lw.attach_loop_approvals_to_fact_card(card, locale="zh-CN")
        if (card.get("loop_approvals") or {}).get("pending_n", 0) < 1:
            print("FAIL fact card loop_approvals", card.get("loop_approvals"))
            return 1
        body = str((card.get("notification") or {}).get("body") or "")
        if "Loop 待审" not in body:
            print("FAIL notification teaser", body)
            return 1
        html = render_fact_card_html(
            card,
            prefs={"enabled_metric_ids": [], "assessment_prompt": "", "locale": "zh-CN"},
            token="test-loop-token-selfcheck",
        )
        if 'id="loop-approvals"' not in html or "同意 · 本机生效" not in html:
            print("FAIL fact card html loop section")
            return 1
        if f"/ops/loop/approvals/{pending3['approval_id']}/approve" not in html:
            print("FAIL approve action missing")
            return 1
        if "本机已生效" not in html:
            print("FAIL local aliases summary missing in html")
            return 1
        print("OK fact card loop section")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
