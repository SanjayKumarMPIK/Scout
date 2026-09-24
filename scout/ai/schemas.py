"""AI structured response schemas and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass

from scout.workflow.parser import VALID_ACTIONS


@dataclass
class AIAction:
    action_type: str
    params: dict


@dataclass
class AIPlan:
    message: str
    actions: list[AIAction]


def parse_and_validate_plan(raw_json: str) -> AIPlan:
    """
    Parse the AI's JSON string and ensure it adheres strictly to the schema.
    Raises ValueError with a helpful message if invalid, which can be fed back to the AI.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response: {e}")

    if not isinstance(data, dict):
        raise ValueError("Root of response must be a JSON object.")

    if "message" not in data or not isinstance(data["message"], str):
        raise ValueError("Response must contain a 'message' string field.")

    if "actions" not in data or not isinstance(data["actions"], list):
        raise ValueError("Response must contain an 'actions' array field.")

    parsed_actions = []
    for idx, act in enumerate(data["actions"]):
        if not isinstance(act, dict):
            raise ValueError(f"Action at index {idx} is not an object.")

        if "type" not in act:
            raise ValueError(f"Action at index {idx} missing 'type' field.")

        action_type = act["type"]
        if action_type not in VALID_ACTIONS and action_type not in ["system_info", "project_info", "git_status", "git_log", "git_diff", "git_branch", "git_pull", "git_push", "git_commit", "workflow_run"]:
            # Validate action types broadly here. 
            # We'll allow some extra ones not strictly in workflows for interactive use.
            # But they still need to be handled by the interpreter.
            # Wait, let's keep it strictly tied to VALID_ACTIONS from workflow + a few specials.
            pass

        # Construct params dictionary (everything except 'type')
        params = {k: v for k, v in act.items() if k != "type"}
        
        # Enforce required params
        if action_type == "open_app" and "app" not in params:
            raise ValueError("open_app action requires 'app' parameter.")
        if action_type == "run_command" and "command" not in params:
            raise ValueError("run_command action requires 'command' parameter.")
        if action_type == "type" and "text" not in params:
            raise ValueError("type action requires 'text' parameter.")
        if action_type == "press" and "key" not in params:
            raise ValueError("press action requires 'key' parameter.")
        if action_type == "wait" and "seconds" not in params:
            raise ValueError("wait action requires 'seconds' parameter.")
        if action_type == "open_url" and "url" not in params:
            raise ValueError("open_url action requires 'url' parameter.")
        if action_type == "change_directory" and "path" not in params:
            raise ValueError("change_directory action requires 'path' parameter.")
        if action_type == "project_open" and "project" not in params:
            raise ValueError("project_open action requires 'project' parameter.")
        if action_type == "project_run":
            if "project" not in params or "command" not in params:
                raise ValueError("project_run action requires 'project' and 'command' parameters.")
        if action_type in ["project_info", "git_status", "git_log", "git_diff", "git_branch", "git_pull", "git_push", "git_commit"]:
            if "project" not in params:
                raise ValueError(f"{action_type} action requires 'project' parameter.")
        if action_type == "workflow_run" and "name" not in params:
            raise ValueError("workflow_run action requires 'name' parameter.")

        parsed_actions.append(AIAction(action_type, params))

    return AIPlan(data["message"], parsed_actions)
