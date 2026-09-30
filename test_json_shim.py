import json
from scout.ai.interpreter import AIInterpreter
from scout.ai.tools import get_tools

# We need to mock user confirmation to always say "y" to avoid blocking
import builtins
class MockConfirm:
    @staticmethod
    def ask(*args, **kwargs):
        return True
import scout.ai.interpreter
scout.ai.interpreter.Confirm = MockConfirm

class MockProvider:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0
    def chat_completion(self, system, messages, tools=None):
        res = self.responses[self.call_count]
        self.call_count += 1
        return {'choices': [{'message': res}]}

# Test 1: Single tool call
print('\n--- TEST 1: Single tool call ---')
provider = MockProvider([
    {'content': '{"name": "open_url", "arguments": {"url": "https://youtube.com"}}'},
    {'content': 'Done.', 'tool_calls': []}
])
interpreter = AIInterpreter(provider)
interpreter.ask('test single')

# Test 2: Multiple consecutive JSON objects
print('\n--- TEST 2: Multiple tool calls ---')
provider = MockProvider([
    {'content': '{"name":"activate_window","arguments":{"title":"YouTube"}}\n{"name":"type_text","arguments":{"text":"rice and ginger"}}\n{"name":"press_key","arguments":{"key":"enter"}}'},
    {'content': 'Done typing.', 'tool_calls': []}
])
interpreter = AIInterpreter(provider)
interpreter.ask('test multiple')

# Test 3: Normal text response
print('\n--- TEST 3: Text response ---')
provider = MockProvider([
    {'content': 'Hello! I am a normal text response.', 'tool_calls': []}
])
interpreter = AIInterpreter(provider)
interpreter.ask('test text')
