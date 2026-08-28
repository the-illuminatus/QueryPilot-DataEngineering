"""Anthropic Claude provider -- the original (Phase 7B) implementation,
moved behind the SQLGenerationProvider interface with no behavioral
change: same model default, same structured-output mechanism
(`messages.parse(output_format=...)`), same system prompt content (now
shared via providers.base, byte-identical).

Optional: only required when NL2SQL_PROVIDER=anthropic (or left unset,
the default -- see providers/__init__.py). Never imported or
constructed when another provider is selected.
"""

import os
from typing import Optional

import anthropic

from .base import (
    ProviderConfigurationError,
    ProviderRequestError,
    SQLGenerationProvider,
    SQLGenerationResult,
    build_system_prompt,
)

DEFAULT_MODEL = "claude-opus-5"
_MAX_TOKENS = 2048


class AnthropicProvider(SQLGenerationProvider):
    def __init__(self, model: Optional[str] = None, client: Optional[anthropic.Anthropic] = None):
        # Only enforced when we'd construct our own client from env --
        # an explicitly injected `client` (tests, or a caller with its
        # own auth setup) is trusted as-is, exactly like the original
        # generate_sql(client=...) parameter worked.
        if client is None and not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise ProviderConfigurationError(
                "ANTHROPIC_API_KEY is not set. Set it in your .env file, or set "
                "NL2SQL_PROVIDER to 'gemini' or 'ollama' to avoid needing a Claude API key."
            )
        self._model = model or os.getenv("NL2SQL_MODEL") or DEFAULT_MODEL
        self._client = client or anthropic.Anthropic()

    def generate(self, question: str, schema_context: str) -> SQLGenerationResult:
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=build_system_prompt(schema_context),
                messages=[{"role": "user", "content": question}],
                output_format=SQLGenerationResult,
            )
        except Exception as exc:  # noqa: BLE001 - normalized into one provider-error type
            raise ProviderRequestError(f"Anthropic request failed: {exc}") from exc
        return response.parsed_output
