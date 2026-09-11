"""Weekly Loop harvest → multi-channel notify → human approval (no catalog auto-merge).

Iron rules:
- Harvest / proposals may write under ``reports/loop/`` only.
- Notifications never apply catalog patches.
- Approve may run full-veto + optional Draft PR / staging; never edits
  ``rules/health_intent_catalog.json``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import smtplib
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPORTS_LOOP = _PACKAGE_ROOT / "reports" / "loop"
PENDING_DIR = REPORTS_LOOP / "approvals" / "pending"
DONE_DIR = REPORTS_LOOP / "approvals" / "done"
INBOX_DIR = _PACKAGE_ROOT / "data" / "loop_inbox"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)


def approval_token_configured() -> str:
    return (
        (os.environ.get("PHA_LOOP_APPROVE_TOKEN") or "").strip()
        or (os.environ.get("PHA_INGEST_TOKEN") or "").strip()
    )


def verify_approve_token(provided: Optional[str]) -> bool:
    expected = approval_token_configured()
    if not expected:
        return False
    return secrets.compare_digest((provided or "").strip(), expected)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def latest_alias_proposal(proposal_dir: Optional[Path] = None) -> Optional[Path]:
    d = proposal_dir or (REPORTS_LOOP / "proposals")
    if not d.is_dir():
        return None
    cands = sorted(
        [p for p in d.glob("alias_proposal_*.json") if ".REJECTED" not in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


def proposal_has_work(doc: dict[str, Any]) -> bool:
    return bool(doc.get("accepted_catalog") or doc.get("patch_ops"))


def _alias_summary(doc: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for row in doc.get("accepted_catalog") or []:
        if not isinstance(row, dict):
            continue
        mid = str(row.get("metric_id") or row.get("target") or "?")
        alias = str(row.get("alias") or "?")
        lines.append(f"{mid} ← {alias}")
    return lines


def create_pending_approval(
    *,
    proposal_path: Path,
    source: str = "weekly_harvest",
    base_url: str = "",
) -> dict[str, Any]:
    """Create a pending approval card (does not merge anything)."""
    ensure_dirs()
    doc = _load_json(proposal_path)
    stamp = _utc_stamp()
    approval_id = f"loopapr_{stamp}_{secrets.token_hex(4)}"
    digest = hashlib.sha256(proposal_path.read_bytes()).hexdigest()[:16]
    base = (base_url or os.environ.get("PHA_LOOP_BASE_URL") or "http://127.0.0.1:8788").rstrip("/")
    approve_url = f"{base}/ops/loop/approvals/{approval_id}/view"
    tok = approval_token_configured()
    embed = (os.environ.get("PHA_LOOP_APPROVE_URL_EMBED_TOKEN") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if embed and tok:
        approve_url = f"{approve_url}?token={tok}"
    pending = {
        "schema": "pha.loop_weekly_approval/v1",
        "approval_id": approval_id,
        "status": "pending",
        "created_at": _now_iso(),
        "source": source,
        "proposal_path": str(proposal_path.resolve()),
        "proposal_sha256_16": digest,
        "accepted_catalog_n": len(doc.get("accepted_catalog") or []),
        "aliases": _alias_summary(doc),
        "approve_url": approve_url,
        "execute_on_approve": [
            "full_veto",
            "optional_draft_pr_if_env",
        ],
        "forbidden": [
            "auto_merge_catalog",
            "edit_health_intent_catalog",
            "change_harness_profiles",
        ],
        "notes": (
            "Approve runs full-veto (+ optional Draft PR). "
            "Catalog edit still requires a human Ready PR after passed verdict."
        ),
    }
    path = PENDING_DIR / f"{approval_id}.json"
    _write_json(path, pending)
    inbox_path = INBOX_DIR / f"{approval_id}.json"
    _write_json(inbox_path, pending)
    pending["pending_path"] = str(path)
    pending["inbox_path"] = str(inbox_path)
    return pending


def list_pending_approvals() -> list[dict[str, Any]]:
    ensure_dirs()
    out: list[dict[str, Any]] = []
    for p in sorted(PENDING_DIR.glob("loopapr_*.json"), reverse=True):
        try:
            doc = _load_json(p)
        except (OSError, json.JSONDecodeError):
            continue
        if doc.get("status") == "pending":
            out.append(doc)
    return out


def get_approval(approval_id: str) -> Optional[dict[str, Any]]:
    ensure_dirs()
    aid = (approval_id or "").strip()
    for folder in (PENDING_DIR, DONE_DIR):
        path = folder / f"{aid}.json"
        if path.is_file():
            doc = _load_json(path)
            doc["_path"] = str(path)
            return doc
    return None


def _move_to_done(doc: dict[str, Any]) -> Path:
    ensure_dirs()
    aid = str(doc.get("approval_id") or "")
    src = PENDING_DIR / f"{aid}.json"
    dst = DONE_DIR / f"{aid}.json"
    _write_json(dst, doc)
    if src.is_file():
        src.unlink()
    inbox = INBOX_DIR / f"{aid}.json"
    if inbox.is_file():
        _write_json(inbox, doc)
    return dst


def notify_mac(title: str, body: str, *, apply: bool) -> dict[str, Any]:
    if not apply:
        return {"ok": True, "dry_run": True, "channel": "mac"}
    # Escape for AppleScript string.
    t = title.replace("\\", "\\\\").replace('"', '\\"')
    b = body.replace("\\", "\\\\").replace('"', '\\"')[:180]
    script = f'display notification "{b}" with title "{t}" sound name "Glass"'
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return {
            "ok": r.returncode == 0,
            "channel": "mac",
            "stderr": (r.stderr or "")[:200],
        }
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "channel": "mac", "error": str(e)}


def notify_email(
    *,
    subject: str,
    body: str,
    apply: bool,
) -> dict[str, Any]:
    host = (os.environ.get("PHA_LOOP_SMTP_HOST") or "").strip()
    to_addr = (os.environ.get("PHA_LOOP_NOTIFY_EMAIL_TO") or "").strip()
    from_addr = (os.environ.get("PHA_LOOP_NOTIFY_EMAIL_FROM") or to_addr).strip()
    if not host or not to_addr:
        return {
            "ok": False,
            "channel": "email",
            "skipped": True,
            "error": "set PHA_LOOP_SMTP_HOST and PHA_LOOP_NOTIFY_EMAIL_TO",
        }
    meta = {
        "to": to_addr,
        "from": from_addr,
        "subject": subject,
        "body_head": body[:200],
    }
    if not apply:
        return {"ok": True, "dry_run": True, "channel": "email", **meta}
    port = int(os.environ.get("PHA_LOOP_SMTP_PORT") or "587")
    user = (os.environ.get("PHA_LOOP_SMTP_USER") or "").strip()
    password = (os.environ.get("PHA_LOOP_SMTP_PASSWORD") or "").strip()
    use_tls = (os.environ.get("PHA_LOOP_SMTP_TLS") or "1").strip() not in ("0", "false", "no")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return {"ok": True, "channel": "email", "to": to_addr}
    except (OSError, smtplib.SMTPException) as e:
        return {"ok": False, "channel": "email", "error": str(e)[:300]}


def notify_webhook(
    *,
    text: str,
    meta: dict[str, Any],
    apply: bool,
) -> dict[str, Any]:
    url = (os.environ.get("LOOP_NOTIFY_WEBHOOK_URL") or "").strip()
    if not url:
        return {
            "ok": False,
            "channel": "webhook",
            "skipped": True,
            "error": "LOOP_NOTIFY_WEBHOOK_URL unset",
        }
    fmt = (os.environ.get("LOOP_NOTIFY_WEBHOOK_FORMAT") or "generic").strip().lower()
    if fmt == "feishu":
        body: dict[str, Any] = {"msg_type": "text", "content": {"text": text}}
    elif fmt == "slack":
        body = {"text": text}
    else:
        body = {"text": text, "meta": meta}
    if not apply:
        return {"ok": True, "dry_run": True, "channel": "webhook", "format": fmt, "body": body}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return {"ok": 200 <= resp.status < 300, "channel": "webhook", "status": resp.status}
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        return {"ok": False, "channel": "webhook", "error": str(e)[:300]}


def notify_pha_inbox(pending: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    """PHA-internal inbox is the pending JSON under data/loop_inbox (already written)."""
    if not apply:
        return {"ok": True, "dry_run": True, "channel": "pha_inbox", "path": pending.get("inbox_path")}
    path = Path(str(pending.get("inbox_path") or ""))
    return {
        "ok": path.is_file(),
        "channel": "pha_inbox",
        "path": str(path),
        "view": pending.get("approve_url"),
    }


def build_notify_text(pending: dict[str, Any]) -> str:
    aliases = pending.get("aliases") or []
    lines = [
        "[PHA Loop] weekly harvest — approval required",
        f"id: {pending.get('approval_id')}",
        f"aliases: {pending.get('accepted_catalog_n')}",
        *[f"  - {a}" for a in aliases[:12]],
        "",
        f"Open to approve or reject: {pending.get('approve_url')}",
        "Or open PHA Fact Card (iOS) — Loop approvals section.",
        "",
        "Approve runs full-veto only. Does NOT auto-merge catalog.",
        "CLI: python3 scripts/pha_loop_weekly_approve.py --id <id> --approve --confirm YES",
    ]
    return "\n".join(lines)


def dispatch_notifications(pending: dict[str, Any], *, apply: bool) -> list[dict[str, Any]]:
    text = build_notify_text(pending)
    subject = f"[PHA Loop] approval {pending.get('approval_id')} ({pending.get('accepted_catalog_n')} aliases)"
    title = "PHA Loop · needs approval"
    body_short = f"{pending.get('accepted_catalog_n')} alias(es). Tap approve URL or use CLI."
    results = [
        notify_pha_inbox(pending, apply=apply),
        notify_mac(title, body_short, apply=apply),
        notify_email(subject=subject, body=text, apply=apply),
        notify_webhook(text=text, meta={"approval_id": pending.get("approval_id")}, apply=apply),
    ]
    channels_env = (os.environ.get("PHA_LOOP_WEEKLY_CHANNELS") or "pha_inbox,mac,email,webhook").lower()
    wanted = {c.strip() for c in channels_env.split(",") if c.strip()}
    if wanted:
        results = [r for r in results if r.get("channel") in wanted]
    return results


def run_harvest_pipeline(*, e2e_jsonl: str = "", dry_distill: bool = False) -> dict[str, Any]:
    """Invoke existing weekly-safe harvest shell (proposal-only)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PACKAGE_ROOT)
    if e2e_jsonl:
        env["PHA_E2E_JSONL"] = e2e_jsonl
    if dry_distill:
        env["PHA_LOOP_DRY_DISTILL"] = "1"
    # Weekly path uses our notifier; disable nested notify inside the shell script.
    env["PHA_LOOP_NOTIFY"] = "0"
    script = _PACKAGE_ROOT / "scripts" / "pha_loop_run_from_e2e.sh"
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=str(_PACKAGE_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=int(os.environ.get("PHA_LOOP_WEEKLY_TIMEOUT_SEC") or "1800"),
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
    }


