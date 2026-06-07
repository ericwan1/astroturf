"""Thin wrapper for local Ollama inference."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import requests

ChatMessage = dict[str, str]


@dataclass
class LLMConfig:
    """Configuration for Ollama API calls."""

    base_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    temperature: float = 0.8
    max_tokens: int = 256
    top_p: float = 0.9
    timeout_seconds: int = 120
    think: Optional[bool] = False


class LLMWrapper:
    """
    Local inference client for Ollama.

    Prefer `chat()` for structured prompts (system + user + few-shot examples).
    `generate()` and `generate_response()` remain for simple single-string prompts.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.logger = logging.getLogger(__name__)

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a response from a chat-style message list."""
        payload = {
            "model": model or self.config.model,
            "messages": messages,
            "stream": False,
            "options": self._options(temperature, max_tokens),
        }
        if self.config.think is not None:
            payload["think"] = self.config.think
        data = self._post("/api/chat", payload)
        message = data.get("message") or {}
        return str(message.get("content", "")).strip()

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate from a single user prompt, optionally with a system message."""
        messages: list[ChatMessage] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream_output: bool = False,
    ) -> str:
        """
        Backward-compatible single-prompt generation.

        `stream_output` is ignored; Ollama calls use non-streaming responses.
        """
        if stream_output:
            self.logger.warning("stream_output is not supported; using non-streaming chat")
        return self.generate(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _options(
        self,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> dict[str, Any]:
        return {
            "temperature": self.config.temperature if temperature is None else temperature,
            "num_predict": self.config.max_tokens if max_tokens is None else max_tokens,
            "top_p": self.config.top_p,
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error("Ollama request failed: %s", exc)
            raise
        except json.JSONDecodeError as exc:
            self.logger.error("Ollama returned invalid JSON: %s", exc)
            raise
