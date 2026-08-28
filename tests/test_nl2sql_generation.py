"""Tests for the provider-agnostic generation layer (src/nl2sql/generation.py).

generation.py itself no longer knows about Anthropic, Gemini, Ollama, or
OpenRouter -- it only delegates to whatever SQLGenerationProvider it's
given (or, by default, whatever NL2SQL_PROVIDER selects via
get_sql_generation_provider()). These tests exercise that delegation
with a fake provider; see tests/test_nl2sql_providers.py for provider
selection/factory tests and tests/test_nl2sql_provider_*.py for each
concrete provider's own request-building tests.
"""

from src.nl2sql.generation import MAX_QUESTION_LENGTH, generate_sql, get_configuration_error, validate_question_length
from src.nl2sql.providers.base import ProviderConfigurationError, SQLGenerationProvider, SQLGenerationResult

SCHEMA_CONTEXT = "Table: orders\n  - order_id: VARCHAR(20)  [PK, NOT NULL]"


class _FakeProvider(SQLGenerationProvider):
    def __init__(self, result: SQLGenerationResult):
        self._result = result
        self.last_call = None

    def generate(self, question: str, schema_context: str) -> SQLGenerationResult:
        self.last_call = (question, schema_context)
        return self._result


def test_generate_sql_delegates_to_the_given_provider():
    expected = SQLGenerationResult(sql="SELECT COUNT(*) FROM orders", explanation="Counts orders.", tables_used=["orders"])
    provider = _FakeProvider(expected)

    result = generate_sql("How many orders are there?", SCHEMA_CONTEXT, provider=provider)

    assert result is expected


def test_generate_sql_passes_question_and_schema_context_through_unchanged():
    provider = _FakeProvider(SQLGenerationResult(sql="", explanation="", tables_used=[]))

    generate_sql("How many orders are there?", SCHEMA_CONTEXT, provider=provider)

    assert provider.last_call == ("How many orders are there?", SCHEMA_CONTEXT)


def test_generate_sql_uses_the_configured_provider_when_none_given(monkeypatch):
    """Without an explicit `provider=`, generate_sql must ask the
    provider factory -- proving generation.py delegates provider
    selection rather than hardcoding one, exactly as the architecture
    requires (dashboard -> generation layer -> provider)."""
    import src.nl2sql.generation as generation_module

    sentinel = _FakeProvider(SQLGenerationResult(sql="SELECT 1", explanation="", tables_used=[]))
    monkeypatch.setattr(generation_module, "get_sql_generation_provider", lambda: sentinel)

    result = generate_sql("q", SCHEMA_CONTEXT)

    assert result.sql == "SELECT 1"
    assert sentinel.last_call == ("q", SCHEMA_CONTEXT)


def test_get_configuration_error_is_none_when_provider_is_ready(monkeypatch):
    import src.nl2sql.generation as generation_module

    monkeypatch.setattr(generation_module, "get_sql_generation_provider", lambda: _FakeProvider(None))

    assert get_configuration_error() is None


def test_get_configuration_error_surfaces_a_safe_message_when_not_ready(monkeypatch):
    import src.nl2sql.generation as generation_module

    def boom():
        raise ProviderConfigurationError("GEMINI_API_KEY is not set.")

    monkeypatch.setattr(generation_module, "get_sql_generation_provider", boom)

    error = get_configuration_error()

    assert error == "GEMINI_API_KEY is not set."


# ---------------------------------------------------------------------------
# Phase 7H: maximum question length (checked before generate_sql() is ever
# called -- see dashboard/nl2sql_ui.py, which is the only current caller
# of this guard).
# ---------------------------------------------------------------------------


def test_question_under_the_limit_is_accepted():
    assert validate_question_length("How many successful payments were made?") is None


def test_question_exactly_at_the_limit_is_accepted():
    question = "a" * MAX_QUESTION_LENGTH
    assert validate_question_length(question) is None


def test_question_one_over_the_limit_is_rejected():
    question = "a" * (MAX_QUESTION_LENGTH + 1)
    assert validate_question_length(question) is not None


def test_question_well_over_the_limit_is_rejected():
    question = "a" * (MAX_QUESTION_LENGTH * 10)
    assert validate_question_length(question) is not None


def test_rejection_message_is_clear_and_mentions_the_limit():
    question = "a" * (MAX_QUESTION_LENGTH + 1)
    message = validate_question_length(question)
    assert str(MAX_QUESTION_LENGTH) in message
    assert "too long" in message.lower()


def test_max_question_length_is_a_single_well_defined_constant():
    assert isinstance(MAX_QUESTION_LENGTH, int)
    assert MAX_QUESTION_LENGTH > 0


def test_get_configuration_error_never_raises_for_other_provider_errors(monkeypatch):
    """get_configuration_error() only catches ProviderConfigurationError
    -- anything else (a genuine bug) should still surface as a real
    exception rather than being silently swallowed."""
    import src.nl2sql.generation as generation_module

    def boom():
        raise RuntimeError("unexpected")

    monkeypatch.setattr(generation_module, "get_sql_generation_provider", boom)

    try:
        get_configuration_error()
        raised = False
    except RuntimeError:
        raised = True
    assert raised is True
