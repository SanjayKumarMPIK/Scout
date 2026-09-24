"""AI Provider abstraction layer. Defines the interface for all AI backends."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract base class for all AI providers (Groq, Ollama, etc.)."""

    def __init__(self, model: str, api_key_env: str = ""):
        self.model = model
        self.api_key_env = api_key_env

    def get_api_key(self) -> str:
        """Resolve the API key from the environment securely."""
        if not self.api_key_env:
            return ""
        key = os.environ.get(self.api_key_env, "")
        return key

    @abstractmethod
    def generate_plan(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Generate a response (should be JSON) from the AI.
        
        Args:
            system_prompt: The overarching instructions for the AI.
            messages: A list of dicts like `[{"role": "user", "content": "..."}]` 
                      representing the conversation history.
                      
        Returns:
            The raw string response from the AI.
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test if the provider is reachable and configured correctly.
        Returns (success, message).
        """
        pass
