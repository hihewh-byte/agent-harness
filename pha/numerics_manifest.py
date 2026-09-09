"""Numerics Manifest + C-layer post-check — v2.2.6.2-min (Catalog Reduce 共享底座)."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, TypedDict

from pha.date_range_parser import default_wearable_window
from pha.health_data import HealthDataResult, effective_query_reference_date, get_health_data
from pha.intent_gates import infer_wearable_metrics
from pha.medical_storage import sanitize_ldl_value

_MANIFEST_MAX_CHARS = int(os.environ.get("PHA_MANIFEST_MAX_CHARS", "600"))

# Known E2E hallucination anchors — always forbidden in model output.
_GLOBAL_FORBIDDEN_DATES: frozenset[str] = frozenset({"2026-04-30", "2025-01-13"})

_WEARABLE_MANIFEST_FORBIDDEN_FOOTER = (
    "FORBIDDEN_90D: sleep_deep_avg, sleep_rem_avg, deep_sleep_90d, rem_sleep_90d "
    "（数仓无睡眠分期历史均值；90 天对比见 WEARABLE_COMPARE_TABLE）"
)

_LIPID_SQL = """
SELECT report_date, metric_name, metric_code, name_zh, value, unit
FROM medical_reports
WHERE user_id = ?
  AND value IS NOT NULL
  AND (
    lower(coalesce(metric_name,'')) LIKE '%胆固醇%'
    OR lower(coalesce(metric_name,'')) LIKE '%ldl%'
    OR lower(coalesce(metric_name,'')) LIKE '%hdl%'
    OR lower(coalesce(metric_name,'')) LIKE '%甘油三酯%'
    OR lower(coalesce(metric_code,'')) IN ('ldl','hdl','tc','tg')
    OR lower(coalesce(name_zh,'')) LIKE '%胆固醇%'
    OR lower(coalesce(name_zh,'')) LIKE '%甘油三酯%'
  )
