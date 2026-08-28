"""Tests for the Anthropic provider (src/nl2sql/providers/anthropic_provider.py).

This is the original Phase 7B `generate_sql()` test suite, retargeted at
`AnthropicProvider` now that generation.py itself is provider-agnostic
(see tests/test_nl2sql_generation.py for the new delegation tests).
Exact same coverage: request shape, schema-context embedding, the
read-only rules, model default/override, structured output. Still uses
a fake Anthropic client -- no real API calls, no network, no API key
required (an explicitly injected client bypasses the config check, same
as the original `generate_sql(client=...)` did).
"""

from types import SimpleNamespace

import pytest

from src.nl2sql.providers.anthropic_provider import DEFAULT_MODEL, AnthropicProvider
from src.nl2sql.providers.base import ProviderConfigurationError, ProviderRequestError, SQLGenerationResult


class _FakeMessages:
    def __init__(self, result: SQLGenerationResult):
        self._result = result
        self.last_call = None

    def parse(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(parsed_output=self._result)


class _FakeClient:
    def __init__(self, result: SQLGenerationResult):
        self.messages = _FakeMessages(result)


SCHEMA_CONTEXT = "Table: orders\n  - order_id: VARCHAR(20)  [PK, NOT NULL]"


def test_generate_returns_the_clients_parsed_output():
    expected = SQLGenerationResult(
        sql="SELECT COUNT(*) FROM orders", explanation="Counts all orders.", tables_used=["orders"]
    )
    client = _FakeClient(expected)
    provider = AnthropicProvider(client=client)

    result = provider.generate("How many orders are there?", SCHEMA_CONTEXT)

    assert result is expected


def test_generate_sends_question_as_user_message():
    client = _FakeClient(SQLGenerationResult(sql="", explanation="", tables_used=[]))
    provider = AnthropicProvider(client=client)

    provider.generate("How many orders are there?", SCHEMA_CONTEXT)

    messages = client.messages.last_call["messages"]
    assert messages == [{"role": "user", "content": "How many orders are there?"}]


def test_generate_embeds_schema_context_in_system_prompt():
    client = _FakeClient(SQLGenerationResult(sql="", explanation="", tables_used=[]))
    provider = AnthropicProvider(client=client)

    provider.generate("How many orders are there?", SCHEMA_CONTEXT)

    system_prompt = client.messages.last_call["system"]
    assert SCHEMA_CONTEXT in system_prompt


def test_generate_instructs_read_only_sql_only():
    client = _FakeClient(SQLGenerationResult(sql="", explanation="", tables_used=[]))
    provider = AnthropicProvider(client=client)

    provider.generate("How many orders are there?", SCHEMA_CONTEXT)

    system_prompt = client.messages.last_call["system"].upper()
    assert "SELECT" in system_prompt
    for forbidden in ("INSERT", "UPDATE", "DELETE", "DROP"):
        assert forbidden in system_prompt  # named explicitly as disallowed


def test_uses_default_model_unless_overridden():
    client = _FakeClient(SQLGenerationResult(sql="", explanation="", tables_used=[]))

    AnthropicProvider(client=client).generate("How many orders are there?", SCHEMA_CONTEXT)
    assert client.messages.last_call["model"] == DEFAULT_MODEL

    AnthropicProvider(client=client, model="claude-sonnet-5").generate("How many orders are there?", SCHEMA_CONTEXT)
    assert client.messages.last_call["model"] == "claude-sonnet-5"


def test_generate_requests_structured_output_format():
    client = _FakeClient(SQLGenerationResult(sql="", explanation="", tables_used=[]))
    provider = AnthropicProvider(client=client)

    provider.generate("How many orders are there?", SCHEMA_CONTEXT)

    assert client.messages.last_call["output_format"] is SQLGenerationResult


# ---------------------------------------------------------------------------
# New in Phase 7F: configuration + failure surfacing
# ---------------------------------------------------------------------------


def test_construction_without_client_or_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(ProviderConfigurationError):
        AnthropicProvider()


def test_construction_with_an_explicit_client_never_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    client = _FakeClient(SQLGenerationResult(sql="", explanation="", tables_used=[]))
    AnthropicProvider(client=client)  # must not raise


def test_request_failure_is_wrapped_in_a_provider_request_error():
    class _BoomMessages:
        def parse(self, **kwargs):
            raise RuntimeError("invalid x-api-key")

    provider = AnthropicProvider(client=SimpleNamespace(messages=_BoomMessages()))
    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)
