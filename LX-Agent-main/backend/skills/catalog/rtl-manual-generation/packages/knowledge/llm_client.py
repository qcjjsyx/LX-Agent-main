"""OpenAI-compatible client wrapper for Knowledge IR semantic enrichment."""

from __future__ import annotations

import os
from typing import Any, Dict, List


class LLMClientError(RuntimeError):
    """Raised when the semantic enrichment LLM cannot be called."""


class OpenAICompatibleLLMClient:
    """Small wrapper around the OpenAI Python SDK.

    This client intentionally stays provider-neutral. It supports OpenAI and
    OpenAI-compatible endpoints such as DeepSeek through environment variables.
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
        self.model = (
            model
            or os.getenv("DEEPSEEK_MODEL")
            or os.getenv("KNOWLEDGE_IR_SEMANTIC_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "deepseek-chat"
        )
        self.api_key = (
            api_key
            or os.getenv("KNOWLEDGE_IR_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        self.base_url = (
            base_url
            or os.getenv("KNOWLEDGE_IR_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or "https://api.deepseek.com"
        )
        self.temperature = temperature
        self.timeout = timeout

    def complete_text(self, messages: List[Dict[str, str]]) -> str:
        if not self.api_key:
            raise LLMClientError(
                "LLM API key is not configured. Set KNOWLEDGE_IR_API_KEY, "
                "OPENAI_API_KEY, DEEPSEEK_API_KEY, or LLM_API_KEY."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMClientError("openai package is required for Knowledge IR semantic enrichment.") from exc

        client_kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        if self.timeout is not None:
            client_kwargs["timeout"] = self.timeout

        client = OpenAI(**client_kwargs)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages, # type: ignore
                temperature=self.temperature,
            )
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
