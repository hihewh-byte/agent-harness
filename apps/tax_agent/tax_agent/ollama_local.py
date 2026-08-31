"""Standalone Ollama HTTP client for tax-agent (no PHA dependency)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import httpx


@dataclass(frozen=True)
class OllamaModelEntry:
    name: str
    size: int = 0
    parameter_size: str = ""


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent
    for path in (root / ".env", Path.cwd() / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


def apply_keep_alive(body: dict[str, Any]) -> dict[str, Any]:
  keep = (os.environ.get("OLLAMA_KEEP_ALIVE") or "").strip()
  if keep:
      body = dict(body)
      body["keep_alive"] = keep
  return body


def list_ollama_model_entries(
    base_url: str,
    *,
    timeout_seconds: float,
) -> list[OllamaModelEntry]:
    url = f"{base_url.rstrip('/')}/api/tags"
    timeout = httpx.Timeout(timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
    payload: dict[str, Any] = response.json()
    out: list[OllamaModelEntry] = []
    for entry in payload.get("models") or []:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        size = int(entry.get("size") or 0)
        details = entry.get("details") or {}
        param = str(details.get("parameter_size") or "") if isinstance(details, dict) else ""
        out.append(OllamaModelEntry(name=name, size=size, parameter_size=param))
    return out


def list_ollama_installed_models(
    base_url: str,
    *,
    timeout_seconds: float,
) -> list[str]:
    return [m.name for m in list_ollama_model_entries(base_url, timeout_seconds=timeout_seconds)]


def list_text_llm_models(entries: list[OllamaModelEntry]) -> list[OllamaModelEntry]:
    blocked = ("vision", "llava", "multimodal", "embed")
    out: list[OllamaModelEntry] = []
    for e in entries:
        n = e.name.lower()
        if any(b in n for b in blocked):
            continue
        out.append(e)
    return out


def pick_largest_text_model(entries: list[OllamaModelEntry]) -> str | None:
    text = list_text_llm_models(entries)
    if not text:
        return None
    return max(text, key=lambda e: e.size).name


class OllamaProvider:
    """Synchronous Ollama client via httpx (tax-agent standalone)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        load_dotenv_if_present()
        resolved_base = (
            base_url
            or os.environ.get("TAX_AGENT_OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_BASE_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        resolved_model = model or os.environ.get("TAX_AGENT_MODEL") or os.environ.get("OLLAMA_MODEL")
        if not resolved_model or not str(resolved_model).strip():
            msg = "TAX_AGENT_MODEL or OLLAMA_MODEL must be set; refusing to guess."
            raise ValueError(msg)
        raw_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.environ.get("LLM_TIMEOUT_SECONDS", "300"))
        )
        if raw_timeout <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        self._base_url = resolved_base
        self._model = str(resolved_model).strip()
        self._timeout_seconds = float(raw_timeout)
        self._http_timeout = httpx.Timeout(self._timeout_seconds)
        self._assert_model_installed()

    @property
    def model(self) -> str:
        return self._model

    def _assert_model_installed(self) -> None:
        installed = list_ollama_installed_models(
            self._base_url,
            timeout_seconds=min(self._timeout_seconds, 10.0),
        )
        if self._model not in installed:
            raise ValueError(
                f"OLLAMA model {self._model!r} not installed at {self._base_url!r}; "
                f"installed={installed!r}"
            )

    def chat_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._assert_model_installed()
        url = f"{self._base_url}/api/chat"
        body = apply_keep_alive(
            {
                "model": self._model,
                "messages": messages,
                "tools": tools,
                "stream": False,
            },
        )
        with httpx.Client(timeout=self._http_timeout) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
        return response.json()

    def stream_chat_messages(self, *, messages: list[dict[str, Any]]) -> Iterator[str]:
        self._assert_model_installed()
        url = f"{self._base_url}/api/chat"
        body = apply_keep_alive(
            {
                "model": self._model,
                "messages": messages,
                "stream": True,
            },
        )
        with httpx.Client(timeout=self._http_timeout) as client:
            with client.stream("POST", url, json=body) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    message = chunk.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, str) and content:
                        yield content
