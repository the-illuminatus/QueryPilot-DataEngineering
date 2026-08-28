"""Ollama provider -- fully local, no cloud API key, no cost.

Talks to a locally running Ollama server's `/api/chat` endpoint over
`requests` (structured output via Ollama's `format` JSON-schema field,
`stream: false` for a single response). Shape verified against
Ollama's current official API docs before writing this.

Unlike the cloud providers, there is no sane default model to fall
back to -- whatever's "installed" is entirely up to what the user has
pulled locally, and guessing wrong would silently fail. NL2SQL_MODEL is
therefore required, not defaulted, when this provider is selected.

Optional: only required when NL2SQL_PROVIDER=ollama. Never imported or
constructed when another provider is selected -- and never requires
Ollama to be running for anyone using a different provider.
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

_DEFAULT_BASE_URL = "http://localhost:11434"
_TIMEOUT_SECONDS = 60  # local model inference can be slow, especially on first load

_FORMAT_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "explanation": {"type": "string"},
        "tables_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sql", "explanation", "tables_used"],
}


class OllamaProvider(SQLGenerationProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self._model = model or os.getenv("NL2SQL_MODEL")
        if not self._model:
            raise ProviderConfigurationError(
                "NL2SQL_MODEL is not set. Ollama requires an explicit local model name "
                "(e.g. 'llama3.1') matching a model you've already pulled ('ollama pull "
                "<model>') -- set NL2SQL_MODEL in your .env file."
            )
        self._session = session or requests.Session()

    def generate(self, question: str, schema_context: str) -> SQLGenerationResult:
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": build_system_prompt(schema_context)},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "format": _FORMAT_SCHEMA,
        }

        try:
            response = self._session.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
        except requests.exceptions.ConnectionError as exc:
            raise ProviderConfigurationError(
                f"Could not reach Ollama at {self._base_url}. Is it running locally? "
                "Start it with `ollama serve`, or set OLLAMA_BASE_URL if it's elsewhere."
            ) from exc
        except requests.RequestException as exc:
            raise ProviderRequestError(f"Ollama request failed: {exc}") from exc

        try:
            response.raise_for_status()
            data = response.json()
            text = data["message"]["content"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise ProviderRequestError(f"Ollama request failed: {exc}") from exc

        return parse_json_response(text)
