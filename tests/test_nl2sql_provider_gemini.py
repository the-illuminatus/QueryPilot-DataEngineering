"""Tests for the Gemini provider (src/nl2sql/providers/gemini.py).

No real network call: a fake `session` object (duck-typing
requests.Session's `.post()`) is injected, so these tests are
deterministic and free -- no GEMINI_API_KEY needed except a fake value
to satisfy the provider's own config check.
"""

import pytest
import requests

from src.nl2sql.providers.base import ProviderConfigurationError, ProviderRequestError
from src.nl2sql.providers.gemini import _TIMEOUT_SECONDS, DEFAULT_MODEL, GeminiProvider

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


def _gemini_envelope(sql="SELECT 1", explanation="test", tables=None):
    import json

    body = json.dumps({"sql": sql, "explanation": explanation, "tables_used": tables or []})
    return {"candidates": [{"content": {"parts": [{"text": body}]}}]}


class _FakeSession:
    def __init__(self, response):
        self._response = response
        self.last_call = None

    def post(self, url, headers=None, json=None, timeout=None):
        self.last_call = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return self._response


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_construction_without_api_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError):
        GeminiProvider()


def test_construction_with_explicit_api_key_does_not_require_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    GeminiProvider(api_key="fake-key")  # must not raise


# ---------------------------------------------------------------------------
# Request shape
# ---------------------------------------------------------------------------


def test_generate_sends_api_key_in_header_not_url():
    session = _FakeSession(_FakeResponse(_gemini_envelope()))
    provider = GeminiProvider(api_key="fake-key-value", session=session)

    provider.generate("How many orders?", SCHEMA_CONTEXT)

    assert session.last_call["headers"]["x-goog-api-key"] == "fake-key-value"
    assert "fake-key-value" not in session.last_call["url"]


def test_generate_embeds_schema_context_in_system_instruction():
    session = _FakeSession(_FakeResponse(_gemini_envelope()))
    provider = GeminiProvider(api_key="fake-key", session=session)

    provider.generate("How many orders?", SCHEMA_CONTEXT)

    system_text = session.last_call["json"]["systemInstruction"]["parts"]["text"]
    assert SCHEMA_CONTEXT in system_text


def test_generate_sends_question_as_user_content():
    session = _FakeSession(_FakeResponse(_gemini_envelope()))
    provider = GeminiProvider(api_key="fake-key", session=session)

    provider.generate("How many orders?", SCHEMA_CONTEXT)

    contents = session.last_call["json"]["contents"]
    assert contents == [{"role": "user", "parts": [{"text": "How many orders?"}]}]


def test_generate_requests_json_structured_output():
    session = _FakeSession(_FakeResponse(_gemini_envelope()))
    provider = GeminiProvider(api_key="fake-key", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    gen_config = session.last_call["json"]["generationConfig"]
    assert gen_config["responseMimeType"] == "application/json"
    assert "responseSchema" in gen_config


def test_timeout_is_generous_enough_for_real_structured_output_latency():
    """Regression guard: a live diagnostic measured a real, successful
    structured-output generateContent call against gemini-flash-latest
    taking ~81s. A too-short timeout aborts an otherwise-successful
    request -- assert the configured timeout leaves real headroom above
    that measurement, not just "some positive number"."""
    session = _FakeSession(_FakeResponse(_gemini_envelope()))
    provider = GeminiProvider(api_key="fake-key", session=session)

    provider.generate("q", SCHEMA_CONTEXT)

    assert session.last_call["timeout"] == _TIMEOUT_SECONDS
    assert _TIMEOUT_SECONDS >= 60


def test_uses_default_model_unless_overridden():
    session = _FakeSession(_FakeResponse(_gemini_envelope()))
    GeminiProvider(api_key="fake-key", session=session).generate("q", SCHEMA_CONTEXT)
    assert f"/models/{DEFAULT_MODEL}:generateContent" in session.last_call["url"]

    GeminiProvider(api_key="fake-key", model="gemini-custom", session=session).generate("q", SCHEMA_CONTEXT)
    assert "/models/gemini-custom:generateContent" in session.last_call["url"]


# ---------------------------------------------------------------------------
# Response mapping -> SQLGenerationResult
# ---------------------------------------------------------------------------


def test_generate_maps_response_to_sql_generation_result():
    session = _FakeSession(
        _FakeResponse(_gemini_envelope(sql="SELECT COUNT(*) FROM orders", explanation="counts orders", tables=["orders"]))
    )
    provider = GeminiProvider(api_key="fake-key", session=session)

    result = provider.generate("How many orders?", SCHEMA_CONTEXT)

    assert result.sql == "SELECT COUNT(*) FROM orders"
    assert result.explanation == "counts orders"
    assert result.tables_used == ["orders"]


# ---------------------------------------------------------------------------
# Failures are safely surfaced
# ---------------------------------------------------------------------------


def test_http_error_is_wrapped_in_provider_request_error():
    session = _FakeSession(_FakeResponse({}, status_code=401))
    provider = GeminiProvider(api_key="fake-key", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)


def test_malformed_response_shape_is_wrapped_in_provider_request_error():
    session = _FakeSession(_FakeResponse({"candidates": []}))  # no content at all
    provider = GeminiProvider(api_key="fake-key", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)


def test_non_json_text_is_wrapped_in_provider_request_error():
    session = _FakeSession(
        _FakeResponse({"candidates": [{"content": {"parts": [{"text": "not json at all"}]}}]})
    )
    provider = GeminiProvider(api_key="fake-key", session=session)

    with pytest.raises(ProviderRequestError):
        provider.generate("q", SCHEMA_CONTEXT)


def test_api_key_never_appears_in_a_raised_error_message():
    session = _FakeSession(_FakeResponse({}, status_code=401))
    provider = GeminiProvider(api_key="super-secret-key-value", session=session)

    with pytest.raises(ProviderRequestError) as exc_info:
        provider.generate("q", SCHEMA_CONTEXT)

    assert "super-secret-key-value" not in str(exc_info.value)
