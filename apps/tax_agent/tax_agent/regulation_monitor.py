from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from tax_agent.rule_registry import (
    OPTIONAL_SNAPSHOT_FILES,
    REQUIRED_SNAPSHOT_FILES,
    RuleRegistry,
    _utc_now,
)

_FEED_SNAPSHOT_FILES = frozenset(REQUIRED_SNAPSHOT_FILES) | frozenset(OPTIONAL_SNAPSHOT_FILES)

RULE_PACK_DEFAULT = "cn_resident_us_equity"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _feed_url() -> str | None:
    url = (os.environ.get("TAX_AGENT_RULES_FEED_URL") or "").strip()
    return url or None


def _inbox_dir() -> Path | None:
    raw = (os.environ.get("TAX_AGENT_RULES_INBOX_DIR") or "").strip()
    if raw:
        return Path(raw)
    default = _repo_root() / "rules" / "inbox" / RULE_PACK_DEFAULT
    return default if default.is_dir() else None


def fetch_remote_feed(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    headers: dict[str, str] = {}
    token = (os.environ.get("TAX_AGENT_RULES_FEED_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("feed must be a JSON object")
    return data


def _download_text(url: str, client: httpx.Client) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def sync_from_feed(
    registry: RuleRegistry | None = None,
    *,
    feed: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Pull snapshots from trusted JSON feed.

    Feed format:
    {
      "rulePackId": "cn_resident_us_equity",
      "snapshots": [{
        "snapshotFolder": "2026.09.01",
        "status": "review",
        "effectiveFrom": "2026-01-01",
        "files": { "rules.yaml": "...", ... }
        // or "fileUrls": { "rules.yaml": "https://..." }
      }]
    }
    """
    reg = registry or RuleRegistry()
    if feed is None:
        url = _feed_url()
        if not url:
            return []
        feed = fetch_remote_feed(url)

    pack_id = str(feed.get("rulePackId") or RULE_PACK_DEFAULT)
    existing = {s.snapshot_folder: s for s in reg.list_snapshots(pack_id)}
    applied: list[dict[str, Any]] = []

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for item in feed.get("snapshots") or []:
            if not isinstance(item, dict):
                continue
            folder = str(item.get("snapshotFolder") or "").strip()
            if not folder:
                continue
            if folder in existing and existing[folder].status == "stable":
                applied.append(
                    {"snapshotFolder": folder, "action": "skip_stable", "snapshotId": existing[folder].snapshot_id}
                )
                continue

            files: dict[str, str] = {}
            inline = item.get("files") or {}
            if isinstance(inline, dict):
                for k, v in inline.items():
                    if isinstance(v, str) and k in _FEED_SNAPSHOT_FILES:
                        files[k] = v
            urls = item.get("fileUrls") or {}
            if isinstance(urls, dict):
                for k, v in urls.items():
                    if isinstance(v, str) and k in _FEED_SNAPSHOT_FILES:
                        files[k] = _download_text(v, client)

            if len(files) < len(REQUIRED_SNAPSHOT_FILES):
                applied.append(
                    {"snapshotFolder": folder, "action": "skip_incomplete", "missing": list(REQUIRED_SNAPSHOT_FILES)}
                )
                continue

            info = reg.apply_snapshot_files(
                pack_id,
                folder,
                files,
                status=str(item.get("status") or "review"),
                effective_from=item.get("effectiveFrom"),
                source=str(item.get("source") or "remote_feed"),
            )
            applied.append(
                {
                    "snapshotFolder": folder,
                    "action": "imported",
                    "snapshotId": info.snapshot_id,
                    "checksum": info.checksum,
                }
            )
    return applied


def sync_from_inbox(registry: RuleRegistry | None = None) -> list[dict[str, Any]]:
    """Import snapshot folders placed under rules/inbox/{pack}/YYYY.MM.DD/ (+ .ready marker)."""
    reg = registry or RuleRegistry()
    inbox = _inbox_dir()
    if not inbox or not inbox.is_dir():
        return []

    pack_id = RULE_PACK_DEFAULT
    if inbox.name != pack_id and (inbox.parent.name == "inbox"):
        pack_id = inbox.name

    applied: list[dict[str, Any]] = []
    for child in sorted(inbox.iterdir()):
        if not child.is_dir():
            continue
        ready = (child / ".ready").is_file() or (inbox / f"{child.name}.ready").is_file()
        if not ready:
            continue
        dest = reg.snapshot_dir(pack_id, child.name)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(child, dest)
        errors = reg.validate_snapshot_dir(dest)
        if errors:
            applied.append({"snapshotFolder": child.name, "action": "invalid", "errors": errors})
            continue
        meta = reg.read_meta(dest)
        if meta.get("status") not in ("review", "stable"):
            meta["status"] = "review"
            meta["syncedAt"] = meta.get("syncedAt") or _utc_now()
            meta["source"] = "inbox"
            reg.write_meta(dest, meta)
        shutil.rmtree(child)
        marker = inbox / f"{child.name}.ready"
        if marker.is_file():
            marker.unlink()
        applied.append(
            {
                "snapshotFolder": child.name,
                "action": "inbox_imported",
                "snapshotId": f"{pack_id}@{child.name}",
            }
        )
    return applied


def collect_pending_review(registry: RuleRegistry | None = None) -> list[str]:
    reg = registry or RuleRegistry()
    return [
        s.snapshot_folder
        for s in reg.list_snapshots(RULE_PACK_DEFAULT)
        if s.status == "review"
    ]