ORDER BY report_date ASC, metric_name
"""

_DATE_ISO_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_DATE_CN_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
_DATE_CN_MD_RE = re.compile(r"(?<!年)(\d{1,2})月\s*(\d{1,2})日")
_DATE_EN_RE = re.compile(
    r"\b("
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
    r")\.?\s+(\d{1,2})(?:,?\s*(20\d{2}))?\b",
    re.I,
)
_EN_MONTH_NUM = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
# 中文语境无词边界：用前后非数字锚定，避免 \b 失效
_DECIMAL_RE = re.compile(r"(?<!\d)(\d+\.\d{1,2})(?!\d)")
_DOSE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:g|mg|ml|mcg|μg|ug|fu|iu|粒|片|根|次|%)\b",
    re.I,
)

# --- Manifest Tier v1: bilingual disclosure sandbox (extend via LANG_DISCLOSURE_MAP only) ---
# Future: add LANG_DISCLOSURE_MAP entries (e.g. id="ja") + compile in _disclosure_patterns();
# do not scatter locale strings in audit_* call paths.


class _LangDisclosureSpec(TypedDict):
    id: str
    block_open_re: str
    block_full_re: str
    source_re: str
    verify_substrings: Tuple[str, ...]
    disclaimer_substrings: Tuple[str, ...]
    t0_forbidden_in_block_re: str


LANG_DISCLOSURE_MAP: Tuple[_LangDisclosureSpec, ...] = (
    {
        "id": "zh",
        "block_open_re": r"【参考标准[^】]*】",
        "block_full_re": (
            r"【参考标准[^】]*】.*?"
            r"[（(]来源[:：][^）)]{4,}[，,][^）)]*?"
            r"(?:请自行查证|请自行核对)[^）)]*?[）)]"
        ),
        "source_re": r"来源[:：]\s*.{4,}",
        "verify_substrings": ("请自行查证", "请自行核对"),
        "disclaimer_substrings": ("非医疗建议", "不构成医疗建议", "不能替代医嘱"),
        "t0_forbidden_in_block_re": (
            r"您的|你的是|你的|化验日期|报告日期|检验报告|上次化验|个人化验"
        ),
    },
    {
        "id": "en",
        "block_open_re": r"\[(?:Reference Standard|Ref\.?\s*Standard)[^\]]*\]",
        "block_full_re": (
            r"\[(?:Reference Standard|Ref\.?\s*Standard)[^\]]*\].*?"
            r"[\(（]\s*source\s*[:：]\s*[^）)]{4,}\s*[,，]\s*"
            r"(?:verify by yourself|please verify independently|verify independently)"
            r"[^）)]*?[）)]"
        ),
        "source_re": r"source\s*[:：]\s*.{4,}",
        "verify_substrings": (
            "verify by yourself",
            "please verify independently",
            "verify independently",
        ),
        "disclaimer_substrings": (
            "not medical advice",
            "not a substitute for medical advice",
        ),
        "t0_forbidden_in_block_re": (
            r"\byour\b|\byours\b|your lab|your report|report date|test date|"
            r"personal lab|my lab results"
        ),
    },
)

# T0 claim cues — evaluated on masked text; T0 always wins over T1 (see audit priority).
FACT_CARD_AUDIT_POLICY_REV = "v1.1"

LANG_T0_CLAIM_MAP: Dict[str, Tuple[str, ...]] = {
    "owner_cues": (
        "您的",
        "你的",
        "你的是",
        "your",
        "yours",
        "your lab",
        "your ldl",
    ),
    "report_cues": (
        "报告",
        "化验",
        "检验",
        "report",
        "lab result",
        "test result",
    ),
    "metric_cues": (
        "LDL",
        "HDL",
        "TC",
        "TG",
        "血脂",
        "胆固醇",
        "HRV",
        "spo2",
        "blood oxygen",
    ),
    "lab_citation_cues": (
        "报告",
        "化验",
        "检验",
        "LDL",
        "HDL",
        "TC",
        "TG",
        "血脂",
        "胆固醇",
        "mmol",
        "mg/dL",
        "report",
        "lab",
    ),
    "temporal_cues": (
        "今天",
        "今晨",
        "昨天",
        "昨夜",
        "本周",
        "上周",
        "最近",
        "过去",
        "近",
        "today",
        "tonight",
        "yesterday",
        "this week",
        "recent",
        "last",
    ),
    "educational_cues": (
        "一般",
        "通常",
        "常见",
        "多数人",
        "健康成年人",
        "人群",
        "建议",
        "推荐",
        "可以",
        "尽量",
        "控制在",
        "保持在",
        "目标",
        "不超过",
        "参考",
        "范围",
        "区间",
        "阈值",
        "指南",
        "typical",
        "usually",
        "most adults",
        "general population",
        "recommend",
        "aim for",
        "keep",
        "try to",
        "target",
        "up to",
        "reference",
        "range",
        "threshold",
        "guideline",
    ),
    "measurement_cues": (
        "测得",
        "记录",
        "显示",
        "读数",
        "卡上",
        "均值",
        "中位",
        "基线",
        "measured",
        "recorded",
        "shows",
        "reading",
        "baseline",
        "median",
    ),
}

_DISCLOSURE_COMPILED: Optional[List[Dict[str, Any]]] = None

_LAB_RANGE_MIN = 0.5
_LAB_RANGE_MAX = 15.0

_METRIC_CANON: List[tuple[str, str]] = [
    ("tc", "TC"),
    ("总胆固醇", "TC"),
    ("ldl", "LDL"),
    ("低密度", "LDL"),
    ("hdl", "HDL"),
    ("高密度", "HDL"),
    ("tg", "TG"),
    ("甘油三酯", "TG"),
]


def _db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "pha_storage.db"


def _canonical_lipid_metric(name: str, code: str, zh: str) -> Optional[str]:
    blob = f"{name}|{code}|{zh}".lower()
    for needle, canon in _METRIC_CANON:
        if needle in blob:
            return canon
    return None


def _fmt_value(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _value_variants(v: float) -> Set[str]:
    out = {_fmt_value(v), f"{v:.1f}", f"{v:.2f}"}
    if abs(v - round(v)) < 1e-6:
        out.add(str(int(round(v))))
    return {x for x in out if x}


@dataclass(frozen=True)
class ManifestEntry:
    domain: str
    metric: str
    value: float
    unit: str
    anchor: str
    source: str

    def kv_line(self) -> str:
        return f"{self.domain}|{self.anchor}|{self.metric}|{_fmt_value(self.value)}|{self.unit or '-'}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "anchor": self.anchor,
            "source": self.source,
        }


@dataclass
class NumericsManifest:
    profile: str
    user_id: str
    entries: List[ManifestEntry] = field(default_factory=list)
    reference_date: str = ""
    forbidden_dates: Set[str] = field(default_factory=set)
    wearable_grain_source: str = "default"
    wearable_window_start: str = ""
    wearable_window_end: str = ""
    card_labels: Set[str] = field(default_factory=set)
    card_units: Set[str] = field(default_factory=set)
    window_day_tokens: Set[str] = field(default_factory=set)
    card_times: Set[str] = field(default_factory=set)

    @property
    def allowed_dates(self) -> Set[str]:
        dates: Set[str] = set()
        for e in self.entries:
            if e.domain == "lipid" and len(e.anchor) == 10:
                dates.add(e.anchor)
            elif e.domain == "fact_card":
                for iso in _DATE_ISO_RE.findall(e.anchor or ""):
                    dates.add(iso)
        if self.profile == "fact_card_interpret" and len(self.reference_date or "") == 10:
            dates.add(self.reference_date)
        return dates

    @property
    def allowed_values(self) -> Set[str]:
        vals: Set[str] = set()
        for e in self.entries:
            vals.update(_value_variants(e.value))
        return vals

    @property
    def lipid_values(self) -> Set[str]:
        vals: Set[str] = set()
        for e in self.entries:
            if e.domain == "lipid":
                vals.update(_value_variants(e.value))
        return vals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "user_id": self.user_id,
            "reference_date": self.reference_date,
            "entry_count": len(self.entries),
            "allowed_dates": sorted(self.allowed_dates),
            "entries": [e.to_dict() for e in self.entries],
            "forbidden_dates": sorted(self.forbidden_dates),
            "wearable_grain_source": self.wearable_grain_source,
            "wearable_window_start": self.wearable_window_start,
            "wearable_window_end": self.wearable_window_end,
            "card_labels": sorted(self.card_labels),
            "card_units": sorted(self.card_units),
            "window_day_tokens": sorted(self.window_day_tokens),
            "card_times": sorted(self.card_times),
        }


def _query_lipid_rows(user_id: str) -> List[Dict[str, Any]]:
    db = _db_path()
    if not db.exists():
        return []
    uid = (user_id or "default").strip() or "default"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(_LIPID_SQL, (uid,))
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return []
        raise
    finally:
        conn.close()


def _lipid_entries(user_id: str) -> List[ManifestEntry]:
    rows = _query_lipid_rows(user_id)
    out: List[ManifestEntry] = []
    seen: Set[tuple[str, str, str]] = set()
    for r in rows:
        canon = _canonical_lipid_metric(
            str(r.get("metric_name") or ""),
            str(r.get("metric_code") or ""),
            str(r.get("name_zh") or ""),
        )
        if not canon:
            continue
        raw_val = r.get("value")
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            continue
        if canon == "LDL":
            sv = sanitize_ldl_value(val)
            if sv is None:
                continue
            val = sv
        anchor = str(r.get("report_date") or "")[:10]
        if not anchor or len(anchor) != 10:
            continue
        key = (anchor, canon, _fmt_value(val))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            ManifestEntry(
                domain="lipid",
                metric=canon,
                value=val,
                unit=str(r.get("unit") or "mmol/L").strip() or "mmol/L",
                anchor=anchor,
                source="sqlite.medical_reports",
            ),
        )
    return out


def _wearable_entries(
    user_id: str,
    user_message: str,
    *,
    wearable_result: Optional[HealthDataResult] = None,
) -> List[ManifestEntry]:
    uid = (user_id or "default").strip() or "default"
    ref = effective_query_reference_date()
    window = default_wearable_window(user_message, reference=ref)
    anchor = f"{window.start.isoformat()}~{window.end.isoformat()}"

    if wearable_result is None or window.start == window.end:
        metrics = infer_wearable_metrics(user_message)
        if not metrics:
            # Registry-hint focus (e.g. 「呼吸正常吗」) may not hit catalog triggers;
            # map focus metric_ids → catalog keys so we do not fall back to hrv+kcal.
            from pha.wearable_compare_table_v1 import infer_single_metric_focus_ids

            _focus_to_cat = {
                "sleep_time_asleep": "sleep",
                "hrv_rmssd_ms": "hrv",
                "hrv_sdnn_ms": "hrv",
                "resting_heart_rate_bpm": "rhr",
                "spo2_percent": "spo2",
                "respiratory_rate": "respiratory_rate",
            }
            metrics = [
                _focus_to_cat[mid]
                for mid in infer_single_metric_focus_ids(user_message)
                if mid in _focus_to_cat
            ]
        if not metrics:
            metrics = ["hrv", "activity_kcal"]
        wearable_result = get_health_data(
            uid,
            window.start,
            window.end,
            metrics,
            user_message=user_message,
        )

    out: List[ManifestEntry] = []
    same_day = window.start == window.end
    point_prefix = "今日" if same_day and window.end == ref else "当日"
    if same_day:
        anchor = window.start.isoformat()
        label_map = {
            "hrv": (f"{point_prefix}HRV", "ms"),
            "activity_kcal": (f"{point_prefix}活动消耗", "kcal"),
            "steps": (f"{point_prefix}步数", "步"),
            "sleep": (f"{point_prefix}睡眠", "h"),
            "rhr": (f"{point_prefix}静息心率", "bpm"),
            "spo2": (f"{point_prefix}血氧", "%"),
            "respiratory_rate": (f"{point_prefix}呼吸率", "breaths/min"),
            "vo2max": (f"{point_prefix}VO2max", "mL/kg/min"),
            "wrist_temp": (f"{point_prefix}手腕体温", "°C"),
        }
    else:
        label_map = {
            "hrv": ("HRV均值", "ms"),
            "activity_kcal": ("活动消耗日均", "kcal"),
            "steps": ("步数均值", "步"),
            "sleep": ("睡眠均值", "h"),
            "rhr": ("静息心率均值", "bpm"),
            "spo2": ("血氧均值", "%"),
            "respiratory_rate": ("呼吸率均值", "breaths/min"),
            "vo2max": ("VO2max均值", "mL/kg/min"),
            "wrist_temp": ("手腕体温均值", "°C"),
        }
    for key, summary in (wearable_result.summaries or {}).items():
        avg = summary.average
        if avg is None:
            continue
        metric_key = str(key).strip().lower()
        label, unit = label_map.get(metric_key, (metric_key, summary.unit or ""))
        out.append(
            ManifestEntry(
                domain="wearable",
                metric=label,
                value=round(float(avg), 2),
                unit=unit or str(summary.unit or ""),
                anchor=anchor,
                source="wearable.summary" if not same_day else "wearable.daily",
            ),
        )
    return out


def build_numerics_manifest(
    user_id: str,
    *,
    profile: str,
    user_message: str = "",
    wearable_result: Optional[HealthDataResult] = None,
    include_lipid: bool = True,
    include_wearable: bool = True,
) -> NumericsManifest:
    """Build machine-verifiable numerics whitelist for the current turn."""
    ref = effective_query_reference_date()
    forbidden = set(_GLOBAL_FORBIDDEN_DATES)
    entries: List[ManifestEntry] = []
    from pha.wearable_time_grain import resolve_wearable_time_grain

    grain = resolve_wearable_time_grain(user_message, reference=ref)

    if include_lipid and profile in ("combined_review", "lab_cross_year", "lifestyle"):
        entries.extend(_lipid_entries(user_id))

    if include_wearable and profile in (
        "combined_review",
        "wearable_only",
        "wearable_screenshot_review",
    ):
        entries.extend(
            _wearable_entries(user_id, user_message, wearable_result=wearable_result),
        )

    return NumericsManifest(
        profile=profile,
        user_id=(user_id or "default").strip() or "default",
        entries=entries,
        reference_date=ref.isoformat(),
        forbidden_dates=forbidden,
        wearable_grain_source=grain.source,
        wearable_window_start=grain.start.isoformat(),
        wearable_window_end=grain.end.isoformat(),
    )


def _window_short(window: Optional[str], *, night: bool) -> str:
    if window == "90d":
        return "近 90 日"
    if window == "365d":
        return "近 12 个月"
    if window == "all":
        return "全部历史"
    return "个人历史"


def _is_night_metric_id(metric_id: str) -> bool:
    return metric_id.startswith("sleep_") or metric_id == "sleep_time_asleep"


_BASELINE_WINDOW_DAYS_RE = re.compile(r"^(\d+)d$")


def build_fact_card_numerics_manifest(
    card: Dict[str, Any],
    *,
    user_id: str = "default",
) -> NumericsManifest:
    """Whitelist built only from the day's fact card — not the 90-day wearable summary."""
    facts = card.get("facts") or {}
    as_of = str(facts.get("as_of") or "")[:10]
    calendar_day = str(facts.get("calendar_day") or "")[:10]
    entries: List[ManifestEntry] = []
    card_labels: Set[str] = set()
    card_units: Set[str] = set()
    window_day_tokens: Set[str] = set()
    card_times: Set[str] = set()
    for item in facts.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("metric") or "").strip()
        if label:
            card_labels.add(label)
        for loc_key in ("label_en", "label_zh"):
            loc_label = str(item.get(loc_key) or "").strip()
            if loc_label:
                card_labels.add(loc_label)
        metric_id = str(item.get("metric") or "")
        unit = str(item.get("unit") or "-") or "-"
        if unit and unit != "-":
            card_units.add(unit)
        day = str(item.get("day") or as_of or "")[:10]
        stamp = str(item.get("as_of_time") or "").strip()
        if stamp:
            card_times.add(stamp)
        bw = str(item.get("baseline_window") or "").strip()
        bw_m = _BASELINE_WINDOW_DAYS_RE.match(bw)
        if bw_m:
            window_day_tokens.add(bw_m.group(1))
            if bw == "365d":
                window_day_tokens.add("12")
            elif bw == "7d":
                window_day_tokens.add("7")
            elif bw == "90d":
                window_day_tokens.add("90")
        value = item.get("value")
        if value is not None:
            anchor = day or as_of or "-"
            if item.get("partial_day") and stamp:
                anchor = f"{anchor}·截至{stamp}"
            entries.append(
                ManifestEntry(
                    domain="fact_card",
                    metric=label or metric_id,
                    value=float(value),
                    unit=unit,
                    anchor=anchor,
                    source="fact_card",
                )
            )
        night = _is_night_metric_id(metric_id)
        short = _window_short(bw, night=night)
        earliest = str(item.get("baseline_earliest") or "")[:10]
        end = as_of or day
        baseline_anchor = f"{earliest}~{end}" if earliest and end else (end or earliest or "-")
        n_unit = "nights" if night else "days"
        for key, suffix in (
            ("baseline_mean", f"{short}均值"),
            ("baseline_min", f"{short}最低"),
            ("baseline_max", f"{short}最高"),
            ("percentile", "百分位"),
        ):
            raw = item.get(key)
            if raw is None:
                continue
            entries.append(
                ManifestEntry(
                    domain="fact_card",
                    metric=f"{label}·{suffix}",
                    value=float(raw),
                    unit="pct" if key == "percentile" else unit,
                    anchor=baseline_anchor,
                    source="fact_card_baseline",
                )
            )
        baseline_n = item.get("baseline_n")
        if baseline_n is not None:
            entries.append(
                ManifestEntry(
                    domain="fact_card",
                    metric=f"{label}·基线{'夜数' if night else '天数'}",
                    value=float(int(baseline_n)),
                    unit=n_unit,
                    anchor=baseline_anchor,
                    source="fact_card_baseline",
                )
            )
        ref = item.get("reference") or {}
        if isinstance(ref, dict):
            ref_unit = str(ref.get("unit") or unit or "-") or "-"
            src = str(ref.get("source") or "registry")
            if ref.get("low") is not None:
                entries.append(
                    ManifestEntry(
                        domain="reference",
                        metric=f"{label}·参考下限",
                        value=float(ref["low"]),
                        unit=ref_unit,
                        anchor="-",
                        source=src,
                    )
                )
            if ref.get("high") is not None:
                entries.append(
                    ManifestEntry(
                        domain="reference",
                        metric=f"{label}·参考上限",
                        value=float(ref["high"]),
                        unit=ref_unit,
                        anchor="-",
                        source=src,
                    )
                )

    cov_total: Any = None
    cov = facts.get("coverage")
    if isinstance(cov, dict):
        cov_total = cov.get("total") or cov.get("coverage_total")
    elif cov is not None and not isinstance(cov, (str, bytes)):
        try:
            cov_total = int(cov)
        except (TypeError, ValueError):
            cov_total = None
    if cov_total is None:
        summary = (card.get("assessment") or {}).get("summary") or {}
        if isinstance(summary, dict):
            cov_total = summary.get("coverage_total")
    if cov_total is not None:
        try:
            window_day_tokens.add(str(int(cov_total)))
        except (TypeError, ValueError):
            pass

    return NumericsManifest(
        profile="fact_card_interpret",
        user_id=(user_id or "default").strip() or "default",
        entries=entries,
        reference_date=as_of or calendar_day,
        forbidden_dates=set(_GLOBAL_FORBIDDEN_DATES),
        wearable_grain_source="default",
        wearable_window_start="",
        wearable_window_end="",
        card_labels=card_labels,
        card_units=card_units,
        window_day_tokens=window_day_tokens,
        card_times=card_times,
    )


