"""Groq AI provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class GroqProvider(AIProvider):
    """Provider for Groq's fast API, using OpenAI's compatibility endpoint."""

    def __init__(self, model: str):
        super().__init__("groq", model)
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

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
            raise RuntimeError(f"Groq API Error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to Groq: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Groq: {str(e)}")

    def _make_request_with_retry(self, payload: dict) -> dict:
        import time
        max_retries = 4
        for attempt in range(max_retries):
            try:
                return self._make_request(payload)
            except RuntimeError as e:
                if "429" in str(e):
                    if attempt < max_retries - 1:
                        backoff = 5 * (attempt + 1)  # 5, 10, 15
                        print(f"[dim]Groq 429 Rate Limit. Retrying in {backoff}s...[/dim]")
                        time.sleep(backoff)
                        continue
                raise

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

        res = self._make_request_with_retry(payload)
        return res

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
            return True, f"Connected to Groq successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
