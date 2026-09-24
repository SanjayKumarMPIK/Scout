"""Ollama AI provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class OllamaProvider(AIProvider):
    """Provider for local Ollama."""

    def __init__(self, model: str, api_key_env: str = ""):
        super().__init__(model, api_key_env)
        self.endpoint = "http://localhost:11434/api/chat"

    def _make_request(self, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Ollama API Error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to Ollama: {e.reason} (Is Ollama running?)")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Ollama: {str(e)}")

    def generate_plan(self, system_prompt: str, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ] + messages,
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
            "format": "json",
        }

        res = self._make_request(payload)
        try:
            return res["message"]["content"]
        except KeyError:
            raise RuntimeError(f"Unexpected response format from Ollama: {res}")

    def test_connection(self) -> tuple[bool, str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": False,
        }
        try:
            self._make_request(payload)
            return True, f"Connected to Ollama successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
