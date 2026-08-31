"""Ollama-compatible tool definitions for Tax Agent chat orchestration."""

from __future__ import annotations

from typing import Any

TAX_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "compute_tax",
            "description": (
                "对已上传的富途 Annual_Statement 税表执行境外所得个税测算。"
                "无 dataset 时不要调用；已有 lastSummary 且用户仅询问结果时不要重复调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "纳税年度，如 2024",
                    },
                    "resident_status": {
                        "type": "string",
                        "enum": ["cn_tax_resident", "uncertain", "non_resident"],
                        "description": "居民身份",
                    },
                    "filing_scope": {
                        "type": "string",
                        "enum": ["foreign_only", "includes_domestic"],
                        "description": (
                            "申报范围：仅境外所得，或含境内综合所得合并汇算。"
                            "含境内时用户须在侧栏填写 domesticIncome，否则仅算境外。"
                        ),
                    },
                },
                "required": ["tax_year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_upload",
            "description": (
                "引导用户上传富途 Annual_Statement xlsx；仅当尚未上传或需补充更早年度税表时调用。"
                "已上传且可测算时不要调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "broker_hint": {
                        "type": "string",
                        "description": "固定 futu",
                    },
                    "reply": {
                        "type": "string",
                        "description": "给用户的简短中文说明",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_report",
            "description": "展示最近一次测算报告摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "可选 runId；缺省用会话最近一次",
                    },
                    "reply": {"type": "string", "description": "给用户的简短说明"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tax_insight",
            "description": (
                "获取报税数据洞察 JSON（期末持仓、未实现盈亏、已实现对照、敏感性辅助）。"
                "用户问年末估值、未卖出亏损、盈利偏高等时调用；数字由后端生成，勿编造。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "纳税年度，如 2023",
                    },
                    "focus": {
                        "type": "string",
                        "enum": [
                            "holdings_year_end",
                            "realized_vs_deferred",
                            "explain_summary",
                        ],
                        "description": "洞察类型",
                    },
                },
                "required": ["tax_year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_coverage",
            "description": (
                "检查已上传富途税表年度是否覆盖跨年 FIFO 所需区间；"
                "用户问缺哪年、材料是否齐全时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "关注年度（可选）",
                    },
                    "reply": {"type": "string", "description": "给用户的简短说明"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_filing_table",
            "description": (
                "获取申报数据表四列（总收入/资产原值/合理费用/净损益）权威 JSON。"
                "用户问怎么填表、四列数字时调用；勿编造金额。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "可选，仅展示该年",
                    },
                    "reply": {"type": "string", "description": "给用户的简短说明"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_filing_narrative",
            "description": (
                "生成指定年度的境外财产转让申报说明（中文叙述）。"
                "数字仅来自申报数据表四列；用户要求写说明信/润色申报叙述时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tax_year": {
                        "type": "integer",
                        "description": "纳税年度，如 2023",
                    },
                    "reply": {"type": "string", "description": "给用户的简短引导"},
                },
                "required": ["tax_year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_brief",
            "description": "列出当前数据集触发的风险规则 R001–R008 与 ambiguous 提示。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reply": {"type": "string", "description": "给用户的简短说明"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_only",
            "description": "仅文字回复（答疑、清单说明、澄清），不触发测算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reply": {"type": "string", "description": "中文回复正文"},
                    "follow_up_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选追问",
                    },
                },
                "required": ["reply"],
            },
        },
    },
]

TOOL_SYSTEM_APPENDIX = """
调用工具规则：
- 用户要求测算税额且 hasDataset → compute_tax
- 完全未上传 → request_upload（仅富途 Annual_Statement xlsx，跨年需多年度）
- 已上传且有 lastSummary，用户问结果/解读 → reply_only（勿 request_upload）
- 用户问年末持仓/估值/未实现盈亏/盈利偏高等 → get_tax_insight 或 reply_only（须引用 TAX_INSIGHT）
- 查看报告 → show_report
- 材料/缺年/覆盖 → check_coverage
- 填表四列 → get_filing_table
- 风险/ambiguous → get_risk_brief
- 申报说明/叙述润色 → compose_filing_narrative
- 其他答疑 → reply_only
勿编造税额；T0=申报口径，T1=辅助对照；勿提 Schwab/Fidelity/CSV。
"""


def model_supports_ollama_tools(model: str) -> bool:
    """DeepSeek-R1 等对 Ollama tools schema 常返回 HTTP 400。"""
    m = (model or "").lower()
    if "deepseek-r1" in m or ("deepseek" in m and "r1" in m):
        return False
    return True
