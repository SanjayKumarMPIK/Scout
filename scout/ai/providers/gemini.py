"""Google Gemini provider implementation using OpenAI compatibility endpoint."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class GeminiProvider(AIProvider):
    """Provider for Google Gemini."""

    def __init__(self, model: str):
        super().__init__("gemini", model)
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    def _make_request(self, payload: dict, max_retries: int = 2) -> dict:
        import time
        from rich.console import Console
        console = Console()
        key = self.get_api_key()

        attempt = 0
        while attempt <= max_retries:
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
                with urllib.request.urlopen(req, timeout=60) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                
                # 503 is High Demand, 429 is Rate Limit
                if e.code in (503, 429):
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        attempt += 1
                        continue
                    else:
                        current_model = payload.get("model", "")
                        if current_model != "gemini-3.8-flash":
                            fallback = "gemini-3.8-flash"
                        elif current_model != "gemini-3.8-flash-lite":
                            fallback = "gemini-3.8-flash-lite"
                        else:
                            raise RuntimeError(f"Gemini API Error ({e.code}): {error_body}")
                            
                        console.print(f"\n[yellow]Gemini model '{current_model}' is overloaded (503/429). Falling back to {fallback}...[/yellow]")
                        payload["model"] = fallback
                        attempt = 0  # Reset retries for the new model
                        continue
                raise RuntimeError(f"Gemini API Error ({e.code}): {error_body}")
            except urllib.error.URLError as e:
                if attempt < max_retries:
                    time.sleep(2)
                    attempt += 1
                    continue
                raise RuntimeError(f"Network error connecting to Gemini: {e.reason}")
            except Exception as e:
                raise RuntimeError(f"Unexpected error communicating with Gemini: {str(e)}")

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
            return True, f"Connected to Gemini successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
