"""Tests for Phase 2: workflow engine, parser, variable substitution, and execution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.user_config import resolve_variables
from scout.workflow.parser import (
    Workflow,
    WorkflowParseError,
    WorkflowStep,
    parse_workflow,
)
from scout.workflow.actions import StepResult, execute_step
from scout.workflow.manager import (
    discover_workflows,
    load_workflow,
    set_workflow_dirs,
)


# ── Helpers ────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_workflows(tmp_path: Path):
    """Create a temp workflow directory and point the manager at it."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    set_workflow_dirs([wf_dir])
    yield wf_dir
    set_workflow_dirs([])  # reset


def _write_workflow(directory: Path, name: str, data: dict) -> Path:
    """Write a workflow JSON file and return its path."""
    path = directory / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


VALID_WORKFLOW = {
    "name": "test-wf",
    "description": "A test workflow",
    "steps": [
        {"action": "run_command", "command": "echo hello"},
        {"action": "wait", "seconds": 0},
    ],
}


# ── Variable substitution tests ────────────────────────────────────────

class TestVariableSubstitution:
    def test_simple_substitution(self):
        config = {"projects": {"web": r"C:\Projects\Web"}}
        result = resolve_variables("${projects.web}", config)
        assert result == r"C:\Projects\Web"

    def test_multiple_substitutions(self):
        config = {"projects": {"a": "AAA", "b": "BBB"}}
        result = resolve_variables("${projects.a} and ${projects.b}", config)
        assert result == "AAA and BBB"

    def test_unknown_variable_left_as_is(self):
        config = {"projects": {"web": "X"}}
        result = resolve_variables("${projects.missing}", config)
        assert result == "${projects.missing}"

    def test_no_variables(self):
        result = resolve_variables("plain text", {})
        assert result == "plain text"

    def test_nested_in_path(self):
        config = {"projects": {"native": r"C:\PROJECTS\Native"}}
        result = resolve_variables(r"${projects.native}\android", config)
        assert result == r"C:\PROJECTS\Native\android"


# ── Workflow discovery tests ───────────────────────────────────────────

class TestWorkflowDiscovery:
    def test_discover_empty_dir(self, tmp_workflows: Path):
        assert discover_workflows() == {}

    def test_discover_json_files(self, tmp_workflows: Path):
        _write_workflow(tmp_workflows, "alpha", VALID_WORKFLOW)
        _write_workflow(tmp_workflows, "beta", VALID_WORKFLOW)
        found = discover_workflows()
        assert "alpha" in found
        assert "beta" in found
        assert len(found) == 2

    def test_non_json_files_ignored(self, tmp_workflows: Path):
        (tmp_workflows / "readme.txt").write_text("not a workflow")
        _write_workflow(tmp_workflows, "real", VALID_WORKFLOW)
        found = discover_workflows()
        assert list(found.keys()) == ["real"]

    def test_multiple_dirs_first_wins(self, tmp_path: Path):
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        _write_workflow(dir1, "shared", {**VALID_WORKFLOW, "name": "from-dir1"})
        _write_workflow(dir2, "shared", {**VALID_WORKFLOW, "name": "from-dir2"})
        set_workflow_dirs([dir1, dir2])
        found = discover_workflows()
        assert found["shared"] == dir1 / "shared.json"
        set_workflow_dirs([])


# ── Workflow parsing tests ─────────────────────────────────────────────

