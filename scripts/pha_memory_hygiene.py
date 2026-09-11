#!/usr/bin/env python3
"""M1-P13 memory hygiene: remove interpret-leaked chat sessions and polluted notes.

Default is dry-run. ``--apply`` copies the DB to ``data/backups/`` first.
Empty sessions (class C) are listed but not deleted unless ``--include-empty``.
Capture-negative question notes (class Q) are deleted on ``--apply``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.chat_background import is_system_tag_message  # noqa: E402
from pha.fact_card_background_brief import note_hits_capture_negative  # noqa: E402
from pha.harness_plan import FACT_CARD_INTERPRET_USER_MESSAGE  # noqa: E402
from pha.sqlite_storage import get_db_path  # noqa: E402

# 2026-09-07..08: interpret used a Chinese TASK-like user message as the
# synthetic chat turn; captured as medication notes and stored as sessions.
LEGACY_SYNTHETIC_USER_MESSAGES = (
    "请根据系统提供的当日事实卡数字与基线摘要，写一段简短的健康教育解读。",
)

_SYSTEM_TAG_RE = re.compile(r"^\[([a-z][a-z0-9_]*)\]")


def synthetic_prefixes() -> list[str]:
    prefixes = [FACT_CARD_INTERPRET_USER_MESSAGE.strip()]
    prefixes.extend(p.strip() for p in LEGACY_SYNTHETIC_USER_MESSAGES if p.strip())
    return [p for p in prefixes if p]


def is_synthetic_user_content(content: str, prefixes: list[str] | None = None) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    for prefix in prefixes or synthetic_prefixes():
        if text == prefix or text.startswith(prefix):
            return True
        clip = prefix[:40]
        if clip and text.startswith(clip):
            return True
    return False


def is_polluted_note_content(content: str, prefixes: list[str] | None = None) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if is_system_tag_message(text) or _SYSTEM_TAG_RE.match(text):
        return True
    return is_synthetic_user_content(text, prefixes)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def classify(conn: sqlite3.Connection) -> dict[str, Any]:
    prefixes = synthetic_prefixes()
    class_a: list[dict[str, Any]] = []
    class_b: list[dict[str, Any]] = []
    class_c: list[dict[str, Any]] = []
    class_q: list[dict[str, Any]] = []

    if _table_exists(conn, "chat_sessions"):
        sessions = conn.execute(
            "SELECT id, user_id, title, created_at FROM chat_sessions",
        ).fetchall()
        for sess in sessions:
            sid = sess["id"]
            user_msgs = conn.execute(
                """
                SELECT content FROM chat_messages
                WHERE session_id = ? AND role = 'user'
                ORDER BY id
                """,
                (sid,),
            ).fetchall() if _table_exists(conn, "chat_messages") else []
            if not user_msgs:
                any_msg = conn.execute(
                    "SELECT 1 FROM chat_messages WHERE session_id = ? LIMIT 1",
                    (sid,),
                ).fetchone() if _table_exists(conn, "chat_messages") else None
                if not any_msg:
                    class_c.append(
                        {
                            "id": sid,
                            "created_at": sess["created_at"],
                            "title": sess["title"],
                            "sample": "",
                        },
                    )
                continue
            if all(is_synthetic_user_content(r["content"], prefixes) for r in user_msgs):
                sample = (user_msgs[0]["content"] or "")[:60]
                class_a.append(
                    {
                        "id": sid,
                        "created_at": sess["created_at"],
                        "title": sess["title"],
                        "sample": sample,
                    },
                )

    if _table_exists(conn, "user_health_background_notes"):
        notes = conn.execute(
            """
            SELECT id, category, created_at, content
            FROM user_health_background_notes
            """,
        ).fetchall()
        for note in notes:
            sample = {
                "id": note["id"],
                "created_at": note["created_at"],
                "title": note["category"],
                "sample": (note["content"] or "")[:60],
            }
            if is_polluted_note_content(note["content"], prefixes):
                class_b.append(sample)
            elif note_hits_capture_negative(note["content"] or ""):
                class_q.append(sample)

    return {
        "A": class_a,
        "B": class_b,
        "C": class_c,
        "Q": class_q,
        "prefixes": prefixes,
    }


def _print_class(label: str, rows: list[dict[str, Any]], *, limit: int = 5) -> None:
    print(f"{label}: {len(rows)}")
    for row in rows[:limit]:
        sample = (row.get("sample") or "").replace("\n", " ")
        print(
            f"  id={row.get('id')} at={row.get('created_at')} "
            f"title={row.get('title')!r} sample={sample!r}",
        )
    if len(rows) > limit:
        print(f"  … {len(rows) - limit} more")


def backup_db(db_path: Path) -> Path:
    backup_dir = ROOT / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = backup_dir / f"pha_storage.{stamp}.db"
    shutil.copy2(db_path, dest)
    return dest


def apply_deletes(
    conn: sqlite3.Connection,
    classified: dict[str, Any],
    *,
    include_empty: bool,
) -> dict[str, int]:
    deleted = {"A": 0, "B": 0, "C": 0, "Q": 0}
    a_ids = [r["id"] for r in classified["A"]]
    b_ids = [r["id"] for r in classified["B"]]
    q_ids = [r["id"] for r in classified.get("Q") or []]
    c_ids = [r["id"] for r in classified["C"]] if include_empty else []
    if a_ids:
        placeholders = ",".join("?" * len(a_ids))
        for table in (
            "chat_messages",
            "chat_session_turn_focus",
            "chat_session_active_recall",
        ):
            if _table_exists(conn, table):
                conn.execute(
                    f"DELETE FROM {table} WHERE session_id IN ({placeholders})",
                    a_ids,
                )
        if _table_exists(conn, "chat_sessions"):
            conn.execute(
                f"DELETE FROM chat_sessions WHERE id IN ({placeholders})",
                a_ids,
            )
        deleted["A"] = len(a_ids)
    if b_ids and _table_exists(conn, "user_health_background_notes"):
        placeholders = ",".join("?" * len(b_ids))
        conn.execute(
            f"DELETE FROM user_health_background_notes WHERE id IN ({placeholders})",
            b_ids,
        )
        deleted["B"] = len(b_ids)
    if q_ids and _table_exists(conn, "user_health_background_notes"):
        placeholders = ",".join("?" * len(q_ids))
        conn.execute(
            f"DELETE FROM user_health_background_notes WHERE id IN ({placeholders})",
            q_ids,
        )
        deleted["Q"] = len(q_ids)
    if c_ids and _table_exists(conn, "chat_sessions"):
        placeholders = ",".join("?" * len(c_ids))
        conn.execute(
            f"DELETE FROM chat_sessions WHERE id IN ({placeholders})",
            c_ids,
        )
        deleted["C"] = len(c_ids)
    conn.commit()
    return deleted


def run(
    *,
    db_path: Path | None = None,
    apply: bool = False,
    include_empty: bool = False,
) -> dict[str, Any]:
    path = Path(db_path) if db_path else get_db_path()
    if not path.is_file():
        raise FileNotFoundError(f"database not found: {path}")
    conn = connect(path)
    try:
        classified = classify(conn)
        print(f"db={path}")
        _print_class("A interpret-only sessions", classified["A"])
        _print_class("B polluted background notes", classified["B"])
        _print_class("C empty sessions (kept unless --include-empty)", classified["C"])
        _print_class(
            "Q capture-negative question notes (deleted on --apply)",
            classified.get("Q") or [],
        )
        if not apply:
            print("dry-run: no deletes")
            return {"db": str(path), "classified": classified, "applied": False}
        backup = None
        try:
            live = get_db_path().resolve()
        except Exception:
            live = None
        if live is not None and path.resolve() == live:
            backup = backup_db(path)
            print(f"backup={backup}")
        deleted = apply_deletes(conn, classified, include_empty=include_empty)
        after = classify(conn)
        print(
            f"after A={len(after['A'])} B={len(after['B'])} C={len(after['C'])} "
            f"Q={len(after.get('Q') or [])} deleted={deleted}",
        )
        return {
            "db": str(path),
            "classified": classified,
            "applied": True,
            "backup": str(backup),
            "deleted": deleted,
            "after": after,
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="SQLite path (default: PHA storage)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete classified rows (copies DB to data/backups first)",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Also delete class C empty sessions",
    )
    args = parser.parse_args()
    run(db_path=args.db, apply=args.apply, include_empty=args.include_empty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
