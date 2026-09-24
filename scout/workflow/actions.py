"""Workflow action executor – translates workflow steps into existing SCOUT commands.

This module does NOT duplicate any command logic.  Every action is routed
through the same code paths that the interactive CLI uses, including the
safety layer.
"""

from __future__ import annotations

import os
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from scout.core.safety import confirm_destructive, is_blocked, is_destructive
from scout.workflow.parser import WorkflowStep

console = Console()


@dataclass
class StepResult:
    """Outcome of executing a single workflow step."""
    success: bool
    message: str = ""


# ── Individual action handlers ─────────────────────────────────────────

def _exec_open_app(step: WorkflowStep) -> StepResult:
    """Open an application – delegates to the same logic as ``open`` command."""
    app = step.params.get("app")
    if not app:
        return StepResult(False, "Missing 'app' parameter")

    # Re-use apps module logic (import here to avoid circular deps at module level).
    from scout.commands.apps import _resolve_app

    exe = _resolve_app(app)
    if exe is None:
        return StepResult(False, f"Could not find application: {app}")

    try:
        subprocess.Popen(
            [exe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return StepResult(True, f"{app} opened")
    except OSError as exc:
        return StepResult(False, f"Failed to open {app}: {exc}")


def _exec_run_command(step: WorkflowStep) -> StepResult:
    """Run a shell command – goes through the full safety layer."""
    command = step.params.get("command")
    if not command:
        return StepResult(False, "Missing 'command' parameter")

    # Safety checks – identical to scout.commands.terminal
    if is_blocked(command):
        return StepResult(False, f"Blocked: {command}")

    if is_destructive(command):
        if not confirm_destructive(command):
            return StepResult(False, "Cancelled by user")

    cwd = step.params.get("cwd")

    try:
        result = subprocess.run(
            command,
            shell=True,  # noqa: S602
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=120,
            cwd=cwd,
        )
        if result.stdout:
            console.print(result.stdout.rstrip())
        if result.stderr:
            console.print(f"[yellow]{result.stderr.rstrip()}[/]")
        if result.returncode != 0:
            return StepResult(False, f"Exited with code {result.returncode}")
        return StepResult(True, "Command completed (exit 0)")
    except subprocess.TimeoutExpired:
        return StepResult(False, "Command timed out (120 s)")
    except Exception as exc:  # noqa: BLE001
        return StepResult(False, str(exc))


def _exec_type(step: WorkflowStep) -> StepResult:
    """Type text via keyboard – delegates to PyAutoGUI."""
    text = step.params.get("text")
    if not text:
        return StepResult(False, "Missing 'text' parameter")

    import pyautogui
    pyautogui.typewrite(text, interval=0.02)
    return StepResult(True, f"Typed {len(text)} chars")


def _exec_press(step: WorkflowStep) -> StepResult:
    """Press a key or combo – delegates to PyAutoGUI."""
    key = step.params.get("key")
    if not key:
        return StepResult(False, "Missing 'key' parameter")

    import pyautogui
    keys = key.lower().split("+")
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return StepResult(True, f"Pressed {key}")


def _exec_wait(step: WorkflowStep) -> StepResult:
    """Wait for a specified number of seconds."""
    seconds = step.params.get("seconds", 1)
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return StepResult(False, f"Invalid 'seconds' value: {seconds}")

    if seconds < 0 or seconds > 300:
        return StepResult(False, f"Wait time must be 0-300 seconds, got {seconds}")

    time.sleep(seconds)
    return StepResult(True, f"Waited {seconds}s")


def _exec_open_url(step: WorkflowStep) -> StepResult:
    """Open a URL in the default browser."""
    url = step.params.get("url")
    if not url:
        return StepResult(False, "Missing 'url' parameter")

    try:
        webbrowser.open(url)
        return StepResult(True, f"Opened {url}")
    except Exception as exc:  # noqa: BLE001
        return StepResult(False, f"Failed to open URL: {exc}")


def _exec_change_directory(step: WorkflowStep) -> StepResult:
    """Change the working directory for subsequent steps."""
    path = step.params.get("path")
    if not path:
        return StepResult(False, "Missing 'path' parameter")

    target = Path(path)
    if not target.is_dir():
        return StepResult(False, f"Directory does not exist: {path}")

    try:
        os.chdir(target)
        return StepResult(True, f"Changed directory to {target}")
    except OSError as exc:
        return StepResult(False, f"Failed to change directory: {exc}")


def _exec_project_open(step: WorkflowStep) -> StepResult:
    """Open a registered project in VS Code."""
    project = step.params.get("project")
    if not project:
        return StepResult(False, "Missing 'project' parameter")

    from scout.core.project_manager import get_project
    entry = get_project(project)
    if entry is None:
        return StepResult(False, f"Project '{project}' not found")

    _, path = entry
    try:
        subprocess.Popen(
            ["code", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return StepResult(True, f"Opened project {project} in VS Code")
    except OSError as exc:
        return StepResult(False, f"Failed to open project: {exc}")


def _exec_project_run(step: WorkflowStep) -> StepResult:
    """Run a command in a registered project's directory."""
    project = step.params.get("project")
    command = step.params.get("command")
    if not project:
        return StepResult(False, "Missing 'project' parameter")
    if not command:
        return StepResult(False, "Missing 'command' parameter")

    from scout.core.project_manager import get_project
    entry = get_project(project)
    if entry is None:
        return StepResult(False, f"Project '{project}' not found")

    _, path = entry

    # Safety checks
    if is_blocked(command):
        return StepResult(False, f"Blocked: {command}")
    if is_destructive(command):
        if not confirm_destructive(command):
            return StepResult(False, "Cancelled by user")

    try:
        result = subprocess.run(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, text=True,
            timeout=120, cwd=path,
        )
        if result.stdout:
            console.print(result.stdout.rstrip())
        if result.stderr:
            console.print(f"[yellow]{result.stderr.rstrip()}[/]")
        if result.returncode != 0:
            return StepResult(False, f"Exited with code {result.returncode}")
        return StepResult(True, "Command completed (exit 0)")
    except subprocess.TimeoutExpired:
        return StepResult(False, "Command timed out (120 s)")
    except Exception as exc:
        return StepResult(False, str(exc))


# ── Dispatch table ─────────────────────────────────────────────────────

_ACTION_HANDLERS: dict[str, callable] = {
    "open_app":          _exec_open_app,
    "run_command":       _exec_run_command,
    "type":              _exec_type,
    "press":             _exec_press,
    "wait":              _exec_wait,
    "open_url":          _exec_open_url,
    "change_directory":  _exec_change_directory,
    "project_open":      _exec_project_open,
    "project_run":       _exec_project_run,
}


def execute_step(step: WorkflowStep) -> StepResult:
    """Execute a single workflow step and return the result."""
    handler = _ACTION_HANDLERS.get(step.action)
    if handler is None:
        return StepResult(False, f"Unknown action: {step.action}")
    return handler(step)