def format_manifest_tier0_block(
    manifest: NumericsManifest,
    *,
    max_chars: Optional[int] = None,
    profile: str = "",
) -> str:
    cap = max_chars if max_chars is not None else _MANIFEST_MAX_CHARS
    if not manifest.entries:
        empty = (
            "【Numerics Manifest · T0 · 机器白名单】\n"
            "Numerics Manifest (T0): no verifiable lipid/wearable values in DB this turn.\n"
            "（本轮库内无血脂/穿戴可校验数值；禁止编造化验或 HRV/千卡数字。）\n"
            "T1 guide values: use 【参考标准】 or [Reference Standard] disclosure; not whitelisted here."
        )
        if (profile or manifest.profile or "").strip() == "wearable_screenshot_review":
            empty = f"{empty}\n{_WEARABLE_MANIFEST_FORBIDDEN_FOOTER}"
        return empty
    header = (
        "【T0 · 您的个人化验/穿戴实测值 · Personal lab/wearable values】\n"
        "Numerics Manifest (T0): reply citations must match KV below.\n"
        "格式 / format: domain|anchor|metric|value|unit\n"
        "T1 指南/理想线: 【参考标准】…（来源：…，请自行查证，非医疗建议） or "
        "[Reference Standard] … (source: …, verify by yourself, not medical advice).\n"
        "T0 主张优先于 T1：个人数据仅可引用下列 KV；参考值不得伪装成您的化验结果。"
    )
    lines = [header.strip()]
    for e in manifest.entries:
        lines.append(e.kv_line())
    body = "\n".join(lines)
    if len(body) <= cap:
        if (profile or manifest.profile or "").strip() == "wearable_screenshot_review":
            body = f"{body}\n{_WEARABLE_MANIFEST_FORBIDDEN_FOOTER}"
        return body
    trimmed = [header.strip()]
    for e in manifest.entries:
        line = e.kv_line()
        candidate = "\n".join(trimmed + [line])
        if len(candidate) > cap - 20:
            break
        trimmed.append(line)
    trimmed.append("…（Manifest 已按 Tier0 上限截断，仍以已列 KV 为唯一合法数字源）")
    body = "\n".join(trimmed)[:cap]
    if (profile or manifest.profile or "").strip() == "wearable_screenshot_review":
        body = f"{body}\n{_WEARABLE_MANIFEST_FORBIDDEN_FOOTER}"
    return body


