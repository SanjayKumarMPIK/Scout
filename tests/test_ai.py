import pytest
from scout.ai.provider import AIProvider

class MockProvider(AIProvider):
    def __init__(self, responses):
        super().__init__("mock", "test-model")
        self.responses = responses
        self.calls = []

    def chat_completion(self, system_prompt: str, messages: list[dict], tools: list[dict] = None) -> dict:
        self.calls.append({"prompt": system_prompt, "messages": messages})
        if self.responses:
            return self.responses.pop(0)
        return {"choices": [{"message": {"content": "Mock complete."}}]}

    def test_connection(self) -> tuple[bool, str]:
        return True, "Mock OK"

def test_mock_provider():
    provider = MockProvider([
        {"choices": [{"message": {"content": "test"}}]}
    ])
    assert provider.chat_completion("", [])["choices"][0]["message"]["content"] == "test"
