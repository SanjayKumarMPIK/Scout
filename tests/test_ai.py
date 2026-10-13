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


def test_build_chat_history_with_tool_calls_and_memory():
    from scout.ai.orchestrator import build_chat_history

    messages = [
        {
            "role": "user",
            "content": "<relevant_memory>\nUser: Sanjay\n</relevant_memory>\n\nUSER REQUEST:\nrun internet speedtest\n\n(A planner produced a 1-step plan for this request. You will receive the steps one at a time.)",
        },
        {
            "role": "user",
            "content": "PLAN STEP 1/1: Run speedtest\nAllowed tools: run_command",
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "function": {"name": "run_command", "arguments": '{"command": "speedtest"}'}}],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "Download: 150 Mbps, Upload: 50 Mbps",
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_2", "function": {"name": "step_done", "arguments": '{"result": "Download: 150 Mbps, Upload: 50 Mbps"}'}}],
        },
        {
            "role": "user",
            "content": "The plan has finished. Step results:\n...\n\nNow call `complete_task`...",
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_3",
                "function": {
                    "name": "complete_task",
                    "arguments": '{"response": "Speedtest complete! Download: 150 Mbps, Upload: 50 Mbps."}',
                },
            }],
        },
        {
            "role": "tool",
            "tool_call_id": "call_3",
            "content": "Task completed successfully.",
        },
    ]

    history = build_chat_history(messages)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "run internet speedtest"}
    assert history[1] == {"role": "assistant", "content": "Speedtest complete! Download: 150 Mbps, Upload: 50 Mbps."}


def test_run_planned_turn_respond_mode_collapses():
    from unittest.mock import MagicMock
    from scout.ai.orchestrator import run_planned_turn
    from scout.ai.planner import Plan
    from scout.ai.interpreter import AIInterpreter

    mock_planner = MagicMock()
    mock_planner.generate_plan.return_value = Plan(mode="respond", response="I can browse the web!")

    mock_provider = MockProvider([])
    interpreter = AIInterpreter(mock_provider)

    run_planned_turn(interpreter, mock_planner, "Can you browse the web?")

    assert len(interpreter.messages) == 2
    assert interpreter.messages[0] == {"role": "user", "content": "Can you browse the web?"}
    assert interpreter.messages[1] == {"role": "assistant", "content": "I can browse the web!"}


def test_run_planned_turn_multi_turn_history():
    from unittest.mock import MagicMock
    from scout.ai.orchestrator import run_planned_turn
    from scout.ai.planner import Plan, PlanStep
    from scout.ai.interpreter import AIInterpreter, StepOutcome

    mock_planner = MagicMock()
    # Turn 1: execute plan
    mock_planner.generate_plan.side_effect = [
        Plan(mode="execute", steps=[PlanStep("Run speedtest", ["run_command"])]),
        # Turn 2: respond plan
        Plan(mode="respond", response="Yes, I have web browsing tools!"),
    ]

    mock_provider = MockProvider([])
    interpreter = AIInterpreter(mock_provider)
    interpreter.run_step = MagicMock(return_value=StepOutcome("done", "150 Mbps"))
    interpreter.finalize = MagicMock(return_value="Speedtest result: 150 Mbps.")

    # Turn 1: Speedtest
    run_planned_turn(interpreter, mock_planner, "check speed")
    assert len(interpreter.messages) == 2
    assert interpreter.messages[0] == {"role": "user", "content": "check speed"}
    assert interpreter.messages[1] == {"role": "assistant", "content": "Speedtest result: 150 Mbps."}

    # Turn 2: "Can you browse the web?"
    run_planned_turn(interpreter, mock_planner, "Can you browse the web?")
    
    # Check what chat_history was passed to planner in Turn 2
    second_call_args = mock_planner.generate_plan.call_args_list[1]
    passed_history = second_call_args.kwargs.get("chat_history")
    assert len(passed_history) == 2
    assert passed_history[0] == {"role": "user", "content": "check speed"}
    assert passed_history[1] == {"role": "assistant", "content": "Speedtest result: 150 Mbps."}

    # Interpreter messages now cleanly has both turns
    assert len(interpreter.messages) == 4
    assert interpreter.messages[2] == {"role": "user", "content": "Can you browse the web?"}
    assert interpreter.messages[3] == {"role": "assistant", "content": "Yes, I have web browsing tools!"}

