"""OpenAI provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class OpenAIProvider(AIProvider):
    """Provider for OpenAI."""

    def __init__(self, model: str):
        super().__init__("openai", model)
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def _make_request(self, payload: dict) -> dict:
        key = self.get_api_key()

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
            raise RuntimeError(f"OpenAI API Error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to OpenAI: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with OpenAI: {str(e)}")

    def chat_completion(self, system_prompt: str, messages: list[dict], tools: list[dict] = None) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ] + messages,
            "temperature": 0.0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        return self._make_request(payload)

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.get_api_key()
        except ValueError as e:
            return False, str(e)

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        try:
            self._make_request(payload)
            return True, f"Connected to OpenAI successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
