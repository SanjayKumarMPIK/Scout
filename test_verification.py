import json
from scout.ai.interpreter import AIInterpreter

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

print('\n--- TEST A: Simple open_url ---')
provider_A = MockProvider([
    {'content': '{"name": "open_url", "arguments": {"url": "https://youtube.com"}}'},
    {'content': '{"name": "complete_task", "arguments": {"response": "Opened URL."}}'}
])
interpreter_A = AIInterpreter(provider_A)
interpreter_A.ask('Open YouTube')

print('\n--- TEST B: Multiple sequential + premature complete ---')
provider_B = MockProvider([
    {'content': '{"name":"activate_window","arguments":{"title":"YouTube"}}\n{"name":"type_text","arguments":{"text":"rice"}}\n{"name":"complete_task","arguments":{"response":"Done"}}'},
    {'content': '{"name":"complete_task","arguments":{"response":"Now verified it is done."}}'}
])
interpreter_B = AIInterpreter(provider_B)
interpreter_B.ask('Search rice')

print('\n--- TEST C: Invalid tool_response ---')
provider_C = MockProvider([
    {'content': '<tool_response>ERROR</tool_response>'},
    {'content': '{"name": "complete_task", "arguments": {"response": "Fixed."}}'}
])
interpreter_C = AIInterpreter(provider_C)
interpreter_C.ask('Do it')
