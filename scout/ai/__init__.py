"""Scout AI interpretation package."""

from __future__ import annotations

from scout.ai.provider import AIProvider
from scout.ai.providers.groq import GroqProvider
from scout.ai.providers.ollama import OllamaProvider

def get_provider(config: dict) -> AIProvider:
    """Return an instantiated AI provider based on configuration."""
    ai_config = config.get("ai", {})
    provider_name = ai_config.get("provider", "groq").lower()
    model = ai_config.get("model", "")
    
    if provider_name == "ollama":
        from scout.ai.providers.ollama import OllamaProvider
        return OllamaProvider(model or "qwen2.5-coder:7b")
    elif provider_name == "groq":
        from scout.ai.providers.groq import GroqProvider
        return GroqProvider(model or "llama-3.1-70b-versatile")
    elif provider_name == "openai":
        from scout.ai.providers.openai import OpenAIProvider
        return OpenAIProvider(model or "gpt-4o")
    elif provider_name == "gemini":
        from scout.ai.providers.gemini import GeminiProvider
        return GeminiProvider(model or "gemini-3.5-flash")
    elif provider_name == "anthropic":
        from scout.ai.providers.anthropic import AnthropicProvider
        return AnthropicProvider(model or "claude-3-5-sonnet-20240620")
    elif provider_name == "openrouter":
        from scout.ai.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(model or "anthropic/claude-3.5-sonnet")
    elif provider_name == "custom":
        from scout.ai.providers.custom import CustomProvider
        endpoint = ai_config.get("endpoint", "")
        return CustomProvider(model, endpoint)
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")
