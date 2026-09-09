"""Ollama request payload helpers (no imports from llm_provider)."""

from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import load_dotenv


def ollama_keep_alive_value() -> int | str:
    load_dotenv(override=False)
    raw = (os.environ.get("OLLAMA_KEEP_ALIVE") or "0").strip()
    if raw.lower() in ("0", "false", "no", "off"):
        return 0
    if raw.isdigit():
        return int(raw)
    return raw


def apply_keep_alive(body: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(body)
    out["keep_alive"] = ollama_keep_alive_value()
    return out


def ollama_think_value() -> bool | None:
    """``OLLAMA_THINK`` → Ollama ``think`` request field.

    Unset/empty → ``None`` (do not send; required for models without thinking
    capability, e.g. qwen2.5, where Ollama rejects an explicit ``think``).
    ``false/0/off/no`` → ``False`` (qwen3 / deepseek-r1: skip reasoning, faster
    fact-card interpret, no ``<think>`` leakage). ``true/1/on/yes`` → ``True``.
    """
    load_dotenv(override=False)
    raw = (os.environ.get("OLLAMA_THINK") or "").strip().lower()
    if not raw:
        return None
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return None


def apply_think_option(body: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(body)
    think = ollama_think_value()
    if think is not None:
        out["think"] = think
    return out


def apply_ollama_options(body: Dict[str, Any]) -> Dict[str, Any]:
    """keep_alive + think (env-driven) in one pass for ``/api/chat`` bodies."""
    return apply_think_option(apply_keep_alive(body))
