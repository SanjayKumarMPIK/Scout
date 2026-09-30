"""API-based vision provider."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Any

from scout.core.auth import get_api_key
from scout.vision.provider import VisionProvider


class APIVisionProvider(VisionProvider):
    """Vision provider using a cloud API (e.g., OpenAI, Groq, Gemini)."""

    def __init__(self, provider_name: str, model: str):
        super().__init__(provider_name, model)
        
        # Configure endpoint based on the selected provider
        self.provider_name = provider_name
        self.endpoint = ""
        self.auth_type = "Bearer"
        self.query_key = False
        
        if provider_name == "openai":
            self.endpoint = "https://api.openai.com/v1/chat/completions"
        elif provider_name == "groq":
            self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
        elif provider_name == "gemini":
            self.endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        elif provider_name == "anthropic":
            # Will use Claude 3.5 Sonnet Vision if configured, but via messages API
            self.endpoint = "https://api.anthropic.com/v1/messages"
        elif provider_name == "openrouter":
            self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        else:
            # Fallback/Custom
            self.endpoint = "http://localhost:11434/v1/chat/completions"

    def _get_headers(self, key: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Scout/1.0",
        }
        if not self.query_key:
            if self.provider_name == "anthropic":
                headers["x-api-key"] = key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {key}"
        return headers

    def _get_url(self, key: str) -> str:
        if self.query_key:
            return f"{self.endpoint}?key={key}"
        return self.endpoint

    def analyze(self, image_path: str, instruction: str) -> dict:
        """Send an image + instruction to the API vision model."""
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return {"success": False, "observation": f"Failed to read image: {e}", "raw": ""}

        key = get_api_key("vision") or get_api_key(self.provider_name)
        if not key and self.provider_name != "custom":
            return {"success": False, "observation": f"No API key stored for {self.provider_name} or dedicated vision.", "raw": ""}

        payload: dict[str, Any] = {}
        
        if self.provider_name == "anthropic":
            # Anthropic formatting
            import mimetypes
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                mime_type = "image/png"
                
            payload = {
                "model": self.model,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                            {"type": "text", "text": instruction}
                        ]
                    }
                ]
            }
        else:
            # OpenAI / Universal formatting
            mime_type = "image/png"
            if image_path.endswith(".jpeg") or image_path.endswith(".jpg"):
                mime_type = "image/jpeg"
                
            payload = {
                "model": self.model,
                "max_tokens": 500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruction},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}}
                        ]
                    }
                ]
            }

        try:
            data = json.dumps(payload).encode("utf-8")
            url = self._get_url(key or "")
            headers = self._get_headers(key or "")
            
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
                
                # Parse response
                if self.provider_name == "anthropic":
                    text = "".join(c.get("text", "") for c in body.get("content", []) if c.get("type") == "text")
                else:
                    text = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                return {
                    "success": True,
                    "observation": text,
                    "raw": text,
                }
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8")
            return {"success": False, "observation": f"API Error ({e.code}): {err}", "raw": ""}
        except Exception as e:
            return {"success": False, "observation": f"Vision analysis failed: {e}", "raw": ""}

    def test_connection(self) -> tuple[bool, str]:
        """Test if the API vision model is available by querying models endpoint if possible, or just checking key."""
        key = get_api_key("vision") or get_api_key(self.provider_name)
        if not key:
            return False, f"No API key stored for {self.provider_name} or dedicated vision"
            
        return True, f"API configured for {self.provider_name} ({self.model})"
