"""Core vision system entry point."""

from __future__ import annotations

from typing import Any

from scout.user_config import load_config
from scout.vision.provider import VisionProvider
from scout.vision.providers.api import APIVisionProvider
from scout.vision.providers.ollama import OllamaVisionProvider


def get_vision_provider(config: dict[str, Any] | None = None) -> VisionProvider | None:
    """Get the configured vision provider, or None if disabled/unconfigured.
    
    If no separate vision provider is configured, it falls back to trying to use 
    the main AI provider if it supports vision.
    """
    if config is None:
        config = load_config()

    vision_config = config.get("vision", {})
    provider_name = vision_config.get("provider", "").lower()
    model = vision_config.get("model", "")

    # If the user explicitly configured a vision provider
    if provider_name == "ollama":
        return OllamaVisionProvider(model or "qwen2.5-vl:3b")
    elif provider_name in ["openai", "groq", "gemini", "anthropic", "openrouter"]:
        return APIVisionProvider(provider_name, model)
        
    # If no explicit vision config, fallback to the main AI config if it supports vision
    ai_config = config.get("ai", {})
    ai_prov = ai_config.get("provider", "").lower()
    ai_model = ai_config.get("model", "")
    
    # Check if the main model is known to be vision-capable
    vision_capable_models = [
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision-preview",
        "gemini-1.5-pro", "gemini-1.5-flash",
        "claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307",
        "llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview"
    ]
    
    # Partial matching for Groq / OpenAI version suffixes
    is_vision = False
    for vcm in vision_capable_models:
        if vcm in ai_model.lower():
            is_vision = True
            break
            
    if is_vision and ai_prov in ["openai", "groq", "gemini", "anthropic", "openrouter"]:
        return APIVisionProvider(ai_prov, ai_model)
        
    return None
