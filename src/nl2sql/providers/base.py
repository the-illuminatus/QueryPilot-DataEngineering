"""The provider contract every LLM backend implements, plus everything
shared across providers: the result type, the system prompt, exception
types, and a small JSON-response helper.

Nothing in this file talks to a network. It exists so
src/nl2sql/generation.py and every concrete provider
(anthropic_provider.py, gemini.py, ollama.py, openrouter.py) depend on
one small, stable surface instead of on each other -- dependency
inversion: generation.py depends on this abstraction, concrete
providers depend on this abstraction, and none of the providers know
about each other or about generation.py.
"""

import json
from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel, Field, ValidationError


class SQLGenerationResult(BaseModel):
    sql: str = Field(
        description=(
            "A single PostgreSQL SELECT statement answering the question, "
            "using only tables/columns from the given schema. Empty string "
            "if the question cannot be answered from that schema."
        )
    )
    explanation: str = Field(
        description=(
            "A brief explanation of what the query does, or a brief "
            "explanation of why the question could not be answered."
        )
    )
    tables_used: List[str] = Field(
        description="Schema table names referenced by the generated SQL."
    )


class ProviderError(Exception):
    """Base class for every provider-layer failure."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is missing required configuration (an API
    key, a required model name, an unreachable local service). Always a
    static, safe message naming the missing setting -- never an actual
    credential value. Callers (generation.py's get_configuration_error(),
    the dashboard) treat this as "not ready yet", not a crash."""


class ProviderRequestError(ProviderError):
    """Raised when a provider's backend call itself failed (network
    error, non-2xx response, a response that didn't match the expected
    shape). Distinct from ProviderConfigurationError so tests and logs
    can tell "you haven't set this up" apart from "the request failed
    once you did"."""


# Identical across providers on purpose: every provider must ground its
# SQL in the same schema and the same read-only rules, so switching
# NL2SQL_PROVIDER never changes what's allowed -- only who answers.
_SYSTEM_PROMPT_TEMPLATE = """You are a PostgreSQL SQL generation assistant for the QueryPilot data \
warehouse. You are given the warehouse's schema and a natural-language \
question. Generate a single candidate SQL query that answers the question.

Rules:
- Write standard PostgreSQL syntax.
- The query must be read-only: SELECT (optionally with CTEs/WITH) only. \
Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, \
GRANT, or any other statement that could modify data or schema.
- Use only the tables and columns listed in the schema below. Never \
invent a table or column name that is not present in it.
- Use table and column names exactly as given, including case.
- Respect the relationships (foreign keys) given when joining tables.
- If the question cannot be answered using only the schema given -- it \
references information the schema does not contain, or it is too \
ambiguous to translate -- set "sql" to an empty string and use \
"explanation" to say why, instead of guessing.
- "tables_used" must list exactly the schema tables your SQL references \
(empty if "sql" is empty).

Respond with a JSON object with exactly these fields: "sql" (string), \
"explanation" (string), "tables_used" (array of strings). No other text.

Schema:
{schema_context}
"""


def build_system_prompt(schema_context: str) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(schema_context=schema_context)


def parse_json_response(text: str) -> SQLGenerationResult:
    """Shared by every REST-based provider (Gemini/Ollama/OpenRouter):
    turns the raw text a provider returned into a SQLGenerationResult,
    raising ProviderRequestError with a safe message (never the raw
    provider payload verbatim beyond the parse-error description) if
    the text isn't valid JSON or doesn't match the expected shape."""
    try:
        data = json.loads(text)
        return SQLGenerationResult(**data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ProviderRequestError(f"Provider response was not valid structured JSON: {exc}") from exc


class SQLGenerationProvider(ABC):
    """generate(question, schema_context) -> SQLGenerationResult is the
    entire contract. Nothing about validation, execution, or the
    warehouse -- a provider's only responsibility is producing a
    candidate SQLGenerationResult; SQL safety is validate_sql()'s job,
    entirely outside this abstraction."""

    @abstractmethod
    def generate(self, question: str, schema_context: str) -> SQLGenerationResult:
        raise NotImplementedError
