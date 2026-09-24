"""Tests for Phase 4: AI Agent interpretation and execution layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scout.ai.interpreter import _get_risk_level, AIInterpreter
from scout.ai.provider import AIProvider
from scout.ai.schemas import AIAction, AIPlan, parse_and_validate_plan


class MockProvider(AIProvider):
    def __init__(self, response_text: str | list[str] = ""):
        super().__init__("test-model")
        if isinstance(response_text, str):
            self.responses = [response_text, '{"message": "Done", "actions": []}']
        else:
            self.responses = list(response_text)
        self.calls = []

    def generate_plan(self, system_prompt: str, messages: list[dict]) -> str:
        self.calls.append({"prompt": system_prompt, "messages": messages})
        if self.responses:
            return self.responses.pop(0)
        return '{"message": "Done", "actions": []}'

    def test_connection(self) -> tuple[bool, str]:
        return True, "Mock OK"


# ── Schema Validation Tests ─────────────────────────────────────────────

def test_parse_valid_plan():
    json_str = """
    {
      "message": "I will open the project.",
      "actions": [
        {"type": "project_open", "project": "expense"},
        {"type": "wait", "seconds": 2}
      ]
    }
    """
    plan = parse_and_validate_plan(json_str)
    assert plan.message == "I will open the project."
    assert len(plan.actions) == 2
    assert plan.actions[0].action_type == "project_open"
    assert plan.actions[0].params["project"] == "expense"
    assert plan.actions[1].action_type == "wait"


def test_parse_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_and_validate_plan("{ bad json")


def test_parse_missing_message():
    json_str = '{"actions": []}'
    with pytest.raises(ValueError, match="message"):
        parse_and_validate_plan(json_str)


def test_parse_missing_actions():
    json_str = '{"message": "hi"}'
    with pytest.raises(ValueError, match="actions"):
        parse_and_validate_plan(json_str)


def test_parse_missing_required_params():
    json_str = '{"message": "hi", "actions": [{"type": "project_run", "project": "only"}]}'
    with pytest.raises(ValueError, match="requires 'project' and 'command'"):
        parse_and_validate_plan(json_str)


# ── Risk Level Tests ───────────────────────────────────────────────────

def test_risk_levels():
    assert _get_risk_level("system_info") == "SAFE"
    assert _get_risk_level("git_status") == "SAFE"
    assert _get_risk_level("run_command") == "CONFIRM"
    assert _get_risk_level("git_commit") == "CONFIRM"
    assert _get_risk_level("git_push") == "HIGH_RISK"
    assert _get_risk_level("made_up_action") == "CONFIRM"


# ── Interpreter Loop Tests ─────────────────────────────────────────────

@patch("scout.ai.interpreter.Confirm.ask")
@patch("scout.ai.interpreter.execute_step")
def test_interpreter_safe_action(mock_exec, mock_confirm):
    # SAFE actions don't prompt for confirmation
    provider = MockProvider('{"message": "Info", "actions": [{"type": "system_info"}]}')
    interpreter = AIInterpreter(provider)
    
    from scout.workflow.actions import StepResult
    mock_exec.return_value = StepResult(True, "OK")
    
    interpreter.ask("check system")
    
    assert mock_confirm.call_count == 0
    # Provider called twice: once for initial request, once for synthesizing results
    assert len(provider.calls) == 2
    assert "Result of system_info: SUCCESS" in interpreter.messages[-2]["content"]


@patch("scout.ai.interpreter.Confirm.ask")
@patch("scout.ai.interpreter.execute_step")
def test_interpreter_confirm_action_accepted(mock_exec, mock_confirm):
    provider = MockProvider('{"message": "Running", "actions": [{"type": "project_run", "project": "a", "command": "b"}]}')
    interpreter = AIInterpreter(provider)
    
    from scout.workflow.actions import StepResult
    mock_exec.return_value = StepResult(True, "OK")
    mock_confirm.return_value = True  # User accepts
    
    interpreter.ask("run it")
    
    assert mock_confirm.call_count == 1
    assert len(provider.calls) == 2


@patch("scout.ai.interpreter.Confirm.ask")
@patch("scout.ai.interpreter.execute_step")
def test_interpreter_confirm_action_rejected(mock_exec, mock_confirm):
    provider = MockProvider('{"message": "Running", "actions": [{"type": "project_run", "project": "a", "command": "b"}]}')
    interpreter = AIInterpreter(provider)
    
    mock_confirm.return_value = False  # User rejects
    
    interpreter.ask("run it")
    
    assert mock_confirm.call_count == 1
    assert mock_exec.call_count == 0  # Should not execute
    assert "cancelled by the user" in interpreter.messages[-1]["content"]


@patch("scout.ai.interpreter.Confirm.ask")
@patch("scout.ai.interpreter.execute_step")
def test_interpreter_schema_correction_loop(mock_exec, mock_confirm):
    # First response is bad JSON, second response is good JSON
    provider = MockProvider()
    provider.generate_plan = MagicMock(side_effect=[
        'BAD JSON',
        '{"message": "Fixed", "actions": []}'
    ])
    
    interpreter = AIInterpreter(provider)
    interpreter.ask("do something")
    
    assert provider.generate_plan.call_count == 2
    # The message history should contain the schema error
    assert "Schema Error" in interpreter.messages[-2]["content"]


def test_chat_turn_memory():
    provider = MockProvider('{"message": "Fixed", "actions": []}')
    interpreter = AIInterpreter(provider)
    
    interpreter.chat_turn("turn 1")
    assert interpreter.messages[0]["content"] == "turn 1"
    
    interpreter.chat_turn("turn 2")
    # messages list: user(1), assistant(1), user(2)
    assert interpreter.messages[2]["content"] == "turn 2"