class TestWorkflowParsing:
    def test_valid_workflow(self, tmp_workflows: Path):
        path = _write_workflow(tmp_workflows, "good", VALID_WORKFLOW)
        wf = parse_workflow(path)
        assert wf.name == "test-wf"
        assert wf.description == "A test workflow"
        assert len(wf.steps) == 2
        assert wf.steps[0].action == "run_command"
        assert wf.steps[1].action == "wait"

    def test_invalid_json(self, tmp_workflows: Path):
        bad = tmp_workflows / "bad.json"
        bad.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(WorkflowParseError, match="Invalid JSON"):
            parse_workflow(bad)

    def test_missing_name(self, tmp_workflows: Path):
        path = _write_workflow(tmp_workflows, "noname", {"steps": [{"action": "wait", "seconds": 1}]})
        with pytest.raises(WorkflowParseError, match="missing or invalid 'name'"):
            parse_workflow(path)

    def test_empty_steps(self, tmp_workflows: Path):
        path = _write_workflow(tmp_workflows, "empty", {"name": "x", "steps": []})
        with pytest.raises(WorkflowParseError, match="non-empty list"):
            parse_workflow(path)

    def test_invalid_action(self, tmp_workflows: Path):
        data = {"name": "x", "steps": [{"action": "explode_computer"}]}
        path = _write_workflow(tmp_workflows, "badact", data)
        with pytest.raises(WorkflowParseError, match="invalid action"):
            parse_workflow(path)

    def test_variable_resolution_in_steps(self, tmp_workflows: Path):
        data = {
            "name": "varstest",
            "steps": [{"action": "change_directory", "path": "${projects.web}"}],
        }
        path = _write_workflow(tmp_workflows, "vars", data)
        config = {"projects": {"web": r"C:\MyWeb"}}
        with patch("scout.workflow.parser.load_config", return_value=config):
            wf = parse_workflow(path)
        assert wf.steps[0].params["path"] == r"C:\MyWeb"

    def test_step_summary(self):
        step = WorkflowStep(1, "open_app", {"app": "chrome"}, {})
        assert step.summary == "Open chrome"
        step2 = WorkflowStep(2, "run_command", {"command": "npm start"}, {})
        assert step2.summary == "Run: npm start"


# ── Workflow loading tests ─────────────────────────────────────────────

class TestWorkflowLoading:
    def test_load_existing(self, tmp_workflows: Path):
        _write_workflow(tmp_workflows, "myflow", VALID_WORKFLOW)
        wf = load_workflow("myflow")
        assert wf.name == "test-wf"

    def test_load_nonexistent(self, tmp_workflows: Path):
        with pytest.raises(WorkflowParseError, match="not found"):
            load_workflow("does-not-exist")


# ── Workflow execution tests ───────────────────────────────────────────

class TestWorkflowExecution:
    def test_run_command_step(self):
        step = WorkflowStep(1, "run_command", {"command": "echo hello"}, {})
        result = execute_step(step)
        assert result.success

    def test_wait_step(self):
        step = WorkflowStep(1, "wait", {"seconds": 0}, {})
        result = execute_step(step)
        assert result.success

    def test_wait_negative(self):
        step = WorkflowStep(1, "wait", {"seconds": -5}, {})
        result = execute_step(step)
        assert not result.success

    def test_change_directory_step(self, tmp_path: Path):
        target = tmp_path / "subdir"
        target.mkdir()
        original = os.getcwd()
        try:
            step = WorkflowStep(1, "change_directory", {"path": str(target)}, {})
            result = execute_step(step)
            assert result.success
            assert os.getcwd() == str(target)
        finally:
            os.chdir(original)

    def test_change_directory_nonexistent(self):
        step = WorkflowStep(1, "change_directory", {"path": r"C:\DOES_NOT_EXIST_12345"}, {})
        result = execute_step(step)
        assert not result.success

    def test_missing_param(self):
        step = WorkflowStep(1, "run_command", {}, {})
        result = execute_step(step)
        assert not result.success
        assert "Missing" in result.message

    def test_unknown_action(self):
        step = WorkflowStep(1, "nuke_everything", {}, {})
        result = execute_step(step)
        assert not result.success


# ── Safety integration tests ──────────────────────────────────────────

class TestWorkflowSafety:
    def test_blocked_command_in_workflow(self):
        step = WorkflowStep(1, "run_command", {"command": "format c:"}, {})
        result = execute_step(step)
        assert not result.success
        assert "Blocked" in result.message

    def test_destructive_command_denied(self):
        step = WorkflowStep(1, "run_command", {"command": "del important.txt"}, {})
        with patch("scout.workflow.actions.confirm_destructive", return_value=False):
            result = execute_step(step)
        assert not result.success
        assert "Cancelled" in result.message

    def test_destructive_command_approved(self):
        step = WorkflowStep(1, "run_command", {"command": "del test_dummy.txt"}, {})
        with patch("scout.workflow.actions.confirm_destructive", return_value=True):
            # The command will fail because the file doesn't exist, but it
            # should pass the safety gate.
            result = execute_step(step)
            # On Windows `del nonexistent` returns exit code 0 anyway,
            # so we just verify it wasn't blocked by safety.
            assert "Blocked" not in result.message
            assert "Cancelled" not in result.message
