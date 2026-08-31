"""Ollama bridge — prefer PHA when co-installed; else standalone ``ollama_local``."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterator


def _walk_repo_roots() -> list[Path]:
    here = Path(__file__).resolve()
    roots: list[Path] = []
    seen: set[str] = set()
    for anc in here.parents:
        key = str(anc)
        if key in seen:
            continue
        seen.add(key)
        roots.append(anc)
    env_root = (os.environ.get("HARNESS_REPO_ROOT") or os.environ.get("PHA_ROOT") or "").strip()
    if env_root:
        roots.insert(0, Path(env_root))
    legacy = here.parents[2] / "personal_health_agent"
    if legacy.is_dir():
        roots.insert(0, legacy)
    return roots


def _pha_root() -> Path | None:
    for root in _walk_repo_roots():
        if (root / "pha" / "llm_provider.py").is_file():
            return root
    return None


def ensure_pha_importable() -> Path | None:
    """Add PHA repo root to ``sys.path`` when present (optional)."""
    root = _pha_root()
    if not root:
        return None
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def _use_pha_backend() -> bool:
    if (os.environ.get("TAX_AGENT_OLLAMA_BACKEND") or "").strip().lower() == "local":
        return False
    return _pha_root() is not None


def import_ollama_provider():
    if _use_pha_backend():
        ensure_pha_importable()
        from pha.llm_provider import OllamaProvider

        return OllamaProvider
    from tax_agent.ollama_local import OllamaProvider

    return OllamaProvider


def import_llm_utils():
    if _use_pha_backend():
        ensure_pha_importable()
        from pha.llm_provider import (
            list_ollama_installed_models,
            list_ollama_model_entries,
            list_text_llm_models,
            pick_largest_text_model,
        )

        return {
            "list_ollama_installed_models": list_ollama_installed_models,
            "list_ollama_model_entries": list_ollama_model_entries,
            "list_text_llm_models": list_text_llm_models,
            "pick_largest_text_model": pick_largest_text_model,
        }
    from tax_agent import ollama_local as loc

    return {
        "list_ollama_installed_models": loc.list_ollama_installed_models,
        "list_ollama_model_entries": loc.list_ollama_model_entries,
        "list_text_llm_models": loc.list_text_llm_models,
        "pick_largest_text_model": loc.pick_largest_text_model,
    }


def ollama_base_url() -> str:
    if _use_pha_backend():
        ensure_pha_importable()
        from pha.llm_provider import load_dotenv_if_present

        load_dotenv_if_present()
    else:
        from tax_agent.ollama_local import load_dotenv_if_present

        load_dotenv_if_present()
    return (
        os.environ.get("TAX_AGENT_OLLAMA_BASE_URL")
        or os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("OLLAMA_HOST")
        or "http://127.0.0.1:11434"
    ).rstrip("/")


def chat_completion_messages(
    provider: Any,
    *,
    messages: list[dict[str, str]],
    json_mode: bool = False,
) -> str:
    """Multi-turn chat via Ollama /api/chat."""
    import httpx

    if _use_pha_backend():
        from pha.ollama_payload import apply_keep_alive
    else:
        from tax_agent.ollama_local import apply_keep_alive

    url = f"{provider._base_url}/api/chat"
    body: dict[str, Any] = apply_keep_alive(
        {
            "model": provider._model,
            "messages": messages,
            "stream": False,
        },
    )
    if json_mode:
        body["format"] = "json"
    with httpx.Client(timeout=provider._http_timeout) as client:
        response = client.post(url, json=body)
        response.raise_for_status()
    data = response.json()
    message = data.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"Ollama empty response: {data!r}")
    return content.strip()


def iter_chat_completion_messages(
    provider: Any,
    *,
    messages: list[dict[str, str]],
) -> Iterator[str]:
    yield from provider.stream_chat_messages(messages=messages)


def chat_with_tools_messages(
    provider: Any,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    return provider.chat_with_tools(messages=messages, tools=tools)
