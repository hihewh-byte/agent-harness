"""Semi-automatic column mapping hints for unrecognized broker statements."""

from __future__ import annotations

import re
from typing import Any

# Canonical field -> header keyword patterns (EN + ZH)
_FIELD_PATTERNS: dict[str, list[str]] = {
    "tradeDate": [
        "date",
        "settlement date",
        "trade date",
        "成交时间",
        "日期",
        "run date",
        "date/time",
    ],
    "eventType": ["action", "type", "transaction type", "transaction type", "类型"],
    "symbol": ["symbol", "代码", "ticker", "investment name", "description"],
    "grossAmount": [
        "amount",
        "proceeds",
        "成交金额",
        "gain/loss",
        "realized p/l",
        "gainloss",
    ],
    "withholdingTax": ["tax", "withholding", "nra tax", "预扣税", "foreign tax"],
    "fee": ["fee", "commission", "comm", "佣金", "fees & comm"],
}


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip()).lower()


def suggest_column_mapping(headers: list[str]) -> dict[str, Any]:
    """Map detected headers to canonical TaxEvent fields with confidence."""
    normalized = {_norm(h): h for h in headers if h}
    suggestions: dict[str, dict[str, Any]] = {}
    unmatched = list(headers)

    for field, patterns in _FIELD_PATTERNS.items():
        best_header = None
        best_score = 0.0
        for pat in patterns:
            pat_n = _norm(pat)
            for nh, orig in normalized.items():
                score = 0.0
                if nh == pat_n:
                    score = 1.0
                elif pat_n in nh or nh in pat_n:
                    score = 0.75
                if score > best_score:
                    best_score = score
                    best_header = orig
        if best_header and best_score >= 0.75:
            suggestions[field] = {
                "header": best_header,
                "confidence": round(best_score, 2),
            }
            if best_header in unmatched:
                unmatched.remove(best_header)

    guessed_template = _guess_template(suggestions, normalized)
    return {
        "suggestedMapping": suggestions,
        "unmatchedHeaders": unmatched,
        "guessedTemplateId": guessed_template,
        "nextSteps": _next_steps(suggestions, guessed_template),
    }


def _guess_template(
    suggestions: dict[str, dict[str, Any]],
    normalized: dict[str, str],
) -> str | None:
    hset = set(normalized.keys())
    if "成交时间" in hset and "成交金额" in hset:
        return "broker_tiger_v1"
    if "settlement date" in hset and "transaction type" in hset:
        return "broker_vanguard_v1"
    if "date" in hset and "type" in hset and "action" not in hset:
        return "broker_futu_v1"
    if "date/time" in hset or ("proceeds" in hset and "symbol" in hset):
        return "broker_ibkr_v1"
    if "run date" in hset and "action" in hset:
        return "broker_fidelity_v1"
    if "date" in hset and "action" in hset:
        return "broker_schwab_v1"
    if suggestions.get("tradeDate") and suggestions.get("grossAmount"):
        return None
    return None


def _next_steps(suggestions: dict[str, dict[str, Any]], guessed: str | None) -> list[str]:
    steps: list[str] = []
    if guessed:
        steps.append(
            f"侧栏「券商模板」选择 {guessed} 后重新上传，或确认下列列映射是否正确。"
        )
    else:
        steps.append("未能自动识别券商，请对照下列建议映射核对表头。")
    required = ("tradeDate", "grossAmount")
    missing = [f for f in required if f not in suggestions]
    if missing:
        steps.append(f"缺少关键列映射：{', '.join(missing)}，请在对话中说明对应列名。")
    steps.append("映射确认前系统不会输出最终税额（风险等级：中/高）。")
    return steps
