"""Tests for the Ollama provider (src/nl2sql/providers/ollama.py).

No real Ollama server, no real network call: a fake `session` object is
injected. Does not require a locally installed/running Ollama or a
pulled model for the normal test suite -- the "Ollama unavailable" path
is tested explicitly by having the fake session raise a connection
error, not by actually failing to connect anywhere.
"""

import json

import pytest
import requests

from src.nl2sql.providers.base import ProviderConfigurationError, ProviderRequestError
from src.nl2sql.providers.ollama import OllamaProvider

SCHEMA_CONTEXT = "Table: orders\n  - order_id: VARCHAR(20)  [PK, NOT NULL]"


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data


def _ollama_envelope(sql="SELECT 1", explanation="test", tables=None):
    content = json.dumps({"sql": sql, "explanation": explanation, "tables_used": tables or []})
    return {"message": {"role": "assistant", "content": content}, "done": True}


class _FakeSession:
    def __init__(self, response=None, raise_connection_error=False):
        self._response = response
        self._raise_connection_error = raise_connection_error
        self.last_call = None

    def post(self, url, json=None, timeout=None):
        self.last_call = {"url": url, "json": json, "timeout": timeout}
        if self._raise_connection_error:
            raise requests.exceptions.ConnectionError("refused")
        return self._response


# ---------------------------------------------------------------------------
# Configuration -- no cloud key, but a model name is required
# ---------------------------------------------------------------------------


def test_construction_without_model_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("NL2SQL_MODEL", raising=False)
    with pytest.raises(ProviderConfigurationError):
        OllamaProvider()


def test_construction_with_explicit_model_does_not_require_env(monkeypatch):
    monkeypatch.delenv("NL2SQL_MODEL", raising=False)
    OllamaProvider(model="llama3.1")  # must not raise


def test_default_base_url_is_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    session = _FakeSession(_FakeResponse(_ollama_envelope()))
    provider = OllamaProvider(model="llama3.1", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    assert session.last_call["url"] == "http://localhost:11434/api/chat"


def test_base_url_is_configurable():
    session = _FakeSession(_FakeResponse(_ollama_envelope()))
    provider = OllamaProvider(model="llama3.1", base_url="http://gpu-box:11434", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    assert session.last_call["url"] == "http://gpu-box:11434/api/chat"


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------


def test_generate_sends_system_and_user_messages():
    session = _FakeSession(_FakeResponse(_ollama_envelope()))
    provider = OllamaProvider(model="llama3.1", session=session)

    provider.generate("How many orders?", SCHEMA_CONTEXT)

    messages = session.last_call["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert SCHEMA_CONTEXT in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "How many orders?"}


def test_generate_requests_non_streaming_structured_output():
    session = _FakeSession(_FakeResponse(_ollama_envelope()))
    provider = OllamaProvider(model="llama3.1", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    payload = session.last_call["json"]
    assert payload["stream"] is False
    assert payload["model"] == "llama3.1"
    assert "format" in payload


# ---------------------------------------------------------------------------
# Response mapping -> SQLGenerationResult
# ---------------------------------------------------------------------------


def test_generate_maps_response_to_sql_generation_result():
    session = _FakeSession(
        _FakeResponse(_ollama_envelope(sql="SELECT COUNT(*) FROM orders", explanation="counts orders", tables=["orders"]))
    )
    provider = OllamaProvider(model="llama3.1", session=session)

    result = provider.generate("How many orders?", SCHEMA_CONTEXT)

    assert result.sql == "SELECT COUNT(*) FROM orders"
    assert result.tables_used == ["orders"]


# ---------------------------------------------------------------------------
# "Ollama unavailable" is a clear, safe error -- not a crash
# ---------------------------------------------------------------------------


def test_connection_error_is_a_clear_configuration_error_naming_the_url():
    session = _FakeSession(raise_connection_error=True)
    provider = OllamaProvider(model="llama3.1", base_url="http://localhost:11434", session=session)

    with pytest.raises(ProviderConfigurationError) as exc_info:
        provider.generate("q", SCHEMA_CONTEXT)

    assert "localhost:11434" in str(exc_info.value)


def test_http_error_is_wrapped_in_provider_request_error():
    session = _FakeSession(_FakeResponse({}, status_code=500))
    provider = OllamaProvider(model="llama3.1", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)


def test_malformed_response_is_wrapped_in_provider_request_error():
    session = _FakeSession(_FakeResponse({"done": True}))  # no "message" key
    provider = OllamaProvider(model="llama3.1", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)