def _normalize_cn_date(y: str, m: str, d: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def _normalize_en_date(month_token: str, day: str, year: str) -> Optional[str]:
    month = _EN_MONTH_NUM.get((month_token or "").strip(".").lower())
    if month is None or not year:
        return None
    try:
        return f"{int(year):04d}-{month:02d}-{int(day):02d}"
    except ValueError:
        return None


_EN_MONTH_NAMES: Dict[int, Tuple[str, ...]] = {
    1: ("January", "Jan", "Jan."),
    2: ("February", "Feb", "Feb."),
    3: ("March", "Mar", "Mar."),
    4: ("April", "Apr", "Apr."),
    5: ("May",),
    6: ("June", "Jun", "Jun."),
    7: ("July", "Jul", "Jul."),
    8: ("August", "Aug", "Aug."),
    9: ("September", "Sep", "Sept", "Sep.", "Sept."),
    10: ("October", "Oct", "Oct."),
    11: ("November", "Nov", "Nov."),
    12: ("December", "Dec", "Dec."),
}


def _resolve_month_day_iso(
    month: int,
    day: int,
    allowed: Set[str],
    *,
    reference_date: str = "",
) -> str:
    """Map month/day to ISO using card-allowed dates when present (FR-6.9)."""
    suffix = f"-{month:02d}-{day:02d}"
    hits = sorted(iso for iso in allowed if len(iso) == 10 and iso.endswith(suffix))
    if hits:
        return hits[-1]
    year = "2026"
    ref = (reference_date or "")[:10]
    if len(ref) == 10 and ref[4] == "-" and ref[7] == "-":
        year = ref[:4]
    else:
        for iso in sorted(allowed, reverse=True):
            if len(iso) == 10 and iso[4] == "-" and iso[7] == "-":
                year = iso[:4]
                break
    return f"{year}-{month:02d}-{day:02d}"


def _en_iso_surface_forms(iso: str) -> List[str]:
    """All common English spellings of an ISO date (with and without year)."""
    if len(iso) != 10 or iso[4] != "-" or iso[7] != "-":
        return [iso]
    try:
        y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    except ValueError:
        return [iso]
    forms: List[str] = [iso]
    for name in _EN_MONTH_NAMES.get(m, ()):
        forms.append(f"{name} {d}")
        forms.append(f"{name} {d}, {y}")
        forms.append(f"{name} {d} {y}")
    return forms


def _cn_iso_surface_forms(iso: str) -> List[str]:
    if len(iso) != 10 or iso[4] != "-" or iso[7] != "-":
        return []
    try:
        y, m, d = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    except ValueError:
        return []
    return [
        f"{y}年{m}月{d}日",
        f"{y}年{m:02d}月{d:02d}日",
        f"{y}年 {m}月 {d}日",
        f"{m}月{d}日",
        f"{m}月 {d}日",
    ]


def _extract_normalized_dates(text: str) -> List[str]:
    """Extract ISO + 中文/英文日期并统一为 YYYY-MM-DD。无年份的月日不在这里解析。"""
    found: List[str] = []
    for iso in _DATE_ISO_RE.findall(text or ""):
        found.append(iso)
    for y, m, d in _DATE_CN_RE.findall(text or ""):
        found.append(_normalize_cn_date(y, m, d))
    for mon, d, y in _DATE_EN_RE.findall(text or ""):
        iso = _normalize_en_date(mon, d, y)
        if iso:
            found.append(iso)
    return found


def _extract_fact_card_dates(
    text: str,
    allowed: Set[str],
    *,
    reference_date: str = "",
) -> List[str]:
    """Like `_extract_normalized_dates`, plus yearless EN/CN month-day resolved to card dates."""
    found = list(_extract_normalized_dates(text))
    for mon, d, y in _DATE_EN_RE.findall(text or ""):
        if y:
            continue
        month = _EN_MONTH_NUM.get((mon or "").strip(".").lower())
        if month is None:
            continue
        try:
            day = int(d)
        except ValueError:
            continue
        found.append(
            _resolve_month_day_iso(month, day, allowed, reference_date=reference_date)
        )
    for month_s, day_s in _DATE_CN_MD_RE.findall(text or ""):
        try:
            month, day = int(month_s), int(day_s)
        except ValueError:
            continue
        found.append(
            _resolve_month_day_iso(month, day, allowed, reference_date=reference_date)
        )
    return found


def _fact_card_date_surface_needles(
    text: str,
    iso_dates: Set[str],
    *,
    allowed: Set[str],
    reference_date: str = "",
) -> List[str]:
    """Blankable surface strings for ISO dates, including yearless EN/CN forms."""
    needles: List[str] = []
    for iso in iso_dates:
        needles.append(iso)
        needles.extend(_en_iso_surface_forms(iso))
        needles.extend(_cn_iso_surface_forms(iso))
        needles.extend(_date_surface_forms(text, iso))
    for mon, d, y in _DATE_EN_RE.findall(text or ""):
        if y:
            iso = _normalize_en_date(mon, d, y)
        else:
            month = _EN_MONTH_NUM.get((mon or "").strip(".").lower())
            if month is None:
                continue
            try:
                iso = _resolve_month_day_iso(
                    month, int(d), allowed, reference_date=reference_date
                )
            except ValueError:
                continue
        if not iso or iso not in iso_dates:
            continue
        needles.append(f"{mon} {d}")
        if y:
            needles.append(f"{mon} {d}, {y}")
            needles.append(f"{mon} {d} {y}")
    for y, m, d in _DATE_CN_RE.findall(text or ""):
        iso = _normalize_cn_date(y, m, d)
        if iso in iso_dates:
            needles.append(f"{y}年{int(m)}月{int(d)}日")
            needles.append(f"{y}年{m}月{d}日")
    for month_s, day_s in _DATE_CN_MD_RE.findall(text or ""):
        try:
            iso = _resolve_month_day_iso(
                int(month_s),
                int(day_s),
                allowed,
                reference_date=reference_date,
            )
        except ValueError:
            continue
        if iso in iso_dates:
            needles.append(f"{month_s}月{day_s}日")
            needles.append(f"{int(month_s)}月{int(day_s)}日")
    return needles


def _extract_decimal_tokens(text: str) -> List[str]:
    return _DECIMAL_RE.findall(text or "")


def _values_cited_in_text(text: str, value_set: Set[str]) -> List[str]:
    """子串匹配白名单数值（适配「日的4.05」等无空格中文语境）。"""
    cited: List[str] = []
    for v in sorted(value_set, key=len, reverse=True):
        if v and v in text:
            cited.append(v)
    return cited


def _in_dose_context(text: str, token: str) -> bool:
    for m in _DOSE_RE.finditer(text):
        if token in m.group(0):
            return True
    return False


def _looks_like_lab_citation(text: str, date_str: str) -> bool:
    idx = text.find(date_str)
    if idx < 0:
        for y, m, d in _DATE_CN_RE.findall(text):
            if _normalize_cn_date(y, m, d) == date_str:
                cn = f"{y}年{int(m)}月{int(d)}日"
                idx = text.find(cn)
                if idx < 0:
                    cn2 = f"{y}年{m}月{d}日"
                    idx = text.find(cn2)
                break
    if idx < 0:
        return False
    window = text[max(0, idx - 40) : idx + len(date_str) + 40]
    cues = LANG_T0_CLAIM_MAP["lab_citation_cues"]
    return any(c in window for c in cues)


def _disclosure_patterns() -> List[Dict[str, Any]]:
    global _DISCLOSURE_COMPILED
    if _DISCLOSURE_COMPILED is not None:
        return _DISCLOSURE_COMPILED
    compiled: List[Dict[str, Any]] = []
    flags = re.I | re.S
    for spec in LANG_DISCLOSURE_MAP:
        compiled.append(
            {
                "id": spec["id"],
                "block_open": re.compile(spec["block_open_re"], flags),
                "block_full": re.compile(spec["block_full_re"], flags),
                "source": re.compile(spec["source_re"], flags),
                "t0_forbidden": re.compile(spec["t0_forbidden_in_block_re"], flags),
                "verify": spec["verify_substrings"],
                "disclaimer": spec["disclaimer_substrings"],
            },
        )
    _DISCLOSURE_COMPILED = compiled
    return compiled


def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    sorted_iv = sorted(intervals)
    merged: List[Tuple[int, int]] = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def extract_disclosure_blocks(text: str) -> List[Tuple[int, int, str, str]]:
    """Return [(start, end, block_text, lang_id), ...] non-overlapping."""
    raw = text or ""
    found: List[Tuple[int, int, str, str]] = []
    for pat in _disclosure_patterns():
        for m in pat["block_full"].finditer(raw):
            found.append((m.start(), m.end(), m.group(0), pat["id"]))
        for m in pat["block_open"].finditer(raw):
            start = m.start()
            if any(start >= s and start < e for s, e, _, _ in found):
                continue
            end_line = raw.find("\n", start)
            if end_line < 0:
                end_line = len(raw)
            close_cn = raw.find("）", start, min(len(raw), start + 500))
            close_en = raw.find(")", start, min(len(raw), start + 500))
            end = end_line
            for close in (close_cn, close_en):
                if close >= start:
                    end = max(end, close + 1)
            segment = raw[start:end]
            if len(segment) >= 8:
                found.append((start, end, segment, pat["id"]))
    if not found:
        return []
    found.sort(key=lambda x: x[0])
    merged = _merge_intervals([(s, e) for s, e, _, _ in found])
    out: List[Tuple[int, int, str, str]] = []
    for ms, me in merged:
        block_text = raw[ms:me]
        lang_id = "zh"
        for pat in _disclosure_patterns():
            if pat["block_open"].search(block_text):
                lang_id = pat["id"]
                break
        out.append((ms, me, block_text, lang_id))
    return out


def mask_disclosure_blocks(text: str, blocks: Sequence[Tuple[int, int, str, str]]) -> str:
    if not blocks:
        return text or ""
    chars = list(text or "")
    for start, end, _, _ in blocks:
        for i in range(max(0, start), min(len(chars), end)):
            chars[i] = " "
    return "".join(chars)


def _disclosure_spec_for_lang(lang_id: str) -> Dict[str, Any]:
    for pat in _disclosure_patterns():
        if pat["id"] == lang_id:
            return pat
    return _disclosure_patterns()[0]


def audit_disclosure_block(
    block: str,
    lang_id: str,
    *,
    m4_mode: str,
) -> Tuple[List[str], List[str]]:
    violations: List[str] = []
    warnings: List[str] = []
    pat = _disclosure_spec_for_lang(lang_id)
    if pat["t0_forbidden"].search(block):
        violations.append("t0_forgery_in_t1_block")
        return violations, warnings
    has_open = bool(pat["block_open"].search(block))
    has_source = bool(pat["source"].search(block))
    has_verify = any(v in block for v in pat["verify"])
    has_m4 = any(d in block.lower() if lang_id == "en" else d in block for d in pat["disclaimer"])
    if not (has_open and has_source and has_verify):
        for token in set(_extract_decimal_tokens(block)):
            violations.append(f"t1_disclosure_incomplete:{token}")
        if not violations:
            violations.append("t1_disclosure_incomplete")
        return violations, warnings
    if not has_m4:
        if m4_mode == "strict":
            for token in set(_extract_decimal_tokens(block)):
                violations.append(f"t1_disclosure_incomplete:{token}")
        elif m4_mode == "warn":
            for token in set(_extract_decimal_tokens(block)):
                warnings.append(f"t1_missing_disclaimer:{token}")
    for token in set(_extract_decimal_tokens(block)):
        try:
            fv = float(token)
        except ValueError:
            continue
        if _LAB_RANGE_MIN <= fv <= _LAB_RANGE_MAX:
            warnings.append(f"t1_unverified_reference:{token}")
    return violations, warnings


def block_contains_t0_forgery(
    block: str,
    lang_id: str,
    manifest: NumericsManifest,
) -> bool:
    pat = _disclosure_spec_for_lang(lang_id)
    if pat["t0_forbidden"].search(block):
        return True
    for d in manifest.allowed_dates:
        if d in block:
            for token in _extract_decimal_tokens(block):
                if token not in manifest.allowed_values:
                    try:
                        fv = float(token)
                    except ValueError:
                        continue
                    if _LAB_RANGE_MIN <= fv <= _LAB_RANGE_MAX:
                        return True
    return False


def _token_in_t0_claim_context(text: str, token: str, *, window: int = 48) -> bool:
    if not text or not token:
        return False
    start = 0
    while True:
        idx = text.find(token, start)
        if idx < 0:
            return False
        win = text[max(0, idx - window) : idx + len(token) + window]
        win_lower = win.lower()
        owner = any(c in win for c in LANG_T0_CLAIM_MAP["owner_cues"]) or any(
            c in win_lower for c in LANG_T0_CLAIM_MAP["owner_cues"]
        )
        report = any(c in win for c in LANG_T0_CLAIM_MAP["report_cues"]) or any(
            c in win_lower for c in LANG_T0_CLAIM_MAP["report_cues"]
        )
        metric = any(c in win for c in LANG_T0_CLAIM_MAP["metric_cues"]) or any(
            c in win_lower for c in LANG_T0_CLAIM_MAP["metric_cues"]
        )
        if owner or report or metric:
            return True
        start = idx + 1


def numerics_audit_scope() -> str:
    raw = os.environ.get("PHA_NUMERICS_AUDIT_SCOPE", "t0_plus_disclosure").strip().lower()
    if raw in ("t0_strict", "strict", "legacy"):
        return "t0_strict"
    if raw in ("t0_plus_disclosure", "disclosure", "tier_v1"):
        return "t0_plus_disclosure"
    return "t0_plus_disclosure"


def numerics_t1_m4_mode() -> str:
    raw = os.environ.get("PHA_NUMERICS_T1_M4_MODE", "warn").strip().lower()
    if raw in ("strict", "warn", "off"):
        return raw
    return "warn"


def _audit_dates_and_citation(
    text: str,
    manifest: NumericsManifest,
    *,
    require_citation: bool,
) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
    """Shared date audit + citation extraction (strict & plus)."""
    violations: List[str] = []
    allowed_dates = manifest.allowed_dates
    allowed_values = manifest.allowed_values
    lipid_values = manifest.lipid_values
    normalized_dates = _extract_normalized_dates(text)

    cited_dates = sorted({d for d in normalized_dates if d in allowed_dates})
    cited_values = _values_cited_in_text(text, allowed_values)
    cited_lipid_values = _values_cited_in_text(text, lipid_values)

    forbidden = set(manifest.forbidden_dates)
    for d in normalized_dates:
        if d in forbidden:
            violations.append(f"forbidden_date:{d}")
    for d in forbidden:
        if d in text:
            violations.append(f"forbidden_date:{d}")

    ref = manifest.reference_date
    if ref:
        try:
            ref_d = date.fromisoformat(ref[:10])
            for d in set(normalized_dates):
                try:
                    dd = date.fromisoformat(d)
                except ValueError:
                    continue
                if dd > ref_d and d not in allowed_dates:
                    violations.append(f"future_date:{d}")
        except ValueError:
            pass

    for d in set(normalized_dates):
        if d in allowed_dates or d in forbidden:
            continue
        if _looks_like_lab_citation(text, d):
            violations.append(f"unauthorized_date:{d}")

    if require_citation and manifest.profile == "combined_review":
        if not cited_dates and not cited_lipid_values:
            violations.append("missing_ground_truth_citation")

    return violations, cited_dates, cited_values, cited_lipid_values, sorted(allowed_dates)


_ISO_DATE_CHUNK_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_WEARABLE_COUNT_RE = re.compile(r"(?<![\d.])(\d{3,6})(?![\d.])")


def _extract_wearable_count_tokens(text: str) -> List[str]:
    """Standalone integers (steps/kcal scale). Skip ISO dates and calendar years."""
    masked = _ISO_DATE_CHUNK_RE.sub(" ", text or "")
    out: List[str] = []
    seen: Set[str] = set()
    for match in _WEARABLE_COUNT_RE.finditer(masked):
        raw = match.group(1)
        try:
            n = int(raw)
        except ValueError:
            continue
        if 1900 <= n <= 2100:
            continue
        if n < 100:
            continue
        if raw in seen:
            continue
        seen.add(raw)
        out.append(raw)
    return out


def _audit_wearable_grain_counts(text: str, manifest: NumericsManifest) -> List[str]:
    """Non-default time grain: cited step-scale integers must be on this window's T0."""
    if (manifest.wearable_grain_source or "default") == "default":
        return []
    allowed = manifest.allowed_values
    violations: List[str] = []
    for token in _extract_wearable_count_tokens(text):
        if token in allowed:
            continue
        if _in_dose_context(text, token):
            continue
        violations.append(f"unauthorized_wearable_count:{token}")
    return violations


def wearable_grain_fence_blocked(audit: Dict[str, Any]) -> bool:
    return any(
        str(v).startswith("unauthorized_wearable_count:")
        for v in (audit or {}).get("violations") or []
    )


def format_wearable_grain_refusal(
    manifest: NumericsManifest,
    *,
    locale: str | None = None,
) -> str:
    start = (manifest.wearable_window_start or "").strip()
    end = (manifest.wearable_window_end or "").strip()
    span = start if start and start == end else (f"{start}~{end}" if start and end else "该时间窗口")
    loc = (locale or "").strip().lower()
    if loc.startswith("en"):
        return (
            f"No verified wearable values in your records for {span}. "
            "This is not filled from another date."
        )
    return f"库内没有 {span} 的可核验穿戴记录，不会用其他日期的数字代替。"


_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\d[A-Za-z0-9_]*|\d+[A-Za-z_][A-Za-z0-9_]*")
_CLAUSE_SPLIT_RE = re.compile(r"[。！？；，.!?;,\n]+")
_WINDOW_PHRASE_RE = re.compile(
    r"(?:近|过去|最近|last|near)\s*(\d+)\s*(?:天|日|夜|个月|月|days?|nights?|months?)",
    re.I,
)
# Numbers with optional thousands separators and 1-2 decimal places; not part of identifiers after mask
_FACT_NUM_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?![\d.])")


