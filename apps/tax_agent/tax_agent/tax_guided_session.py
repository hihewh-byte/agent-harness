"""Guided filing wizard session persistence (Tax Chat Experience v2 · C4)."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tax_agent.harness_plan import JourneyPhase

_GUIDED_STEPS: tuple[JourneyPhase, ...] = (
    "collecting",
    "ready",
    "computed",
    "reviewing",
    "export",
)


def _db_path() -> Path:
    env = os.environ.get("TAX_AGENT_DB")
    if env:
        return Path(env)
    data_dir = Path(__file__).resolve().parent.parent / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tax_agent.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tax_guided_session (
    session_id TEXT PRIMARY KEY,
    guided_step TEXT NOT NULL DEFAULT 'collecting',
    wizard_active INTEGER NOT NULL DEFAULT 0,
    tax_year INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_tax_guided_session_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


@dataclass
class TaxGuidedSession:
    session_id: str
    guided_step: JourneyPhase
    wizard_active: bool
    tax_year: int
    updated_at: str = ""


def _step_index(step: str) -> int:
    try:
        return _GUIDED_STEPS.index(step)  # type: ignore[arg-type]
    except ValueError:
        return 0


def max_guided_step(a: str, b: str) -> JourneyPhase:
    ia, ib = _step_index(a), _step_index(b)
    return _GUIDED_STEPS[max(ia, ib)]


def get_tax_guided_session(session_id: str) -> TaxGuidedSession | None:
    sid = (session_id or "").strip()
    if not sid:
        return None
    init_tax_guided_session_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT session_id, guided_step, wizard_active, tax_year, updated_at "
            "FROM tax_guided_session WHERE session_id = ?",
            (sid,),
        ).fetchone()
    if not row:
        return None
    return TaxGuidedSession(
        session_id=row["session_id"],
        guided_step=row["guided_step"] or "collecting",
        wizard_active=bool(row["wizard_active"]),
        tax_year=int(row["tax_year"] or 0),
        updated_at=row["updated_at"] or "",
    )


def save_tax_guided_session(
    session_id: str,
    *,
    guided_step: JourneyPhase,
    wizard_active: bool = True,
    tax_year: int = 0,
) -> None:
    sid = (session_id or "").strip()
    if not sid:
        return
    init_tax_guided_session_schema()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tax_guided_session (session_id, guided_step, wizard_active, tax_year, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                guided_step = excluded.guided_step,
                wizard_active = excluded.wizard_active,
                tax_year = excluded.tax_year,
                updated_at = excluded.updated_at
            """,
            (sid, guided_step, 1 if wizard_active else 0, int(tax_year), now),
        )
        conn.commit()


def clear_tax_guided_session(session_id: str) -> None:
    sid = (session_id or "").strip()
    if not sid:
        return
    init_tax_guided_session_schema()
    with _connect() as conn:
        conn.execute("DELETE FROM tax_guided_session WHERE session_id = ?", (sid,))
        conn.commit()
