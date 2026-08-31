from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatTurnResult:
    reply: str
    action: str  # none | need_upload | compute | show_report
    compute_params: dict[str, Any] | None = None
    fact_bundle: Any | None = None
    follow_ups: list[str] | None = None


_INTENT_COMPUTE = re.compile(
    r"(算|计算|测算|应纳税|补税|交多少税|税额|estimate|compute|tax due)",
    re.I,
)
_INTENT_CHECKLIST = re.compile(r"(材料|清单|申报|checklist|filing)", re.I)
_INTENT_REPORT = re.compile(r"(报告|结果|明细|report)", re.I)


def _normalize_year_token(token: str) -> int:
    t = str(token).strip()
    if len(t) == 4 and t.isdigit():
        return int(t)
    yy = int(t)
    return 2000 + yy if yy < 70 else 1900 + yy


def infer_tax_years(text: str, default: int = 2022) -> list[int]:
    """One or more 所得所属纳税年度 from message (range, enumeration, or single year)."""
    msg = (text or "").strip()
    m_range = re.search(r"(\d{2,4})\s*年?\s*(?:到|至|—|-)\s*(\d{2,4})\s*年?", msg)
    if m_range:
        y1 = _normalize_year_token(m_range.group(1))
        y2 = _normalize_year_token(m_range.group(2))
        lo, hi = min(y1, y2), max(y1, y2)
        return list(range(lo, hi + 1))

    years: list[int] = []
    for m in re.finditer(r"(20\d{2})\s*年?", msg):
        years.append(int(m.group(1)))
    for m in re.finditer(r"(?<!\d)(\d{2})\s*年", msg):
        years.append(_normalize_year_token(m.group(1)))
    if years:
        return sorted(set(years))
    return [default]


def infer_tax_year(text: str, default: int = 2022) -> int:
    return infer_tax_years(text, default)[0]


def orchestrate_user_message(
    message: str,
    *,
    dataset_id: str | None,
    last_run_id: str | None,
    default_tax_year: int = 2022,
    broker_template_id: str | None = None,
    mapping_hints: dict[str, Any] | None = None,
    filing_scope: str = "foreign_only",
    domestic_income_provided: bool = False,
) -> ChatTurnResult:
    msg = (message or "").strip()
    if not msg:
        return ChatTurnResult(
            reply="请上传富途 Annual_Statement 税表 xlsx，并说明纳税年度（如「测算 2022 年应补税额」）。",
            action="none",
        )

    if not dataset_id:
        if _INTENT_COMPUTE.search(msg):
            return ChatTurnResult(
                reply=(
                    "请先上传富途税表 xlsx（App「我的税表」→ Annual_Statement）。\n"
                    "跨年卖出需同会话上传买入年至卖出年全部税表。"
                ),
                action="need_upload",
            )
        return ChatTurnResult(
            reply=(
                "你好，我是富途境外所得报税助手（中国税务居民）。\n"
                "请上传 Annual_Statement xlsx，然后说「测算 2022 年应补多少税」。"
            ),
            action="need_upload",
        )

    if _INTENT_REPORT.search(msg) and last_run_id:
        return ChatTurnResult(
            reply="正在加载上一份测算报告。",
            action="show_report",
            compute_params={"runId": last_run_id},
        )

    if _INTENT_CHECKLIST.search(msg):
        return ChatTurnResult(
            reply=(
                "申报材料通常包括：个人所得税自行纳税申报表（B 表及附表）、"
                "富途年度税表、境外已纳税额凭证。测算完成后可查看完整报告。"
            ),
            action="none",
        )

    if _INTENT_COMPUTE.search(msg) or re.search(r"^(好|开始|确认|请算|测试)", msg):
        year = infer_tax_year(msg, default_tax_year)
        return ChatTurnResult(
            reply=f"好的，将按 **{year}** 年度、中国税务居民口径测算富途境外所得。",
            action="compute",
            compute_params={
                "taxYear": year,
                "residentStatus": "cn_tax_resident",
                "filingScope": "foreign_only",
                "fxPolicy": "cn_supplemental",
            },
        )

    if last_run_id and re.search(r"(结果|对不对|准确|多少税|纳税)", msg):
        return ChatTurnResult(
            reply="请查看上方测算卡片中的「预计应补税额」。如需其他年度请说明年份。",
            action="none",
        )

    return ChatTurnResult(
        reply="已收到。你可以说「测算 2023 年税额」或「给我申报材料清单」。",
        action="none",
    )
