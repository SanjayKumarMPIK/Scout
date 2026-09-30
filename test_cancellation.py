import json
from scout.ai.interpreter import AIInterpreter

# We mock Confirm to simulate a user pressing "no" during the second tool call.
import builtins
class MockConfirm:
    @staticmethod
    def ask(*args, **kwargs):
        # We will track calls globally in this simple script
        global tool_index
        tool_index += 1
        if tool_index == 2:
            return False # User cancels the second tool
        return True

import scout.ai.interpreter
scout.ai.interpreter.Confirm = MockConfirm
scout.ai.interpreter.SAFE.clear() # Make all tools require confirm for the test

class MockProvider:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0
    def chat_completion(self, system, messages, tools=None):
        if self.call_count < len(self.responses):
            res = self.responses[self.call_count]
            self.call_count += 1
        else:
            res = {'content': 'End of mock.'}
        return {'choices': [{'message': res}]}


print('\n--- TEST E: Repeated malformed <tool_response> ---')
provider_E = MockProvider([
    {'content': '<tool_response>ERROR</tool_response>'},
    {'content': '<tool_response>ERROR2</tool_response>'},
    {'content': '<tool_response>ERROR3</tool_response>'},
    {'content': 'Should never reach here'}
])
interpreter_E = AIInterpreter(provider_E)
interpreter_E.ask('Do it')


print('\n--- TEST F: User cancellation ---')
tool_index = 0
provider_F = MockProvider([
    {'content': '{"name":"activate_window","arguments":{"title":"YouTube"}}\n{"name":"type_text","arguments":{"text":"rice"}}\n{"name":"press_key","arguments":{"key":"enter"}}'},
    {'content': 'Model should not run again because loop exited'}
])
interpreter_F = AIInterpreter(provider_F)
interpreter_F.ask('Search rice')


print('\n--- TEST G: New request after cancellation ---')
# A completely fresh agent run
interpreter_F.messages.clear()
provider_G = MockProvider([
    {'content': '{"name": "complete_task", "arguments": {"response": "All good."}}'}
])
interpreter_F.provider = provider_G
interpreter_F.ask('Do a new thing')

