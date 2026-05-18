"""OpenAI-compatible client wrapper for Manual IR enrichment."""

from __future__ import annotations

import os
from typing import Any, Dict, List


class LLMClientError(RuntimeError):
    """Raised when the enrichment LLM cannot be called."""


class OpenAICompatibleLLMClient:
    """Small wrapper around the OpenAI Python SDK.

    The wrapper intentionally stays narrow so enrichment remains an optional
    post-processing step. Environment defaults support OpenAI-compatible
    providers such as DeepSeek without importing application-level globals.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.1,
        timeout: float | None = None,
    ) -> None:
        _load_dotenv_if_available()
        self.model = model or os.getenv("MANUAL_IR_ENRICH_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-chat"
        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        self.base_url = (
            base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or "https://api.deepseek.com"
        )
        self.temperature = temperature
        self.timeout = timeout

    def complete_text(self, messages: List[Dict[str, str]]) -> str:
        return self._complete(messages, response_format=None)

    def complete_json(self, messages: List[Dict[str, str]]) -> str:
        return self._complete(messages, response_format={"type": "json_object"})

    def _complete(self, messages: List[Dict[str, str]], *, response_format: Dict[str, str] | None) -> str:
        if not self.api_key:
            raise LLMClientError(
                "LLM API key is not configured. Set OPENAI_API_KEY, DEEPSEEK_API_KEY, or LLM_API_KEY."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMClientError("openai package is required for Manual IR enrichment.") from exc

        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
        }
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        if self.timeout is not None:
            client_kwargs["timeout"] = self.timeout

        client = OpenAI(**client_kwargs)
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        try:
            response = client.chat.completions.create(**request_kwargs)
        except Exception as exc:  # pragma: no cover - provider-specific transport detail
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise LLMClientError("LLM response was empty.")
        return content


def _load_dotenv_if_available() -> None:
    try:
        import dotenv
    except ImportError:
        return
    dotenv.load_dotenv()
