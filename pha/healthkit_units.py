"""Normalize HealthKit / Shortcuts units onto warehouse units. Fail-closed."""

from __future__ import annotations

import math
import re
from typing import Optional

from pha.sqlite_storage import (
    METRIC_ACTIVE_ENERGY,
    METRIC_HRV_SDNN,
    METRIC_RESPIRATORY_RATE,
    METRIC_RHR,
    METRIC_SPO2,
    METRIC_STEPS,
    METRIC_VO2MAX,
    METRIC_WRIST_TEMP,
)

_UNIT_FOLD_RE = re.compile(r"[^a-z0-9%]+")


def _primary_unit(raw: str) -> str:
    """Shortcuts Get Details Unit on a list concatenates every sample's unit."""
    text = (raw or "").replace("\r", "\n").strip()
    if not text:
        return ""
    first_line = text.split("\n", 1)[0].strip()
    parts = first_line.split()
    return parts[0] if parts else first_line


def _fold_unit(raw: str) -> str:
    text = _primary_unit(raw).lower().replace("µ", "u").replace("μ", "u")
    text = text.replace("°", "").replace("º", "")
    return _UNIT_FOLD_RE.sub("", text)


def _require_finite(value: float, *, metric: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"implausible_{metric}:non_finite")
    return float(value)


def normalize_ingest_value(metric: str, value: float, unit: Optional[str]) -> float:
    """Convert a posted sample to the warehouse unit for ``metric``.

    Unknown units raise ``ValueError``. Magnitude gates match ``data_integrity``.
    """
    n = _require_finite(value, metric=metric or "value")
    folded = _fold_unit(unit or "")
    if metric == METRIC_SPO2:
        return _as_spo2_percent(n, folded)
    if metric == METRIC_RESPIRATORY_RATE:
        return _as_respiratory_bpm(n, folded)
    if metric == METRIC_WRIST_TEMP:
        return _as_wrist_c(n, folded)
    if metric == METRIC_VO2MAX:
        return _as_vo2max(n, folded)
    if metric == METRIC_RHR:
        if folded and folded not in {"countmin", "bpm", "beatsmin", "count"}:
            raise ValueError(f"unknown_unit:{unit}")
        if n < 30 or n > 220:
            raise ValueError("implausible_rhr")
        return n
    if metric == METRIC_HRV_SDNN:
        if folded and folded not in {"ms", "msec", "milliseconds"}:
            raise ValueError(f"unknown_unit:{unit}")
        if n <= 0 or n > 500:
            raise ValueError("implausible_hrv")
        return n
    if metric == METRIC_STEPS:
        if folded and folded not in {"count", "steps", "step"}:
            raise ValueError(f"unknown_unit:{unit}")
        if n < 0 or n > 60_000:
            raise ValueError("implausible_steps")
        return n
    if metric == METRIC_ACTIVE_ENERGY:
        if folded and folded not in {"kcal", "cal", "kilocalories", "calories"}:
            raise ValueError(f"unknown_unit:{unit}")
        if n < 0 or n > 20_000:
            raise ValueError("implausible_active_energy")
        return n
    return n


def _as_spo2_percent(value: float, folded: str) -> float:
    if folded in {"", "percent", "%", "pct"}:
        pct = value * 100.0 if 0 < value <= 1.5 else value
    elif folded in {"fraction", "ratio"}:
        pct = value * 100.0
    else:
        raise ValueError(f"unknown_unit:{folded or 'empty'}")
    if pct < 50 or pct > 100:
        raise ValueError("implausible_spo2")
    return pct


def _as_respiratory_bpm(value: float, folded: str) -> float:
    if folded in {"counts", "hz"}:
        bpm = value * 60.0
    elif folded in {"", "countmin", "breathsmin", "brpm", "bpm", "count"}:
        bpm = value
    else:
        raise ValueError(f"unknown_unit:{folded or 'empty'}")
    if bpm <= 0 or bpm > 40:
        raise ValueError("implausible_respiratory_rate")
    return bpm


def _as_wrist_c(value: float, folded: str) -> float:
    if folded in {"f", "degf", "fahrenheit"}:
        celsius = (value - 32.0) * 5.0 / 9.0
    elif folded in {"", "c", "degc", "celsius", "degreescelsius"}:
        celsius = value if value < 45 else (value - 32.0) * 5.0 / 9.0
    else:
        raise ValueError(f"unknown_unit:{folded or 'empty'}")
    if celsius < 30 or celsius > 42:
        raise ValueError("implausible_wrist_temp")
    return celsius


def _as_vo2max(value: float, folded: str) -> float:
    if folded and "ml" not in folded and folded not in {"vo2max"}:
        raise ValueError(f"unknown_unit:{folded}")
    if value < 10 or value > 90:
        raise ValueError("implausible_vo2max")
    return value


__all__ = ["normalize_ingest_value"]
