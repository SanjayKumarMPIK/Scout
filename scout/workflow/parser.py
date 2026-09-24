"""Workflow parser – loads and validates workflow JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from scout.user_config import load_config, resolve_variables

# Action types supported in V2.
VALID_ACTIONS: set[str] = {
    "open_app",
    "run_command",
    "type",
    "press",
    "wait",
    "open_url",
    "change_directory",
    "project_open",
    "project_run",
}


@dataclass
class WorkflowStep:
    """A single step inside a workflow."""
    index: int            # 1-based position
    action: str           # one of VALID_ACTIONS
    params: dict          # action-specific parameters (resolved)
    raw: dict             # original dict from JSON (pre-resolution)

    @property
    def summary(self) -> str:
        """Human-readable one-liner for this step."""
        if self.action == "open_app":
            return f"Open {self.params.get('app', '?')}"
        if self.action == "run_command":
            return f"Run: {self.params.get('command', '?')}"
        if self.action == "type":
            return f"Type: {self.params.get('text', '?')}"
        if self.action == "press":
            return f"Press: {self.params.get('key', '?')}"
        if self.action == "wait":
            return f"Wait {self.params.get('seconds', '?')}s"
        if self.action == "open_url":
            return f"Open URL: {self.params.get('url', '?')}"
        if self.action == "change_directory":
            return f"cd {self.params.get('path', '?')}"
        if self.action == "project_open":
            return f"Open project: {self.params.get('project', '?')}"
        if self.action == "project_run":
            return f"Project run: {self.params.get('project', '?')} -> {self.params.get('command', '?')}"
        return f"{self.action}: {self.params}"


@dataclass
class Workflow:
    """Parsed and validated workflow."""
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    source_path: Path | None = None


class WorkflowParseError(Exception):
    """Raised when a workflow file is invalid."""


def parse_workflow(path: Path) -> Workflow:
    """Parse a workflow JSON file and return a validated Workflow object.

    Variables (``${section.key}``) in string values are resolved against
    the user's ``config.json``.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowParseError(f"Invalid JSON in {path.name}: {exc}") from exc
    except OSError as exc:
        raise WorkflowParseError(f"Cannot read {path.name}: {exc}") from exc

    if not isinstance(raw, dict):
        raise WorkflowParseError(f"{path.name}: top-level must be a JSON object")

    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise WorkflowParseError(f"{path.name}: missing or invalid 'name' field")

    description = raw.get("description", "")
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or len(raw_steps) == 0:
        raise WorkflowParseError(f"{path.name}: 'steps' must be a non-empty list")

    config = load_config()
    steps: list[WorkflowStep] = []

    for i, step_dict in enumerate(raw_steps, start=1):
        if not isinstance(step_dict, dict):
            raise WorkflowParseError(f"{path.name}: step {i} must be a JSON object")

        action = step_dict.get("action")
        if action not in VALID_ACTIONS:
            raise WorkflowParseError(
                f"{path.name}: step {i} has invalid action '{action}'. "
                f"Valid actions: {', '.join(sorted(VALID_ACTIONS))}"
            )

        # Resolve variables in all string-valued params.
        params: dict = {}
        for k, v in step_dict.items():
            if k == "action":
                continue
            if isinstance(v, str):
                params[k] = resolve_variables(v, config)
            else:
                params[k] = v

        steps.append(WorkflowStep(index=i, action=action, params=params, raw=step_dict))

    return Workflow(
        name=name,
        description=description,
        steps=steps,
        source_path=path,
    )
