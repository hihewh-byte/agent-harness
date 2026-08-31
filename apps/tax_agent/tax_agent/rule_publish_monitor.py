"""Post-publish 72h compute anomaly monitoring and optional auto-rollback.

规格见 docs/rule-versioning-pipeline-v1.md §4.3：
- 新 stable 发布后进入监控窗口（默认 72h）
- 统计该快照下的测算失败率（status=failed）
- 超过阈值且样本足够时自动 rollback 到 previousStable
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tax_agent.regulation_monitor import RULE_PACK_DEFAULT


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_path() -> Path:
    env = os.environ.get("TAX_AGENT_RULES_MONITOR_STATE")
    if env:
        return Path(env)
    d = _repo_root() / ".data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "rule_publish_monitor.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def monitor_hours() -> int:
    return max(1, int(os.environ.get("TAX_AGENT_RULES_MONITOR_HOURS", "72") or "72"))


def rollback_error_rate() -> float:
    return float(os.environ.get("TAX_AGENT_RULES_ROLLBACK_ERROR_RATE", "0.01") or "0.01")


def rollback_min_samples() -> int:
    return max(1, int(os.environ.get("TAX_AGENT_RULES_ROLLBACK_MIN_SAMPLES", "5") or "5"))


def auto_rollback_enabled() -> bool:
    v = (os.environ.get("TAX_AGENT_RULES_AUTO_ROLLBACK") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


@dataclass
class PublishWatch:
    snapshot_id: str
    previous_stable: str | None
    published_at: str
    window_hours: int = 72
    total_computes: int = 0
    failed_computes: int = 0
    status: str = "watching"  # watching | passed | rolled_back | insufficient_data
    rolled_back_at: str | None = None
    rollback_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def error_rate(self) -> float:
        if self.total_computes <= 0:
            return 0.0
        return self.failed_computes / self.total_computes

    def published_dt(self) -> datetime:
        return datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))

    def window_end(self) -> datetime:
        return self.published_dt() + timedelta(hours=self.window_hours)

    def is_active(self) -> bool:
        return self.status == "watching" and _utc_now() < self.window_end()


def load_monitor_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return {"watches": [], "history": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"watches": [], "history": []}
    data.setdefault("watches", [])
    data.setdefault("history", [])
    return data


def save_monitor_state(state: dict[str, Any]) -> dict[str, Any]:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def _watches_from_state(state: dict[str, Any]) -> list[PublishWatch]:
    out: list[PublishWatch] = []
    for raw in state.get("watches") or []:
        if isinstance(raw, dict):
            out.append(PublishWatch(**raw))
    return out


def _persist_watches(state: dict[str, Any], watches: list[PublishWatch]) -> None:
    state["watches"] = [asdict(w) for w in watches]
    save_monitor_state(state)


def on_publish_stable(publish_log: dict[str, Any]) -> PublishWatch | None:
    """Start monitoring when a snapshot is promoted to stable."""
    snapshot_id = str(publish_log.get("snapshotId") or "")
    if not snapshot_id:
        return None
    state = load_monitor_state()
    watches = _watches_from_state(state)
    # Close any stale watching entries for same snapshot
    for w in watches:
        if w.snapshot_id == snapshot_id and w.status == "watching":
            w.status = "passed"
            w.notes.append("superseded_by_republish")
    watch = PublishWatch(
        snapshot_id=snapshot_id,
        previous_stable=publish_log.get("previousStable"),
        published_at=str(publish_log.get("publishedAt") or _iso(_utc_now())),
        window_hours=monitor_hours(),
    )
    watches.append(watch)
    _persist_watches(state, watches)
    return watch


def record_compute_outcome(rule_snapshot_id: str, status: str) -> None:
    """Record a compute result against active publish watches."""
    state = load_monitor_state()
    watches = _watches_from_state(state)
    changed = False
    for w in watches:
        if not w.is_active():
            continue
        if w.snapshot_id != rule_snapshot_id:
            continue
        w.total_computes += 1
        if status == "failed":
            w.failed_computes += 1
        changed = True
    if changed:
        _persist_watches(state, watches)


def evaluate_watches(registry: Any | None = None) -> list[dict[str, Any]]:
    """
    Evaluate active watches; optionally auto-rollback when error rate exceeds threshold.
    Returns list of actions taken.
    """
    from tax_agent.rule_registry import RuleRegistry

    reg = registry or RuleRegistry()
    state = load_monitor_state()
    watches = _watches_from_state(state)
    actions: list[dict[str, Any]] = []
    now = _utc_now()

    for w in watches:
        if w.status != "watching":
            continue
        window_ended = now >= w.window_end()
        rate = w.error_rate()
        enough = w.total_computes >= rollback_min_samples()
        threshold = rollback_error_rate()

        if not window_ended and not (enough and rate > threshold):
            continue

        if w.total_computes < rollback_min_samples() and window_ended:
            w.status = "insufficient_data"
            w.notes.append(
                f"窗口结束仅 {w.total_computes} 次测算，低于最小样本 {rollback_min_samples()}"
            )
            actions.append(
                {
                    "action": "insufficient_data",
                    "snapshotId": w.snapshot_id,
                    "total": w.total_computes,
                }
            )
            continue

        if rate > threshold and auto_rollback_enabled() and w.previous_stable:
            prev_folder = w.previous_stable.split("@", 1)[-1]
            try:
                rollback = reg.publish_stable(
                    RULE_PACK_DEFAULT,
                    prev_folder,
                    reviewer_id="auto_monitor_rollback",
                )
                w.status = "rolled_back"
                w.rolled_back_at = _iso(now)
                w.rollback_reason = f"error_rate={rate:.4f}>{threshold}"
                actions.append(
                    {
                        "action": "auto_rollback",
                        "snapshotId": w.snapshot_id,
                        "errorRate": rate,
                        "rollbackTo": rollback.get("snapshotId"),
                    }
                )
                state.setdefault("history", []).append(
                    {
                        "at": _iso(now),
                        "snapshotId": w.snapshot_id,
                        "errorRate": rate,
                        "rollbackTo": rollback.get("snapshotId"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                w.notes.append(f"rollback_failed:{exc}")
                actions.append(
                    {
                        "action": "rollback_failed",
                        "snapshotId": w.snapshot_id,
                        "error": str(exc)[:200],
                    }
                )
        elif rate > threshold:
            w.notes.append(f"error_rate={rate:.4f} 超阈值但未启用自动回滚或无 previousStable")
            actions.append(
                {
                    "action": "threshold_exceeded",
                    "snapshotId": w.snapshot_id,
                    "errorRate": rate,
                    "autoRollback": False,
                }
            )
            if window_ended:
                w.status = "passed"
        else:
            w.status = "passed"
            actions.append(
                {
                    "action": "passed",
                    "snapshotId": w.snapshot_id,
                    "errorRate": rate,
                    "total": w.total_computes,
                }
            )

    _persist_watches(state, watches)
    return actions


def get_monitor_status() -> dict[str, Any]:
    state = load_monitor_state()
    watches = _watches_from_state(state)
    active = [asdict(w) for w in watches if w.is_active()]
    recent = [asdict(w) for w in watches if not w.is_active()][-10:]
    return {
        "monitorHours": monitor_hours(),
        "rollbackErrorRate": rollback_error_rate(),
        "rollbackMinSamples": rollback_min_samples(),
        "autoRollbackEnabled": auto_rollback_enabled(),
        "activeWatches": active,
        "recentWatches": recent,
        "history": (state.get("history") or [])[-10:],
    }
