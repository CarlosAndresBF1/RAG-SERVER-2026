"""LLM provider factory.

Selects and instantiates the configured LLM provider based on the
LLM_PROVIDER environment variable (settings.llm_provider).
"""

from __future__ import annotations

from odyssey_rag.config import Settings
from odyssey_rag.exceptions import ConfigError
from odyssey_rag.llm.provider import BaseLLMProvider


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    """Create and return the configured LLM provider.

    Provider selection via settings.llm_provider:
    - ``"openai"``    (default): GPT-4o, requires OPENAI_API_KEY.
    - ``"anthropic"``           : Claude, requires ANTHROPIC_API_KEY.
    - ``"gemini"``              : Gemini 2.5 Pro, requires GOOGLE_API_KEY.

    Args:
        settings: Application settings instance.

    Returns:
        Configured LLM provider instance.

    Raises:
        ConfigError: If the provider name is unknown or a required API key
            is missing.
    """
    provider_name = settings.llm_provider.lower()

    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ConfigError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        from odyssey_rag.llm.openai_provider import OpenAILLMProvider

        return OpenAILLMProvider(api_key=settings.openai_api_key)

    if provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            )
        from odyssey_rag.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider(api_key=settings.anthropic_api_key)

    if provider_name == "gemini":
        if not settings.google_api_key:
            raise ConfigError(
                "GOOGLE_API_KEY is required when LLM_PROVIDER=gemini"
            )
        from odyssey_rag.llm.gemini_provider import GeminiLLMProvider

        return GeminiLLMProvider(api_key=settings.google_api_key)

    raise ConfigError(
        f"Unknown LLM_PROVIDER: '{provider_name}'. "
        "Valid options: openai, anthropic, gemini"
    )
