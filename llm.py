"""Unified chat wrapper over local and cloud LLM providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from llm_providers import ChatMessage, ProviderConfig, create_provider

__all__ = ["ChatMessage", "LLMConfig", "LLMWrapper"]


@dataclass
class LLMConfig:
    """Configuration for LLM calls."""

    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    api_key: Optional[str] = None
    temperature: float = 0.8
    max_tokens: int = 256
    top_p: float = 0.9
    timeout_seconds: int = 120
    think: Optional[bool] = False

    def to_provider_config(self) -> ProviderConfig:
        return ProviderConfig(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            timeout_seconds=self.timeout_seconds,
            think=self.think,
        )

    @classmethod
    def from_env(cls, provider: Optional[str] = None) -> "LLMConfig":
        provider_config = ProviderConfig.from_env(provider)
        return cls(
            provider=provider_config.provider,
            model=provider_config.model,
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
            temperature=provider_config.temperature,
            max_tokens=provider_config.max_tokens,
            top_p=provider_config.top_p,
            timeout_seconds=provider_config.timeout_seconds,
            think=provider_config.think,
        )


class LLMWrapper:
    """
    Chat wrapper used across Astroturf.

    Supports:
    - `ollama` for local inference
    - `gemini` for Google Gemini API
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.logger = logging.getLogger(__name__)
        self._provider = create_provider(self.config.to_provider_config())

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        return self._provider.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
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
        if stream_output:
            self.logger.warning("stream_output is not supported")
        return self.generate(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
