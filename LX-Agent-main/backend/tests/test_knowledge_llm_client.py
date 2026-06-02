from __future__ import annotations

import types

from backend.tests.module_loader import load_llm_client


def test_semantic_model_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("KNOWLEDGE_IR_SEMANTIC_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    llm_client = load_llm_client()
    client = llm_client.OpenAICompatibleLLMClient()

    assert client.model == "deepseek-v4-flash"
    assert client.disable_thinking is True


def test_v4_request_disables_thinking(monkeypatch):
    captured_client_kwargs = {}
    captured_request_kwargs = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured_request_kwargs.update(kwargs)
            message = types.SimpleNamespace(content="OK")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured_client_kwargs.update(kwargs)
            self.chat = types.SimpleNamespace(
                completions=FakeCompletions(),
            )

    fake_openai = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)

    llm_client = load_llm_client()
    client = llm_client.OpenAICompatibleLLMClient(
        model="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        timeout=30,
    )

    assert client.complete_text([{"role": "user", "content": "ping"}]) == "OK"
    assert captured_client_kwargs == {
        "api_key": "test-key",
        "base_url": "https://api.deepseek.com",
        "timeout": 30,
    }
    assert captured_request_kwargs["model"] == "deepseek-v4-flash"
    assert captured_request_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_non_v4_request_does_not_add_thinking_body(monkeypatch):
    captured_request_kwargs = {}
    monkeypatch.setenv("KNOWLEDGE_IR_DISABLE_THINKING", "false")

    class FakeCompletions:
        def create(self, **kwargs):
            captured_request_kwargs.update(kwargs)
            message = types.SimpleNamespace(content="OK")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(__import__("sys").modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    llm_client = load_llm_client()
    client = llm_client.OpenAICompatibleLLMClient(model="some-openai-compatible-model", api_key="test-key")

    assert client.complete_text([{"role": "user", "content": "ping"}]) == "OK"
    assert "extra_body" not in captured_request_kwargs
