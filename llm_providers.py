"""LLM provider implementations for Astroturf."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import requests

ChatMessage = dict[str, str]


@dataclass
class ProviderConfig:
    provider: str = "ollama"
    model: str = "llama3.2"
    api_key: Optional[str] = None
    base_url: str = "http://localhost:11434"
    temperature: float = 0.8
    max_tokens: int = 256
    top_p: float = 0.9
    timeout_seconds: int = 120
    think: Optional[bool] = False

    @classmethod
    def from_env(cls, provider: Optional[str] = None) -> "ProviderConfig":
        selected = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        if selected == "gemini":
            return cls(
                provider="gemini",
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
                api_key=os.getenv("GEMINI_API_KEY"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.8")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "256")),
                timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
            )
        return cls(
            provider="ollama",
            model=os.getenv("OLLAMA_MODEL", "deepseek-r1:1.5b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.8")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
            timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
            think=False,
        )


class ChatProvider(Protocol):
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str: ...


class OllamaProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature if temperature is None else temperature,
                "num_predict": self.config.max_tokens if max_tokens is None else max_tokens,
                "top_p": self.config.top_p,
            },
        }
        if self.config.think is not None:
            payload["think"] = self.config.think

        url = f"{self.config.base_url.rstrip('/')}/api/chat"
        response = requests.post(url, json=payload, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        return str(message.get("content", "")).strip()


class GeminiProvider:
    """Google Gemini generateContent API."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        if not config.api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        system_text = "\n\n".join(
            message["content"]
            for message in messages
            if message.get("role") == "system" and message.get("content")
        )
        contents = []
        for message in messages:
            role = message.get("role")
            if role in {"system", None}:
                continue
            gemini_role = "user" if role == "user" else "model"
            contents.append(
                {
                    "role": gemini_role,
                    "parts": [{"text": message["content"]}],
                }
            )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature if temperature is None else temperature,
                "maxOutputTokens": self.config.max_tokens if max_tokens is None else max_tokens,
                "topP": self.config.top_p,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        model_name = model or self.config.model
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent"
        )
        response = requests.post(
            url,
            params={"key": self.config.api_key},
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data)[:300]}")

        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        return text


def create_provider(config: ProviderConfig) -> ChatProvider:
    if config.provider == "gemini":
        return GeminiProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