def _mask_identifiers(text: str) -> str:
    return _IDENTIFIER_RE.sub(lambda m: " " * len(m.group(0)), text or "")


def leftover_s_level_numeric_tokens(text: str) -> list[str]:
    """Numbers that remain after identifier/date masking (brief post-check).

    Does not change the ``fact_card`` audit policy. Hyphenated identifiers
    such as Omega-3 and letter-leading identifiers (D3, SpO2) are masked.
    Digit-leading tokens like ``400mg`` are leftover doses, not identifiers.
    """
    working = text or ""
    working = re.sub(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b", lambda m: " " * len(m.group(0)), working)
    working = re.sub(
        r"[A-Za-z_][A-Za-z0-9_]*\d[A-Za-z0-9_]*",
        lambda m: " " * len(m.group(0)),
        working,
    )
    working = _DATE_ISO_RE.sub(" ", working)
    working = _DATE_CN_RE.sub(" ", working)
    working = _DATE_EN_RE.sub(" ", working)
    working = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", working)
    out: list[str] = []
    for m in _FACT_NUM_RE.finditer(working):
        token = f"{m.group(1)}.{m.group(2)}" if m.group(2) is not None else m.group(1)
        out.append(token)
    return out


def _normalize_num_token(token: str) -> Set[str]:
    raw = (token or "").translate(_FULLWIDTH_DIGITS).replace(",", "").strip()
    if not raw:
        return set()
    out: Set[str] = {raw}
    if "." in raw:
        try:
            fv = float(raw)
        except ValueError:
            return out
        if abs(fv - round(fv)) < 1e-9:
            out.add(str(int(round(fv))))
    return out


def _token_in_allowed(token: str, allowed: Set[str]) -> bool:
    if not token or not allowed:
        return False
    norms = _normalize_num_token(token)
    if norms & allowed:
        return True
    # also accept if an allowed variant normalizes into the token set
    for a in allowed:
        if _normalize_num_token(a) & norms:
            return True
    return False


def _is_nonzero_fraction_decimal(token: str) -> bool:
    raw = (token or "").translate(_FULLWIDTH_DIGITS).replace(",", "").strip()
    if "." not in raw:
        return False
    frac = raw.split(".", 1)[1]
    return bool(frac) and any(ch != "0" for ch in frac)


def _clause_has_cues(clause: str, cues: Sequence[str]) -> bool:
    cl = clause or ""
    if not cl or not cues:
        return False
    cl_lower = cl.lower()
    for cue in cues:
        if not cue:
            continue
        if cue.isascii():
            if cue.lower() in cl_lower:
                return True
        elif cue in cl:
            return True
    return False


def _personal_clause(clause: str) -> bool:
    return (
        _clause_has_cues(clause, LANG_T0_CLAIM_MAP["owner_cues"])
        or _clause_has_cues(clause, LANG_T0_CLAIM_MAP["temporal_cues"])
        or _clause_has_cues(clause, LANG_T0_CLAIM_MAP["measurement_cues"])
    )


def _educational_clause(clause: str) -> bool:
    return _clause_has_cues(clause, LANG_T0_CLAIM_MAP["educational_cues"])


def _metric_clause(clause: str, labels: Set[str], units: Set[str]) -> bool:
    cl = clause or ""
    for lab in labels:
        if len(lab) >= 2 and lab in cl:
            return True
    for unit in units:
        if len(unit) >= 1 and unit in cl:
            return True
    return False


def _complete_disclosure_blocks(
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """T1 blocks with open + source + verify. Incomplete opens stay for E-level."""
    out: List[Tuple[int, int, str, str]] = []
    for start, end, block_text, lang_id in extract_disclosure_blocks(text):
        pat = _disclosure_spec_for_lang(lang_id)
        has_open = bool(pat["block_open"].search(block_text))
        has_source = bool(pat["source"].search(block_text))
        has_verify = any(v in block_text for v in pat["verify"])
        if has_open and has_source and has_verify:
            out.append((start, end, block_text, lang_id))
    return out


def _blank_spans(text: str, spans: Sequence[Tuple[int, int]]) -> str:
    if not spans:
        return text or ""
    chars = list(text or "")
    for start, end in spans:
        for i in range(max(0, start), min(len(chars), end)):
            chars[i] = " "
    return "".join(chars)


def _blank_substrings(text: str, needles: Sequence[str]) -> str:
    raw = text or ""
    if not needles:
        return raw
    for needle in sorted({n for n in needles if n}, key=len, reverse=True):
        if needle not in raw:
            continue
        raw = raw.replace(needle, " " * len(needle))
    return raw


def _date_surface_forms(text: str, iso: str) -> List[str]:
    """Surface strings in text that normalize to the given ISO date."""
    forms: List[str] = [iso]
    for y, m, d in _DATE_CN_RE.findall(text or ""):
        if _normalize_cn_date(y, m, d) == iso:
            forms.append(f"{y}年{int(m)}月{int(d)}日")
            forms.append(f"{y}年{m}月{d}日")
            forms.append(f"{y}年 {int(m)}月 {int(d)}日")
    for mon, d, y in _DATE_EN_RE.findall(text or ""):
        if _normalize_en_date(mon, d, y) == iso:
            forms.append(f"{mon} {d}")
            if y:
                forms.append(f"{mon} {d}, {y}")
                forms.append(f"{mon} {d} {y}")
    return forms


def _split_clauses(text: str) -> List[Tuple[int, int, str]]:
    raw = text or ""
    clauses: List[Tuple[int, int, str]] = []
    last = 0
    for m in _CLAUSE_SPLIT_RE.finditer(raw):
        if m.start() > last:
            clauses.append((last, m.start(), raw[last : m.start()]))
        last = m.end()
    if last < len(raw):
        clauses.append((last, len(raw), raw[last:]))
    return clauses


def _clause_for_pos(clauses: Sequence[Tuple[int, int, str]], pos: int) -> str:
    for start, end, body in clauses:
        if start <= pos < end:
            return body
    return ""


def _audit_response_numerics_fact_card(
    answer_text: str,
    manifest: NumericsManifest,
    *,
    require_citation: bool = False,
) -> Dict[str, Any]:
    """Fact-card policy: whitelist personal/decimal numbers; educational ints via clause cues."""
    del require_citation  # fact_card path does not require citation
    text = answer_text or ""
    violations: List[str] = []
    warnings: List[str] = []
    educational_ints: Set[str] = set()
    cited_values: List[str] = []
    allowed_values = manifest.allowed_values
    allowed_dates = manifest.allowed_dates
    labels = set(manifest.card_labels)
    units = set(manifest.card_units)
    window_ok = set(manifest.window_day_tokens) | set(allowed_values)
    value_ok = set(allowed_values) | set(manifest.window_day_tokens)
    m4_mode = numerics_t1_m4_mode()

    complete_blocks = _complete_disclosure_blocks(text)
    for _, _, block_text, lang_id in complete_blocks:
        if block_contains_t0_forgery(block_text, lang_id, manifest):
            violations.append("t0_forgery_in_t1_block")
        b_v, b_w = audit_disclosure_block(block_text, lang_id, m4_mode=m4_mode)
        violations.extend(b_v)
        warnings.extend(b_w)

    working = mask_disclosure_blocks(text, complete_blocks)

    normalized_dates = _extract_fact_card_dates(
        working,
        allowed_dates,
        reference_date=manifest.reference_date or "",
    )
    cited_dates = sorted({d for d in normalized_dates if d in allowed_dates})
    forbidden = set(manifest.forbidden_dates)
    for d in set(normalized_dates):
        if d in forbidden:
            violations.append(f"forbidden_date:{d}")
    for d in forbidden:
        if d in working:
            violations.append(f"forbidden_date:{d}")

    ref = manifest.reference_date
    if ref:
        try:
            ref_d = date.fromisoformat(ref[:10])
            for d in set(normalized_dates):
                try:
                    dd = date.fromisoformat(d)
                except ValueError:
                    continue
                if dd > ref_d and d not in allowed_dates:
                    violations.append(f"future_date:{d}")
        except ValueError:
            pass

    for d in set(normalized_dates):
        if d in allowed_dates or d in forbidden:
            continue
        violations.append(f"unauthorized_date:{d}")

    # Blank every recognized date surface (allowed or not) so year/month/day
    # fragments — including yearless "September 3" — are not re-scanned as ints.
    date_blank_needles = _fact_card_date_surface_needles(
        working,
        set(normalized_dates),
        allowed=allowed_dates,
        reference_date=manifest.reference_date or "",
    )
    working = _blank_substrings(working, date_blank_needles)
    working = _blank_substrings(working, sorted(manifest.card_times))

    window_spans: List[Tuple[int, int]] = []
    for m in _WINDOW_PHRASE_RE.finditer(working):
        num = m.group(1)
        if not _token_in_allowed(num, window_ok):
            violations.append(f"unauthorized_window:{num}")
        # blank the matched number only (keep cue words for clause classification)
        window_spans.append((m.start(1), m.end(1)))
    working = _blank_spans(working, window_spans)

    working = _mask_identifiers(working)
    clauses = _split_clauses(working)

    for m in _FACT_NUM_RE.finditer(working):
        whole = m.group(0)
        token = whole
        if m.group(2) is not None:
            token = f"{m.group(1)}.{m.group(2)}"
        else:
            token = m.group(1)
        clause = _clause_for_pos(clauses, m.start())
        if _token_in_allowed(token, value_ok):
            hit = _normalize_num_token(token) & value_ok
            cited_values.extend(hit if hit else [token])
            continue
        if _is_nonzero_fraction_decimal(token):
            violations.append(f"unauthorized_value:{token}")
            continue
        if _personal_clause(clause):
            violations.append(f"unauthorized_value:{token}")
            continue
        if _educational_clause(clause):
            educational_ints.update(_normalize_num_token(token) or {token})
            continue
        if _metric_clause(clause, labels, units):
            violations.append(f"unauthorized_value:{token}")
            continue
        educational_ints.update(_normalize_num_token(token) or {token})

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": sorted(set(violations)),
        "warnings": sorted(set(warnings)),
        "cited_dates": cited_dates,
        "cited_values": sorted(set(cited_values)),
        "cited_lipid_values": [],
        "manifest_entry_count": len(manifest.entries),
        "allowed_dates": sorted(allowed_dates),
        "audit_scope": "fact_card",
        "educational_ints": sorted(educational_ints),
        "disclosure_block_count": len(complete_blocks),
        "policy_rev": FACT_CARD_AUDIT_POLICY_REV,
    }


def _audit_response_numerics_strict(
    answer_text: str,
    manifest: NumericsManifest,
    *,
    require_citation: bool = False,
) -> Dict[str, Any]:
    """Legacy C-layer audit — unchanged behavior for t0_strict."""
    text = answer_text or ""
    warnings: List[str] = []
    allowed_values = manifest.allowed_values

    violations, cited_dates, cited_values, cited_lipid_values, allowed_dates = _audit_dates_and_citation(
        text,
        manifest,
        require_citation=require_citation,
    )
    violations.extend(_audit_wearable_grain_counts(text, manifest))

    for token in set(_extract_decimal_tokens(text)):
        if token in allowed_values:
            continue
        if _in_dose_context(text, token):
            continue
        try:
            fv = float(token)
        except ValueError:
            continue
        if _LAB_RANGE_MIN <= fv <= _LAB_RANGE_MAX:
            violations.append(f"unauthorized_value:{token}")

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": sorted(set(violations)),
        "warnings": sorted(set(warnings)),
        "cited_dates": cited_dates,
        "cited_values": sorted(set(cited_values)),
        "cited_lipid_values": sorted(set(cited_lipid_values)),
        "manifest_entry_count": len(manifest.entries),
        "allowed_dates": allowed_dates,
        "audit_scope": "t0_strict",
    }


