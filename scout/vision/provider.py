"""Vision provider abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod


class VisionProvider(ABC):
    """Abstract base class for vision providers."""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    @abstractmethod
    def analyze(self, image_path: str, instruction: str) -> dict:
        """Analyze an image with a given instruction.
        
        Args:
            image_path: Absolute path to the image file.
            instruction: What to look for / describe.
            
        Returns:
            dict with:
                success: bool
                observation: str (what the model sees)
                raw: str (raw model response)
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test if the vision provider is reachable.
        Returns (success, message).
        """
        pass

    def is_available(self) -> bool:
        """Check if this vision provider is usable."""
        ok, _ = self.test_connection()
        return ok
