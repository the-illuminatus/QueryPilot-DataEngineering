"""Tests for provider selection (src/nl2sql/providers/__init__.py) and
the shared provider contract (src/nl2sql/providers/base.py).

No real network/API calls: provider *selection* only constructs a
provider (which validates its own configuration synchronously) and
never calls .generate(), so these tests never need real credentials --
only enough fake env vars to satisfy each provider's own config check.
"""

import pytest

from src.nl2sql.providers import SUPPORTED_PROVIDERS, get_sql_generation_provider
from src.nl2sql.providers.anthropic_provider import AnthropicProvider
from src.nl2sql.providers.base import (
    ProviderConfigurationError,
    SQLGenerationProvider,
    SQLGenerationResult,
)
from src.nl2sql.providers.gemini import GeminiProvider
from src.nl2sql.providers.ollama import OllamaProvider
from src.nl2sql.providers.openrouter import OpenRouterProvider


def _clear_all_provider_env(monkeypatch):
    for var in (
        "NL2SQL_PROVIDER",
        "NL2SQL_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "GEMINI_API_KEY",
        "OLLAMA_BASE_URL",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# The interface itself
# ---------------------------------------------------------------------------


def test_sql_generation_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        SQLGenerationProvider()  # abstract -- generate() has no implementation


def test_a_provider_missing_generate_cannot_be_instantiated():
    class Incomplete(SQLGenerationProvider):
        pass

    with pytest.raises(TypeError):
        Incomplete()


# ---------------------------------------------------------------------------
# Factory: selecting each provider
# ---------------------------------------------------------------------------


def test_factory_selects_gemini(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    provider = get_sql_generation_provider()

    assert isinstance(provider, GeminiProvider)


def test_factory_selects_ollama(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "ollama")
    monkeypatch.setenv("NL2SQL_MODEL", "llama3.1")

    provider = get_sql_generation_provider()

    assert isinstance(provider, OllamaProvider)


def test_factory_selects_anthropic(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")

    provider = get_sql_generation_provider()

    assert isinstance(provider, AnthropicProvider)


def test_factory_selects_openrouter(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setenv("NL2SQL_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

    provider = get_sql_generation_provider()

    assert isinstance(provider, OpenRouterProvider)


def test_factory_defaults_to_anthropic_when_unset(monkeypatch):
    """Backward compatibility: an existing .env with only
    ANTHROPIC_API_KEY set (no NL2SQL_PROVIDER at all) must keep working
    exactly as it did before providers existed."""
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")

    provider = get_sql_generation_provider()

    assert isinstance(provider, AnthropicProvider)


def test_factory_explicit_provider_name_overrides_env_var(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")

    provider = get_sql_generation_provider("anthropic")

    assert isinstance(provider, AnthropicProvider)


def test_factory_provider_name_is_case_and_whitespace_insensitive(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "  Gemini  ")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    provider = get_sql_generation_provider()

    assert isinstance(provider, GeminiProvider)


# ---------------------------------------------------------------------------
# Unsupported provider is rejected clearly and safely
# ---------------------------------------------------------------------------


def test_unsupported_provider_name_rejected_clearly(monkeypatch):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", "chatgpt")

    with pytest.raises(ProviderConfigurationError) as exc_info:
        get_sql_generation_provider()

    message = str(exc_info.value)
    assert "chatgpt" in message
    for name in SUPPORTED_PROVIDERS:
        assert name in message


# ---------------------------------------------------------------------------
# Each provider only requires its own credentials
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider_name", "required_env", "provider_cls"),
    [
        ("gemini", {"GEMINI_API_KEY": "fake-gemini-key"}, GeminiProvider),
        ("ollama", {"NL2SQL_MODEL": "llama3.1"}, OllamaProvider),
        ("anthropic", {"ANTHROPIC_API_KEY": "fake-anthropic-key"}, AnthropicProvider),
        (
            "openrouter",
            {"OPENROUTER_API_KEY": "fake-openrouter-key", "NL2SQL_MODEL": "some/model:free"},
            OpenRouterProvider,
        ),
    ],
)
def test_selected_provider_only_requires_its_own_credentials(monkeypatch, provider_name, required_env, provider_cls):
    """None of ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENROUTER_API_KEY is
    set except what this provider itself needs -- construction must
    still succeed, proving the factory never cross-checks another
    provider's config."""
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", provider_name)
    for key, value in required_env.items():
        monkeypatch.setenv(key, value)

    provider = get_sql_generation_provider()

    assert isinstance(provider, provider_cls)


@pytest.mark.parametrize(
    ("provider_name", "provider_cls"),
    [
        ("gemini", GeminiProvider),
        ("ollama", OllamaProvider),
        ("anthropic", AnthropicProvider),
        ("openrouter", OpenRouterProvider),
    ],
)
def test_provider_missing_its_own_config_raises_clearly(monkeypatch, provider_name, provider_cls):
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("NL2SQL_PROVIDER", provider_name)

    with pytest.raises(ProviderConfigurationError):
        get_sql_generation_provider()


# ---------------------------------------------------------------------------
# No credentials ever appear in configuration-error messages
# ---------------------------------------------------------------------------


def test_configuration_error_messages_never_echo_a_provided_credential_value(monkeypatch):
    """Every ProviderConfigurationError raised here is a "you're missing
    X" message about an *absent* setting -- confirms none of them
    accidentally interpolate an actual (fake, in this test) secret
    value some other env var holds."""
    _clear_all_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-appear-in-any-other-providers-error")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-should-never-appear-in-any-other-providers-error")

    monkeypatch.setenv("NL2SQL_PROVIDER", "ollama")  # missing NL2SQL_MODEL
    with pytest.raises(ProviderConfigurationError) as exc_info:
        get_sql_generation_provider()
    message = str(exc_info.value)
    assert "sk-ant-should-never-appear" not in message
    assert "gm-should-never-appear" not in message


# ---------------------------------------------------------------------------
# SQLGenerationResult is the shared contract, unchanged by provider choice
# ---------------------------------------------------------------------------


def test_sql_generation_result_shape_is_provider_independent():
    result = SQLGenerationResult(sql="SELECT 1", explanation="test", tables_used=["orders"])
    assert result.sql == "SELECT 1"
    assert result.explanation == "test"
    assert result.tables_used == ["orders"]