def _audit_response_numerics_t0_plus_disclosure(
    answer_text: str,
    manifest: NumericsManifest,
    *,
    require_citation: bool = False,
) -> Dict[str, Any]:
    """T0 strict on masked text; T1 format-only inside disclosure blocks."""
    text = answer_text or ""
    violations: List[str] = []
    warnings: List[str] = []
    allowed_values = manifest.allowed_values
    m4_mode = numerics_t1_m4_mode()

    blocks = extract_disclosure_blocks(text)
    masked = mask_disclosure_blocks(text, blocks)

    violations, cited_dates, cited_values, cited_lipid_values, allowed_dates = _audit_dates_and_citation(
        masked,
        manifest,
        require_citation=require_citation,
    )
    violations.extend(_audit_wearable_grain_counts(masked, manifest))

    # T1 block audit (format + t0 forgery in shell)
    for _, _, block_text, lang_id in blocks:
        if block_contains_t0_forgery(block_text, lang_id, manifest):
            violations.append("t0_forgery_in_t1_block")
        b_v, b_w = audit_disclosure_block(block_text, lang_id, m4_mode=m4_mode)
        violations.extend(b_v)
        warnings.extend(b_w)

    # T0 priority: decimals outside disclosure blocks — strict on masked text
    for token in set(_extract_decimal_tokens(masked)):
        if token in allowed_values:
            continue
        if _in_dose_context(masked, token):
            continue
        try:
            fv = float(token)
        except ValueError:
            continue
        if _LAB_RANGE_MIN <= fv <= _LAB_RANGE_MAX:
            violations.append(f"unauthorized_value:{token}")

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": sorted(set(violations)),
        "warnings": sorted(set(warnings)),
        "cited_dates": cited_dates,
        "cited_values": sorted(set(cited_values)),
        "cited_lipid_values": sorted(set(cited_lipid_values)),
        "manifest_entry_count": len(manifest.entries),
        "allowed_dates": allowed_dates,
        "audit_scope": "t0_plus_disclosure",
        "disclosure_block_count": len(blocks),
    }


