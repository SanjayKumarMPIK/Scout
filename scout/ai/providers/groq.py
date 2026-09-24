"""Groq AI provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class GroqProvider(AIProvider):
    """Provider for Groq's fast API, using OpenAI's compatibility endpoint."""

    def __init__(self, model: str, api_key_env: str = "SCOUT_GROQ_API_KEY"):
        super().__init__(model, api_key_env)
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def _make_request(self, payload: dict) -> dict:
        key = self.get_api_key()
        if not key:
            raise ValueError(f"API key missing. Set {self.api_key_env} in your environment.")

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "Scout/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Groq API Error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to Groq: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Groq: {str(e)}")

    def generate_plan(self, system_prompt: str, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ] + messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        res = self._make_request(payload)
        try:
            return res["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected response format from Groq: {res}")

    def test_connection(self) -> tuple[bool, str]:
        if not self.get_api_key():
            return False, f"API key missing ({self.api_key_env} environment variable not set)"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        try:
            self._make_request(payload)
            return True, f"Connected to Groq successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
