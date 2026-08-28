"""Google Gemini provider -- the preferred free-tier cloud option.

Talks to the Gemini REST API directly over `requests` rather than the
`google-genai` SDK: the request is one JSON POST with structured-output
support built in (`responseSchema`), so a whole SDK dependency isn't
needed for it -- consistent with this project's "no dependency without
a concrete need" convention (see requirements.txt).

Request/response shape and auth (API key in the `x-goog-api-key`
header, not the URL, so it can never end up in a logged request line)
verified against Google's current official documentation
(ai.google.dev) before writing this, not assumed from memory.

Optional: only required when NL2SQL_PROVIDER=gemini. Never imported or
constructed when another provider is selected.
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

# Google's own rolling alias for its current recommended flash-tier
# model, rather than a dated version string -- confirmed to exist via a
# live ListModels call against the real API before picking it (an
# earlier choice, "gemini-2.0-flash", had already been fully retired by
# the time this was verified, which is exactly the failure mode a fixed
# version string invites). Override with NL2SQL_MODEL for a pinned
# version instead; see ai.google.dev/gemini-api/docs/models.
DEFAULT_MODEL = "gemini-flash-latest"

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT_SECONDS = 30

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "explanation": {"type": "string"},
        "tables_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sql", "explanation", "tables_used"],
}


class GeminiProvider(SQLGenerationProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is not set. Get a free-tier key at "
                "https://aistudio.google.com/apikey and set it in your .env file."
            )
        self._model = model or os.getenv("NL2SQL_MODEL") or DEFAULT_MODEL
        self._session = session or requests.Session()

    def generate(self, question: str, schema_context: str) -> SQLGenerationResult:
        url = f"{_API_BASE}/models/{self._model}:generateContent"
        payload = {
            "systemInstruction": {"parts": {"text": build_system_prompt(schema_context)}},
            "contents": [{"role": "user", "parts": [{"text": question}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
            },
        }
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

        try:
            response = self._session.post(url, headers=headers, json=payload, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise ProviderRequestError(f"Gemini request failed: {exc}") from exc

        return parse_json_response(text)