def audit_response_numerics(
    answer_text: str,
    manifest: NumericsManifest,
    *,
    require_citation: bool = False,
) -> Dict[str, Any]:
    """C-layer post-check: response numerics/dates must stay within manifest."""
    if manifest.profile == "fact_card_interpret":
        return _audit_response_numerics_fact_card(
            answer_text,
            manifest,
            require_citation=require_citation,
        )
    if numerics_audit_scope() == "t0_plus_disclosure":
        return _audit_response_numerics_t0_plus_disclosure(
            answer_text,
            manifest,
            require_citation=require_citation,
        )
    return _audit_response_numerics_strict(
        answer_text,
        manifest,
        require_citation=require_citation,
    )


def numerics_audit_mode() -> str:
    return os.environ.get("PHA_NUMERICS_AUDIT", "warn").strip().lower()


def numerics_require_citation() -> bool:
    return os.environ.get("PHA_NUMERICS_REQUIRE_CITATION", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def apply_numerics_audit_to_answer(
    answer_text: str,
    audit: Dict[str, Any],
) -> str:
    """When block mode is on, replace answer with audit failure notice."""
    if audit.get("passed"):
        return answer_text
    vlist = ", ".join(audit.get("violations") or [])
    scope = audit.get("audit_scope") or numerics_audit_scope()
    t1_hint = ""
    if scope == "t0_plus_disclosure":
        t1_hint = (
            "\n· T1 参考标准: 【参考标准】…（来源：…，请自行查证，非医疗建议） or "
            "[Reference Standard] … (source: …, verify by yourself, not medical advice)."
        )
    return (
        "【PHA 数字合规审计未通过，本轮答复已拦截】\n"
        f"违规项：{vlist or 'unknown'}\n"
        "请仅引用 Numerics Manifest 白名单中的报告日/数值（T0）；"
        "若库内无该指标，应明确写「库内无该指标」。"
        f"{t1_hint}"
    )


__all__ = [
    "FACT_CARD_AUDIT_POLICY_REV",
    "LANG_DISCLOSURE_MAP",
    "LANG_T0_CLAIM_MAP",
    "ManifestEntry",
    "NumericsManifest",
    "apply_numerics_audit_to_answer",
    "audit_disclosure_block",
    "audit_response_numerics",
    "build_fact_card_numerics_manifest",
    "build_numerics_manifest",
    "extract_disclosure_blocks",
    "format_wearable_grain_refusal",
    "leftover_s_level_numeric_tokens",
    "wearable_grain_fence_blocked",
    "mask_disclosure_blocks",
    "numerics_audit_mode",
    "numerics_audit_scope",
    "numerics_require_citation",
    "numerics_t1_m4_mode",
]
