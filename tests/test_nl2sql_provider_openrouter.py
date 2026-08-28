"""Tests for the OpenRouter provider (src/nl2sql/providers/openrouter.py).

No real network call: a fake `session` object is injected. No real
OPENROUTER_API_KEY needed except a fake value to satisfy the provider's
own config check.
"""

import json

import pytest
import requests

from src.nl2sql.providers.base import ProviderConfigurationError, ProviderRequestError
from src.nl2sql.providers.openrouter import OpenRouterProvider

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


def _openrouter_envelope(sql="SELECT 1", explanation="test", tables=None):
    content = json.dumps({"sql": sql, "explanation": explanation, "tables_used": tables or []})
    return {"choices": [{"message": {"content": content}}]}


class _FakeSession:
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return self._response


# ---------------------------------------------------------------------------
# Configuration -- both an API key and an explicit model are required
# ---------------------------------------------------------------------------


def test_construction_without_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError):
        OpenRouterProvider(model="some/model:free")


def test_construction_without_model_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("NL2SQL_MODEL", raising=False)
    with pytest.raises(ProviderConfigurationError):
        OpenRouterProvider(api_key="fake-key")


def test_construction_with_explicit_values_does_not_require_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NL2SQL_MODEL", raising=False)
    OpenRouterProvider(api_key="fake-key", model="some/model:free")  # must not raise


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------


def test_generate_sends_bearer_authorization_header():
    session = _FakeSession(_FakeResponse(_openrouter_envelope()))
    provider = OpenRouterProvider(api_key="fake-key-value", model="some/model:free", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    assert session.last_call["headers"]["Authorization"] == "Bearer fake-key-value"


def test_generate_sends_system_and_user_messages():
    session = _FakeSession(_FakeResponse(_openrouter_envelope()))
    provider = OpenRouterProvider(api_key="fake-key", model="some/model:free", session=session)

    provider.generate("How many orders?", SCHEMA_CONTEXT)

    messages = session.last_call["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert SCHEMA_CONTEXT in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "How many orders?"}


def test_generate_requests_strict_json_schema_structured_output():
    session = _FakeSession(_FakeResponse(_openrouter_envelope()))
    provider = OpenRouterProvider(api_key="fake-key", model="some/model:free", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    response_format = session.last_call["json"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True


def test_generate_uses_the_configured_model():
    session = _FakeSession(_FakeResponse(_openrouter_envelope()))
    provider = OpenRouterProvider(api_key="fake-key", model="meta-llama/llama-3.1-8b-instruct:free", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    assert session.last_call["json"]["model"] == "meta-llama/llama-3.1-8b-instruct:free"


# ---------------------------------------------------------------------------
# Response mapping -> SQLGenerationResult
# ---------------------------------------------------------------------------


def test_generate_maps_response_to_sql_generation_result():
    session = _FakeSession(
        _FakeResponse(_openrouter_envelope(sql="SELECT COUNT(*) FROM orders", explanation="counts orders", tables=["orders"]))
    )
    provider = OpenRouterProvider(api_key="fake-key", model="some/model:free", session=session)

    result = provider.generate("How many orders?", SCHEMA_CONTEXT)

    assert result.sql == "SELECT COUNT(*) FROM orders"
    assert result.tables_used == ["orders"]


# ---------------------------------------------------------------------------
# Failures are safely surfaced
# ---------------------------------------------------------------------------


def test_http_error_is_wrapped_in_provider_request_error():
    session = _FakeSession(_FakeResponse({}, status_code=402))  # e.g. out of free credits
    provider = OpenRouterProvider(api_key="fake-key", model="some/model:free", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)


def test_malformed_response_is_wrapped_in_provider_request_error():
    session = _FakeSession(_FakeResponse({"choices": []}))
    provider = OpenRouterProvider(api_key="fake-key", model="some/model:free", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)


def test_api_key_never_appears_in_a_raised_error_message():
    session = _FakeSession(_FakeResponse({}, status_code=401))
    provider = OpenRouterProvider(api_key="super-secret-key-value", model="some/model:free", session=session)

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.generate("q", SCHEMA_CONTEXT)

    assert "super-secret-key-value" not in str(exc_info.value)
