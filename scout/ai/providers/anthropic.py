"""Anthropic provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scout.ai.provider import AIProvider


class AnthropicProvider(AIProvider):
    """Provider for Anthropic."""

    def __init__(self, model: str):
        super().__init__("anthropic", model)
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def _make_request(self, payload: dict) -> dict:
        key = self.get_api_key()

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
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
            raise RuntimeError(f"Anthropic API Error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to Anthropic: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with Anthropic: {str(e)}")

    def chat_completion(self, system_prompt: str, messages: list[dict], tools: list[dict] = None) -> dict:
        # Convert OpenAI tools schema to Anthropic tools schema
        anthropic_tools = []
        if tools:
            for t in tools:
                if t.get("type") == "function":
                    func = t["function"]
                    anthropic_tools.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {})
                    })

        # Convert OpenAI messages to Anthropic messages
        anthropic_msgs = []
        for msg in messages:
            if msg["role"] == "system":
                continue # handled separately
            if msg["role"] == "tool":
                # Anthropic expects 'user' role with 'tool_result' blocks
                anthropic_msgs.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content", "")
                    }]
                })
            elif msg["role"] == "assistant":
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        if tc.get("type") == "function":
                            args_str = tc["function"].get("arguments", "{}")
                            try:
                                args = json.loads(args_str)
                            except:
                                args = {}
                            content.append({
                                "type": "tool_use",
                                "id": tc.get("id", ""),
                                "name": tc["function"]["name"],
                                "input": args
                            })
                anthropic_msgs.append({
                    "role": "assistant",
                    "content": content
                })
            else:
                anthropic_msgs.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": anthropic_msgs,
            "max_tokens": 4096,
            "temperature": 0.0,
        }
        
        if anthropic_tools:
            payload["tools"] = anthropic_tools
            
        res = self._make_request(payload)
        
        # Convert Anthropic response back to OpenAI format
        choice = {"message": {"role": "assistant", "content": "", "tool_calls": []}}
        
        if "content" in res:
            for block in res["content"]:
                if block["type"] == "text":
                    choice["message"]["content"] += block["text"]
                elif block["type"] == "tool_use":
                    choice["message"]["tool_calls"].append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"])
                        }
                    })
        
        if not choice["message"]["tool_calls"]:
            del choice["message"]["tool_calls"]
            
        return {"choices": [choice]}

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
            return True, f"Connected to Anthropic successfully using model '{self.model}'"
        except Exception as e:
            return False, str(e)
