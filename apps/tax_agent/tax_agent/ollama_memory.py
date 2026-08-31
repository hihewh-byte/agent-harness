from __future__ import annotations

import os
from typing import List

from tax_agent.pha_llm import ensure_pha_importable, ollama_base_url


# 16GB Mac：报税前可卸载占 VRAM 的大模型
HEAVY_MODELS_DEFAULT: tuple[str, ...] = (
    "gemma4:26b",
    "llama3.2-vision:11b",
    "gemma4:e4b",
)


def unload_heavy_models_enabled() -> bool:
    v = (os.environ.get("TAX_AGENT_UNLOAD_HEAVY_MODELS") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def prepare_ollama_for_tax(*, keep_model: str | None = None) -> List[str]:
    """
    在加载报税对话模型前，卸载已知重模型以释放统一内存。
    返回成功请求卸载的模型名列表。
    """
    if not unload_heavy_models_enabled():
        return []
    ensure_pha_importable()
    from pha.ollama_runtime import unload_ollama_model

    base = ollama_base_url()
    keep = (keep_model or "").strip()
    unloaded: List[str] = []
    for name in HEAVY_MODELS_DEFAULT:
        if keep and name == keep:
            continue
        if unload_ollama_model(name, base_url=base):
            unloaded.append(name)
    return unloaded
