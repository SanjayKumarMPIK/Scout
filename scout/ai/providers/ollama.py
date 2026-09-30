"""Ollama AI provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class OllamaProvider(AIProvider):
    """Provider for local Ollama."""

    def __init__(self, model: str):
        super().__init__("ollama", model)
        self.endpoint = "http://localhost:11434/v1/chat/completions"

    def get_api_key(self) -> str:
        return ""

    def _make_request(self, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Ollama API Error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to Ollama: {e.reason} (Is Ollama running?)")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Ollama: {str(e)}")

    def chat_completion(self, system_prompt: str, messages: list[dict], tools: list[dict] = None) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ] + messages,
            "temperature": 0.0,
            "max_tokens": 500,
        }
        if tools:
            payload["tools"] = tools

        res = self._make_request(payload)
        
        # Fallback for models (like qwen) that output tool calls as JSON text instead of native tool_calls
        if "choices" in res and res["choices"]:
            msg = res["choices"][0].get("message", {})
            content = msg.get("content", "")
            if not msg.get("tool_calls") and content:
                import re
                
                tool_calls = []
                cleaned_content = content
                
                # First, check if there's a JSON array of tool calls.
                array_match = re.search(r'\[\s*\{.*"name"\s*:\s*".*".*\}\s*\]', content, re.DOTALL)
                if array_match:
                    try:
                        raw_json = array_match.group(0)
                        parsed = json.loads(raw_json)
                        if isinstance(parsed, list):
                            for idx, p in enumerate(parsed):
                                if isinstance(p, dict) and "name" in p and "arguments" in p:
                                    tool_calls.append({
                                        "id": f"call_ollama_fallback_{idx}",
                                        "type": "function",
                                        "function": {
                                            "name": p["name"],
                                            "arguments": json.dumps(p["arguments"]) if isinstance(p["arguments"], dict) else p["arguments"]
                                        }
                                    })
                            if tool_calls:
                                cleaned_content = content.replace(raw_json, "").strip()
                    except Exception:
                        pass
                
                # If no array found, extract individual JSON objects robustly
                if not tool_calls:
                    idx = 0
                    for match in re.finditer(r'\{\s*"name"\s*:', content):
                        start = match.start()
                        brace_count = 0
                        in_string = False
                        escape = False
                        
                        for i in range(start, len(content)):
                            c = content[i]
                            if not escape:
                                if c == '"':
                                    in_string = not in_string
                                elif not in_string:
                                    if c == '{':
                                        brace_count += 1
                                    elif c == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            raw_json = content[start:i+1]
                                            try:
                                                p = json.loads(raw_json)
                                                if "name" in p and "arguments" in p:
                                                    tool_calls.append({
                                                        "id": f"call_ollama_fallback_{idx}",
                                                        "type": "function",
                                                        "function": {
                                                            "name": p["name"],
                                                            "arguments": json.dumps(p["arguments"]) if isinstance(p["arguments"], dict) else p["arguments"]
                                                        }
                                                    })
                                                    idx += 1
                                                    cleaned_content = cleaned_content.replace(raw_json, "")
                                            except Exception:
                                                pass
                                            break
                            if c == '\\' and not escape:
                                escape = True
                            else:
                                escape = False

                if tool_calls:
                    msg["tool_calls"] = tool_calls
                    msg["content"] = cleaned_content.strip()
                    
        return res
    def test_connection(self) -> tuple[bool, str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10,
        }
        try:
            self._make_request(payload)
            return True, f"Connected to Ollama successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
