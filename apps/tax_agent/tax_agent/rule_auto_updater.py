from __future__ import annotations

import os
from typing import Any

from tax_agent.regulation_monitor import (
    RULE_PACK_DEFAULT,
    collect_pending_review,
    sync_from_feed,
    sync_from_inbox,
)
from tax_agent.rule_registry import RuleRegistry
from tax_agent.rule_regression import run_golden_regression
from tax_agent.rule_sync_state import save_sync_state


def auto_publish_enabled() -> bool:
    v = (os.environ.get("TAX_AGENT_AUTO_PUBLISH") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def run_auto_update(registry: RuleRegistry | None = None) -> dict[str, Any]:
    """
    Full unattended cycle:
    1. Sync remote feed + local inbox
    2. For each `review` snapshot: run golden regression
    3. If pass and TAX_AGENT_AUTO_PUBLISH=1 → publish stable
    """
    reg = registry or RuleRegistry()
    result: dict[str, Any] = {
        "feedSync": [],
        "inboxSync": [],
        "regression": [],
        "published": [],
        "skipped": [],
        "errors": [],
    }

    try:
        result["feedSync"] = sync_from_feed(reg)
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"feed_sync:{exc}")

    try:
        result["inboxSync"] = sync_from_inbox(reg)
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"inbox_sync:{exc}")

    manifest_stable = reg.load_manifest(RULE_PACK_DEFAULT).get("latestStable")

    for folder in collect_pending_review(reg):
        snap = reg.snapshot_dir(RULE_PACK_DEFAULT, folder)
        if manifest_stable == f"{RULE_PACK_DEFAULT}@{folder}":
            result["skipped"].append({"snapshotFolder": folder, "reason": "already_latest_stable"})
            continue

        report = run_golden_regression()
        result["regression"].append(
            {"snapshotFolder": folder, "reportId": report["reportId"], "passed": report["passed"]}
        )
        if not report["passed"]:
            result["skipped"].append(
                {"snapshotFolder": folder, "reason": "regression_failed", "stderr": report.get("stderr")}
            )
            continue

        if not auto_publish_enabled():
            result["skipped"].append(
                {"snapshotFolder": folder, "reason": "auto_publish_disabled", "hint": "set TAX_AGENT_AUTO_PUBLISH=1"}
            )
            continue

        try:
            pub = reg.publish_stable(
                RULE_PACK_DEFAULT,
                folder,
                reviewer_id="auto_regression",
                regression_report_id=str(report["reportId"]),
            )
            result["published"].append(pub)
            manifest_stable = pub["snapshotId"]
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"publish:{folder}:{exc}")

    result["latestStable"] = reg.load_manifest(RULE_PACK_DEFAULT).get("latestStable")
    result["autoPublishEnabled"] = auto_publish_enabled()
    return result


def run_auto_update_and_record(
    registry: RuleRegistry | None = None,
    *,
    trigger: str = "manual",
) -> dict[str, Any]:
    result = run_auto_update(registry)
    state = save_sync_state(result, trigger=trigger)
    result["syncState"] = state
    return result
