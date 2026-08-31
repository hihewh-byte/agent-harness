"""Fetch USD/CNY PBOC central parity rates and merge into curated dataset."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "pboc_usd_cny_middle.yaml"

# China Foreign Exchange Trade System — historical central parity (month-end last publish)
CHINAMONEY_HIS_URL = (
    "https://www.chinamoney.com.cn/ags/ms/hisUsdCnyCentralParity"
    "?startDate={start}&endDate={end}&pageNum=1&pageSize=10000"
)


def _repo_data_path(path: Path | None = None) -> Path:
    return path or DEFAULT_DATA


def load_pboc_dataset(path: Path | None = None) -> dict[str, Any]:
    p = _repo_data_path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def save_pboc_dataset(data: dict[str, Any], path: Path | None = None) -> Path:
    p = _repo_data_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return p


def _month_end_dates(year: int, month: int) -> tuple[str, str]:
    """Return (start, end) query range covering the month's last business day."""
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    last = nxt.fromordinal(nxt.toordinal() - 1)
    start = date(year, month, 1)
    return start.isoformat(), last.isoformat()


def _parse_chinamoney_payload(payload: Any) -> list[tuple[str, Decimal]]:
    """Parse chinamoney JSON into (YYYY-MM-DD, rate) pairs."""
    records = payload
    if isinstance(payload, dict):
        records = payload.get("records") or payload.get("data") or payload.get("list") or []
    out: list[tuple[str, Decimal]] = []
    if not isinstance(records, list):
        return out
    for row in records:
        if not isinstance(row, dict):
            continue
        d = str(row.get("date") or row.get("tradeDate") or row.get("showDateCN") or "").strip()
        rate_raw = row.get("middleRate") or row.get("centralParity") or row.get("value")
        if not d or rate_raw is None:
            continue
        d = d.replace("/", "-")[:10]
        try:
            out.append((d, Decimal(str(rate_raw))))
        except Exception:
            continue
    return out


def fetch_month_end_rate(year: int, month: int, *, timeout: float = 30.0) -> tuple[str, Decimal] | None:
    """
    Fetch last published central parity in the given calendar month.
    Returns (YYYY-MM, rate) using the last trading day in range.
    """
    start, end = _month_end_dates(year, month)
    url = CHINAMONEY_HIS_URL.format(start=start, end=end)
    headers = {"User-Agent": "TaxAgent/1.0 (PBOC rate sync)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    pairs = _parse_chinamoney_payload(payload)
    if not pairs:
        # fallback: parse HTML-ish fragments in text
        text = resp.text
        found = re.findall(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"[^}]*?"middleRate"\s*:\s*"?([\d.]+)"?', text)
        pairs = [(d, Decimal(r)) for d, r in found]
    if not pairs:
        return None
    pairs.sort(key=lambda x: x[0])
    last_date, rate = pairs[-1]
    mk = f"{year}-{month:02d}"
    return mk, rate


def merge_monthly_rates(
    new_rates: dict[str, str | Decimal],
    *,
    path: Path | None = None,
    source_note: str | None = None,
) -> dict[str, Any]:
    """Merge new monthly rates into pboc_usd_cny_middle.yaml; returns updated dict."""
    data = load_pboc_dataset(path)
    monthly = dict(data.get("monthly") or {})
    changed: list[str] = []
    for mk, val in sorted(new_rates.items()):
        sval = str(val)
        if monthly.get(mk) != sval:
            monthly[mk] = sval
            changed.append(mk)
    data["monthly"] = monthly
    data["lastSyncedAt"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    if source_note:
        data["lastSyncSource"] = source_note
    if changed:
        data["version"] = datetime.utcnow().strftime("%Y.%m.%d")
    save_pboc_dataset(data, path)
    data["_changedMonths"] = changed
    return data


def sync_recent_months(
    *,
    months_back: int = 3,
    path: Path | None = None,
) -> dict[str, Any]:
    """Fetch and merge recent month-end rates."""
    today = date.today()
    new_rates: dict[str, str] = {}
    errors: list[str] = []
    y, m = today.year, today.month
    for _ in range(months_back):
        try:
            got = fetch_month_end_rate(y, m)
            if got:
                mk, rate = got
                new_rates[mk] = str(rate)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{y}-{m:02d}:{exc}")
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    merged = merge_monthly_rates(new_rates, path=path, source_note="chinamoney_hisUsdCnyCentralParity")
    merged["_errors"] = errors
    return merged
