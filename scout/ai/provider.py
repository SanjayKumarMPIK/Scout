"""AI Provider abstraction layer. Defines the interface for all AI backends."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract base class for all AI providers (Groq, Ollama, etc.)."""

    def __init__(self, name: str, model: str):
        self.name = name.lower()
        self.model = model

    def get_api_key(self) -> str:
        """Resolve the API key from secure storage."""
        from scout.core.auth import get_api_key
        key = get_api_key(self.name)
        if not key:
            raise ValueError(f"API key missing for provider '{self.name}'. Set it using '/provider key'.")
        return key

    @abstractmethod
    def chat_completion(self, system_prompt: str, messages: list[dict], tools: list[dict] = None) -> dict:
        """
        Generate a response using tool calling.
        
        Args:
            system_prompt: The overarching instructions for the AI.
            messages: Conversation history.
            tools: List of JSON schema tool definitions.
                      
        Returns:
            The raw dictionary response from the AI (matching OpenAI format).
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test if the provider is reachable and configured correctly.
        Returns (success, message).
        """
        pass
