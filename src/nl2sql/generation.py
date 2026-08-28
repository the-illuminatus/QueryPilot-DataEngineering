"""LLM-based candidate SQL generation.

Takes a natural-language question and the schema context produced by
`context.build_schema_context()` and asks the configured LLM provider
for a single candidate PostgreSQL SELECT statement. This module only
*generates* SQL -- it does not validate the statement beyond what
structured output guarantees (the response shape), and it never
executes anything against the warehouse. Validation and execution are
later, separate phases.

This module itself has no idea which LLM backend answers the question.
NL2SQL_PROVIDER (see src/nl2sql/providers/__init__.py) selects one of
Anthropic Claude, Google Gemini, a local Ollama model, or OpenRouter;
generate_sql() just asks the selected provider and returns its
SQLGenerationResult. Every provider produces the exact same result
shape (sql / explanation / tables_used) regardless of which one
answered.
"""

from typing import Optional

from .providers import (
    ProviderConfigurationError,
    SQLGenerationProvider,
    SQLGenerationResult,
    get_sql_generation_provider,
)

__all__ = ["generate_sql", "get_configuration_error", "SQLGenerationResult"]


def get_configuration_error() -> Optional[str]:
    """None if the currently configured NL2SQL provider (NL2SQL_PROVIDER,
    defaulting to Anthropic) is ready to use. Otherwise, a short, safe,
    user-facing message explaining what's missing -- names a missing
    setting (an env var, a required model), never a credential value.
    Callers (the dashboard) use this to show a configuration message
    instead of letting a question fail after the fact."""
    try:
        get_sql_generation_provider()
    except ProviderConfigurationError as exc:
        return str(exc)
    return None


def generate_sql(
    question: str,
    schema_context: str,
    *,
    provider: Optional[SQLGenerationProvider] = None,
) -> SQLGenerationResult:
    """Generates one candidate SQL query for `question` against the given
    schema context, via the given provider or (by default) whichever
    provider NL2SQL_PROVIDER selects. Does not execute or validate the
    SQL beyond the guaranteed response shape -- the caller decides what
    to do with it."""
    provider = provider or get_sql_generation_provider()
    return provider.generate(question, schema_context)
