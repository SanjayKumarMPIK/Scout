"""Scout AI interpretation package."""

from __future__ import annotations

from scout.ai.provider import AIProvider
from scout.ai.providers.groq import GroqProvider
from scout.ai.providers.ollama import OllamaProvider

def get_provider(config: dict) -> AIProvider:
    """Return an instantiated AI provider based on configuration."""
    ai_config = config.get("ai", {})
    provider_name = ai_config.get("provider", "groq").lower()
    model = ai_config.get("model", "openai/gpt-oss-120b")
    api_key_env = ai_config.get("api_key_env", "SCOUT_GROQ_API_KEY")

    if provider_name == "groq":
        return GroqProvider(model, api_key_env)
    elif provider_name == "ollama":
        return OllamaProvider(model, api_key_env)
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")