def run_full_veto(proposal_path: Path) -> dict[str, Any]:
    py = _PACKAGE_ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.is_file() else "python3"
    proc = subprocess.run(
        [exe, "scripts/pha_loop_promote_candidate.py", "--proposal", str(proposal_path), "--full-veto"],
        cwd=str(_PACKAGE_ROOT),
        env={**os.environ, "PYTHONPATH": str(_PACKAGE_ROOT)},
        text=True,
        capture_output=True,
        check=False,
        timeout=int(os.environ.get("PHA_LOOP_VETO_TIMEOUT_SEC") or "3600"),
    )
    verdicts = sorted((REPORTS_LOOP / "verdicts").glob("promote_verdict_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest = verdicts[0] if verdicts else None
    passed = False
    if latest and latest.is_file():
        try:
            passed = bool(_load_json(latest).get("passed"))
        except (OSError, json.JSONDecodeError):
            passed = False
    return {
        "ok": proc.returncode == 0 and passed,
        "exit_code": proc.returncode,
        "verdict_path": str(latest) if latest else "",
        "passed": passed,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-3000:],
    }


def maybe_draft_pr(proposal_path: Path) -> dict[str, Any]:
    """Optional Draft PR via existing notify script (still not catalog merge)."""
    if (os.environ.get("PHA_LOOP_WEEKLY_DRAFT_PR") or "0").strip() not in ("1", "true", "yes"):
        return {"ok": True, "skipped": True, "channel": "draft-pr"}
    py = _PACKAGE_ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.is_file() else "python3"
    proc = subprocess.run(
        [
            exe,
            "scripts/pha_loop_notify_proposal.py",
            "--proposal",
            str(proposal_path),
            "--channels",
            "draft-pr",
            "--apply",
        ],
        cwd=str(_PACKAGE_ROOT),
        env={**os.environ, "PYTHONPATH": str(_PACKAGE_ROOT), "PHA_LOOP_NOTIFY_APPLY": "1"},
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    return {
        "ok": proc.returncode == 0,
        "channel": "draft-pr",
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def reject_approval(approval_id: str, *, reason: str = "rejected_by_operator") -> dict[str, Any]:
    doc = get_approval(approval_id)
    if not doc:
        return {"ok": False, "error": "not_found"}
    if doc.get("status") != "pending":
        return {"ok": False, "error": f"not_pending:{doc.get('status')}"}
    doc["status"] = "rejected"
    doc["rejected_at"] = _now_iso()
    doc["reject_reason"] = reason
    path = _move_to_done(doc)
    return {"ok": True, "status": "rejected", "path": str(path)}


def approve_and_execute(
    approval_id: str,
    *,
    confirm: str,
    run_draft_pr: bool = False,
    enable_full_veto: Optional[bool] = None,
) -> dict[str, Any]:
    """Human-gated execute (Path B): apply aliases on this machine only.

    Does **not** edit ``rules/health_intent_catalog.json``. Optional full-veto /
    Draft PR remain maintainer extras (env / flags).
    """
    if (confirm or "").strip() != "YES":
        return {"ok": False, "error": "confirm_must_be_YES"}
    doc = get_approval(approval_id)
    if not doc:
        return {"ok": False, "error": "not_found"}
    if doc.get("status") != "pending":
        return {"ok": False, "error": f"not_pending:{doc.get('status')}"}
    proposal = Path(str(doc.get("proposal_path") or ""))
    if not proposal.is_file():
        return {"ok": False, "error": f"proposal_missing:{proposal}"}

    try:
        proposal_doc = _load_json(proposal)
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"proposal_unreadable:{e}"}

    from pha.loop_local_aliases import apply_proposal_aliases

    local_apply = apply_proposal_aliases(
        proposal_doc,
        approval_id=str(doc.get("approval_id") or ""),
        source="fact_card_or_ops_approve",
    )

    want_veto = enable_full_veto
    if want_veto is None:
        want_veto = (os.environ.get("PHA_LOOP_APPROVE_FULL_VETO") or "0").strip().lower() in (
            "1",
            "true",
            "yes",
        )
    veto: dict[str, Any] = {"ok": True, "skipped": True}
    if want_veto:
        veto = run_full_veto(proposal)

    draft: dict[str, Any] = {"ok": True, "skipped": True}
    if run_draft_pr and (os.environ.get("PHA_LOOP_WEEKLY_DRAFT_PR") or "0").strip() in (
        "1",
        "true",
        "yes",
    ):
        draft = maybe_draft_pr(proposal)

    added_n = int(local_apply.get("added_n") or 0)
    doc["status"] = "approved_local_applied" if added_n else "approved_no_new_aliases"
    if want_veto and not veto.get("ok") and not veto.get("skipped"):
        doc["status"] = "approved_local_applied_veto_failed"
    doc["approved_at"] = _now_iso()
    doc["execution"] = {
        "local_aliases": local_apply,
        "full_veto": veto,
        "draft_pr": draft,
        "catalog_merged": False,
        "local_effect": True,
        "note": (
            "Aliases applied under data/loop_local_aliases.json on this Mac only. "
            "Repo catalog unchanged."
        ),
    }
    path = _move_to_done(doc)
    return {
        "ok": True,
        "status": doc["status"],
        "path": str(path),
        "local_aliases": local_apply,
        "verdict_path": veto.get("verdict_path"),
        "draft_pr": draft,
        "catalog_merged": False,
        "local_effect": True,
        "added_n": added_n,
    }


def weekly_harvest_and_notify(
    *,
    e2e_jsonl: str = "",
    notify_apply: bool = False,
    force_empty: bool = False,
) -> dict[str, Any]:
    """End-to-end weekly job: harvest → pending approval → multi-channel notify."""
    ensure_dirs()
    harvest = run_harvest_pipeline(e2e_jsonl=e2e_jsonl, dry_distill=False)
    proposal = latest_alias_proposal()
    result: dict[str, Any] = {
        "harvest": harvest,
        "proposal_path": str(proposal) if proposal else "",
        "pending": None,
        "notify": [],
        "skipped": False,
    }
    if not proposal or not proposal.is_file():
        result["skipped"] = True
        result["skip_reason"] = "no_alias_proposal"
        return result
    doc = _load_json(proposal)
    if not proposal_has_work(doc) and not force_empty:
        result["skipped"] = True
        result["skip_reason"] = "empty_accepted_catalog"
        result["proposal_path"] = str(proposal)
        return result
    pending = create_pending_approval(proposal_path=proposal, source="weekly_harvest")
    result["pending"] = pending
    result["notify"] = dispatch_notifications(pending, apply=notify_apply)
    _write_json(
        REPORTS_LOOP / "approvals" / f"weekly_run_{pending['approval_id']}.json",
        result,
    )
    return result


def list_pending_approvals_for_fact_card(*, limit: int = 5) -> list[dict[str, Any]]:
    """Compact pending rows for the fact-card JSON / HTML (no secrets)."""
    rows: list[dict[str, Any]] = []
    for doc in list_pending_approvals()[: max(0, int(limit))]:
        rows.append(
            {
                "approval_id": doc.get("approval_id"),
                "created_at": doc.get("created_at"),
                "accepted_catalog_n": doc.get("accepted_catalog_n") or 0,
                "aliases": list(doc.get("aliases") or [])[:12],
                "status": doc.get("status"),
                "notes": doc.get("notes"),
            }
        )
    return rows


def attach_loop_approvals_to_fact_card(
    card: dict[str, Any],
    *,
    locale: Optional[str] = None,
) -> dict[str, Any]:
    """Mutate card with ``loop_approvals``; also tease on lock-screen notification."""
    from pha.fact_card_copy import card_copy

    from pha.loop_local_aliases import local_aliases_summary

    pending = list_pending_approvals_for_fact_card()
    local = local_aliases_summary(limit=12)
    card["loop_approvals"] = {
        "pending_n": len(pending),
        "pending": pending,
        "local_aliases": local,
        "approve_hint": "local_aliases_this_mac_no_catalog_merge",
    }
    if pending:
        n = len(pending)
        aliases = pending[0].get("aliases") or []
        head = aliases[0] if aliases else str(pending[0].get("approval_id") or "")
        loc = locale or "en-US"
        if str(loc).startswith("zh"):
            note = f"Loop 待审 ×{n}"
            if head:
                note += f"：{head}"
        else:
            note = f"Loop approval pending ×{n}"
            if head:
                note += f": {head}"
        _ = card_copy  # locale tables remain source for HTML; teaser stays short
        notif = card.get("notification")
        if isinstance(notif, dict):
            body = str(notif.get("body") or "")
            notif["body"] = f"{note}\n{body}" if body else note
            notif["loop_pending_n"] = n
    return card


__all__ = [
    "approve_and_execute",
    "attach_loop_approvals_to_fact_card",
    "create_pending_approval",
    "dispatch_notifications",
    "get_approval",
    "list_pending_approvals",
    "list_pending_approvals_for_fact_card",
    "reject_approval",
    "verify_approve_token",
    "weekly_harvest_and_notify",
]
