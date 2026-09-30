import json
from scout.ai.interpreter import AIInterpreter

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
        if self.call_count < len(self.responses):
            res = self.responses[self.call_count]
            self.call_count += 1
        else:
            res = {'content': 'End'}
        return {'choices': [{'message': res}]}

# Test 6: External tool name format
print('\n--- TEST 6: External tool name format ---')
provider = MockProvider([
    {
        'content': '''Scout:
I'll save it for you.

press_key
{"key":"ctrl+s"}

complete_task
{"response":"The user interrupted the save operation."}
'''
    },
    {'content': '{"name": "complete_task", "arguments": {"response": "Done."}}'}
])
interpreter = AIInterpreter(provider)
interpreter.ask('test external name format')
