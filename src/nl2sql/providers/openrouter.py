"""OpenRouter provider -- OpenAI-compatible chat-completions API,
giving access to many providers (including free-tier models) through
one key. Turned out low-complexity to add via plain `requests` (same
pattern as gemini.py/ollama.py), so it's implemented rather than
deferred.

Request/response shape and structured-output mechanism
(`response_format.json_schema`, strict mode) verified against
OpenRouter's current official documentation before writing this.

Not all models routed through OpenRouter honor `response_format`
equally well -- that's a model-choice concern, not something this
provider can paper over, which is why NL2SQL_MODEL is required rather
than defaulted (see __init__): a silently-guessed model could look
configured and then fail unpredictably at request time.

Optional: only required when NL2SQL_PROVIDER=openrouter. Never
imported or constructed when another provider is selected.
"""

import os
from typing import Optional

import requests

from .base import (
    ProviderConfigurationError,
    ProviderRequestError,
    SQLGenerationProvider,
    SQLGenerationResult,
    build_system_prompt,
    parse_json_response,
)

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT_SECONDS = 30

_STRICT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "explanation": {"type": "string"},
        "tables_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sql", "explanation", "tables_used"],
    "additionalProperties": False,
}


class OpenRouterProvider(SQLGenerationProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self._api_key:
            raise ProviderConfigurationError(
                "OPENROUTER_API_KEY is not set. Get a key at https://openrouter.ai/keys "
                "and set it in your .env file."
            )
        self._model = model or os.getenv("NL2SQL_MODEL")
        if not self._model:
            raise ProviderConfigurationError(
                "NL2SQL_MODEL is not set. OpenRouter requires an explicit model slug "
                "(e.g. 'meta-llama/llama-3.1-8b-instruct:free') -- see "
                "https://openrouter.ai/models -- set NL2SQL_MODEL in your .env file."
            )
        self._session = session or requests.Session()

    def generate(self, question: str, schema_context: str) -> SQLGenerationResult:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": build_system_prompt(schema_context)},
                {"role": "user", "content": question},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "sql_generation_result", "strict": True, "schema": _STRICT_JSON_SCHEMA},
            },
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        try:
            response = self._session.post(_API_URL, headers=headers, json=payload, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise ProviderRequestError(f"OpenRouter request failed: {exc}") from exc

        return parse_json_response(text)
