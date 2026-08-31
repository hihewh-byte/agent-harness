from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from tax_agent.pha_llm import import_llm_utils, ollama_base_url


# 16GB Mac Air 默认优先级：先 7B 轻量，再 DeepSeek-R1 14B
TAX_MODEL_PRIORITY_LOW_RAM: tuple[str, ...] = (
    "qwen2.5:7b-instruct",
    "qwen2.5:7b",
    "deepseek-r1:14b",
    "deepseek-r1:8b",
    "qwen2.5:14b-instruct",
    "qwen2.5:14b",
)

TAX_MODEL_PRIORITY_DEFAULT: tuple[str, ...] = (
    "qwen2.5:14b-instruct",
    "qwen2.5:14b",
    "qwen2.5:7b-instruct",
    "qwen2.5:7b",
    "deepseek-r1:14b",
    "deepseek-r1:8b",
)

# 勿用于报税编排（仍可安装在机器上供 PHA 使用）
TAX_MODEL_BLOCKLIST_SUBSTR: tuple[str, ...] = (
    "vision",
    "llava",
    "multimodal",
    "gemma4:26b",
)


@dataclass(frozen=True)
class TaxModelResolution:
    model: str | None
    reason: str
    installed: list[str]
    recommended: str = "qwen2.5:7b-instruct"


def _match_installed(requested: str, installed: list[str]) -> str | None:
    req = requested.strip()
    if req in installed:
        return req
    low = req.lower()
    for name in installed:
        if name.lower() == low:
            return name
    for name in installed:
        if low in name.lower() or name.lower().startswith(low.split(":")[0]):
            return name
    return None


def _low_ram_mode() -> bool:
    v = (os.environ.get("TAX_AGENT_LOW_RAM") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _priority_list() -> tuple[str, ...]:
    return TAX_MODEL_PRIORITY_LOW_RAM if _low_ram_mode() else TAX_MODEL_PRIORITY_DEFAULT


def _is_blocked(name: str) -> bool:
    n = name.lower()
    return any(b in n for b in TAX_MODEL_BLOCKLIST_SUBSTR)


def _score_tax_fit(name: str) -> int:
    n = name.lower()
    if _is_blocked(n):
        return -100
    score = 0
    if "qwen2.5" in n:
        score += 50
    if "qwen" in n:
        score += 40
    if "deepseek-r1" in n:
        score += 45
    if "deepseek" in n:
        score += 35
    if "llama3.1" in n:
        score += 25
    if "instruct" in n:
        score += 5
    m = re.search(r"(\d+)\s*b", n)
    if m:
        score += min(int(m.group(1)), 32)
    return score


def resolve_tax_agent_model(
    *,
    override: str | None = None,
    timeout_seconds: float = 5.0,
) -> TaxModelResolution:
    utils = import_llm_utils()
    base = ollama_base_url()
    try:
        installed = utils["list_ollama_installed_models"](base, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return TaxModelResolution(model=None, reason=f"ollama_unreachable:{exc}", installed=[])

    explicit = (
        (override or "").strip()
        or (os.environ.get("TAX_AGENT_MODEL") or "").strip()
        or (os.environ.get("OLLAMA_MODEL") or "").strip()
    )
    if explicit and explicit.lower() not in {"auto", "__auto__", "smart"}:
        matched = _match_installed(explicit, installed)
        if matched:
            return TaxModelResolution(model=matched, reason="explicit_override", installed=installed)
        return TaxModelResolution(
            model=None,
            reason=f"override_not_installed:{explicit}",
            installed=installed,
        )

    for candidate in _priority_list():
        matched = _match_installed(candidate, installed)
        if matched:
            return TaxModelResolution(model=matched, reason=f"priority:{candidate}", installed=installed)

    entries = utils["list_ollama_model_entries"](base, timeout_seconds=timeout_seconds)
    text_entries = utils["list_text_llm_models"](entries)
    if not text_entries:
        return TaxModelResolution(model=None, reason="no_text_models", installed=installed)

    candidates = [e for e in text_entries if not _is_blocked(e.name)]
    if not candidates:
        return TaxModelResolution(model=None, reason="only_blocked_models", installed=installed)
    best = max(candidates, key=lambda e: (_score_tax_fit(e.name), -e.size))
    return TaxModelResolution(model=best.name, reason="scored_best_fit", installed=installed)


def recommended_model_doc_zh() -> str:
    return (
        "16GB Mac 默认：**qwen2.5:7b-instruct**（快、省内存）。\n"
        "复杂推演可设 TAX_AGENT_MODEL=**deepseek-r1:14b**（更慢）。\n"
        "报税勿用：vision / **gemma4:26b**（占满内存）。\n"
        "Excel 解析与算税不占用 LLM；汇率/洞察类问题走规则快车道，不调用模型。"
    )


def list_tax_model_choices(installed: list[str] | None = None) -> list[dict[str, str]]:
    """UI model picker options (installed Ollama text models + auto/off)."""
    if installed is None:
        installed = resolve_tax_agent_model().installed
    priority = _priority_list()
    choices: list[dict[str, str]] = [
        {"id": "auto", "label": "自动选择（推荐）", "hint": "按内存与已安装模型自动解析"},
        {"id": "__off__", "label": "关闭 LLM（仅规则/快车道）", "hint": "不算税编排，洞察/汇率仍秒回"},
    ]
    seen: set[str] = set()
    for pref in priority:
        matched = _match_installed(pref, installed)
        if matched and matched not in seen and not _is_blocked(matched):
            seen.add(matched)
            choices.append(
                {
                    "id": matched,
                    "label": matched,
                    "hint": "推荐" if pref == priority[0] else "可选",
                }
            )
    for name in sorted(installed):
        if name in seen or _is_blocked(name):
            continue
        seen.add(name)
        choices.append({"id": name, "label": name, "hint": "已安装"})
    return choices
