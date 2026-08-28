"""Provider selection for src/nl2sql's SQL-generation layer.

`get_sql_generation_provider()` is the single place NL2SQL_PROVIDER is
read and turned into a concrete provider. Nothing outside this module
(generation.py, the dashboard) should branch on provider name -- they
call get_sql_generation_provider() (indirectly, via generate_sql()) and
get back something implementing SQLGenerationProvider, full stop.

Each concrete provider module is imported lazily, inside its branch --
so selecting "gemini" never imports the `anthropic` package (or vice
versa), and a provider's own optional dependencies (none currently; all
four are covered by this project's existing requirements.txt) stay
scoped to when that provider is actually selected.
"""

import os
from typing import Optional

from .base import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRequestError,
    SQLGenerationProvider,
    SQLGenerationResult,
    build_system_prompt,
    parse_json_response,
)

SUPPORTED_PROVIDERS = ("anthropic", "gemini", "ollama", "openrouter")

# Unset NL2SQL_PROVIDER keeps today's behavior (Anthropic) so existing
# .env setups with only ANTHROPIC_API_KEY continue working unchanged.
# New setups are expected to set NL2SQL_PROVIDER explicitly -- see
# .env.example, which documents gemini/ollama as the no-paid-key options.
_DEFAULT_PROVIDER = "anthropic"


def get_sql_generation_provider(provider_name: Optional[str] = None) -> SQLGenerationProvider:
    """Builds the SQL-generation provider named by `provider_name`, or
    by NL2SQL_PROVIDER, or the default ("anthropic") if neither is set.
    Raises ProviderConfigurationError -- never a bare KeyError/ValueError
    -- for both an unsupported provider name and a supported provider
    that's missing its own required configuration (API key, model)."""
    name = (provider_name or os.getenv("NL2SQL_PROVIDER") or _DEFAULT_PROVIDER).strip().lower()

    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider()
    if name == "ollama":
        from .ollama import OllamaProvider

        return OllamaProvider()
    if name == "openrouter":
        from .openrouter import OpenRouterProvider

        return OpenRouterProvider()

    raise ProviderConfigurationError(
        f"Unsupported NL2SQL_PROVIDER '{name}'. Supported values: {', '.join(SUPPORTED_PROVIDERS)}."
    )


__all__ = [
    "get_sql_generation_provider",
    "SUPPORTED_PROVIDERS",
    "SQLGenerationProvider",
    "SQLGenerationResult",
    "ProviderError",
    "ProviderConfigurationError",
    "ProviderRequestError",
    "build_system_prompt",
    "parse_json_response",
]
