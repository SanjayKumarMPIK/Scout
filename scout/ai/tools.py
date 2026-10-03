"""AI Tool registry and execution."""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

@dataclass
class StepResult:
    success: bool
    message: str = ""

@dataclass
class AITool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., StepResult]

_TOOLS: dict[str, AITool] = {}

def register_tool(name: str, description: str, parameters: dict[str, Any]):
    def decorator(func: Callable[..., StepResult]):
        _TOOLS[name] = AITool(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
        )
        return func
    return decorator

def get_tools() -> list[dict[str, Any]]:
    """Return JSON schema format of all registered tools."""
    tools_list = []
    for tool in _TOOLS.values():
        tools_list.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
        })
    return tools_list

def execute_tool(name: str, args: dict[str, Any]) -> StepResult:
    """Execute a tool by name with arguments."""
    tool = _TOOLS.get(name)
    if not tool:
        return StepResult(False, f"Tool '{name}' not found.")
    
    try:
        # We can map kwargs directly to the handler
        return tool.handler(**args)
    except TypeError as e:
        return StepResult(False, f"Invalid arguments for {name}: {e}")
    except Exception as e:
        return StepResult(False, f"Tool {name} execution failed: {e}")

# -- Tool Implementations --

@register_tool(
    name="open_application",
    description="Open an application on Windows (e.g. notepad, chrome, vscode).",
    parameters={
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "The name of the application to open."}
        },
        "required": ["app"]
    }
)
def tool_open_application(app: str) -> StepResult:
    from scout.ai.window_manager import find_window, activate_window, get_active_window
    import time
    import json
    
    # Maybe it's already open?
    win = find_window(app)
    if not win:
        from scout.commands.apps import _resolve_app
        import subprocess
        exe = _resolve_app(app)
        if not exe:
            return StepResult(False, f"Could not find application: {app}")
        try:
            subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        except OSError as exc:
            return StepResult(False, f"Failed to open {app}: {exc}")
        
        # Wait for window to appear
        for _ in range(10):
            time.sleep(0.5)
            win = find_window(app)
            if win:
                break
    
    if not win:
        return StepResult(False, f"Opened {app}, but could not detect its window.")
        
    # Attempt to activate it
    activate_window(win["title"])
    
    # Verify
    active = get_active_window()
    is_active = False
    if active and active.get("handle") == win.get("handle"):
        is_active = True
        
    info = {
        "success": True,
        "application": app,
        "window_title": win["title"],
        "window_handle": win["handle"],
        "active": is_active
    }
    return StepResult(True, json.dumps(info))

@register_tool(
    name="run_command",
    description="Run a shell command in the terminal. Use cautiously.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run."},
            "cwd": {"type": "string", "description": "Optional working directory."}
        },
        "required": ["command"]
    }
)
def tool_run_command(command: str, cwd: str = "") -> StepResult:
    from scout.core.safety import is_blocked, is_destructive, confirm_destructive
    import subprocess
    
    if is_blocked(command):
        return StepResult(False, f"Blocked: {command}")
    if is_destructive(command) and not confirm_destructive(command):
        return StepResult(False, "Cancelled by user")

    try:
        ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        result = subprocess.run(ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=cwd or None)
        out = ""
        if result.stdout:
            out += result.stdout.rstrip() + "\n"
        if result.stderr:
            out += "STDERR: " + result.stderr.rstrip() + "\n"
            
        if result.returncode != 0:
            return StepResult(False, f"Exited with code {result.returncode}\n{out}")
        return StepResult(True, f"Command completed (exit 0)\n{out}")
    except subprocess.TimeoutExpired:
        return StepResult(False, "Command timed out (120 s)")
    except Exception as exc:
        return StepResult(False, str(exc))

# -- Removed legacy mouse/keyboard tools (now unified under 'computer') --

# -- New Window Management Tools --

@register_tool(
    name="list_windows",
    description="List all visible windows with their titles and handles.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def tool_list_windows() -> StepResult:
    from scout.ai.window_manager import list_windows
    windows = list_windows()
    if not windows:
        return StepResult(True, "No visible windows found.")
    info = ", ".join([w["title"] for w in windows])
    return StepResult(True, f"Found {len(windows)} windows: {info}")

@register_tool(
    name="get_active_window",
    description="Get the currently active and focused window.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def tool_get_active_window() -> StepResult:
    from scout.ai.window_manager import get_active_window
    win = get_active_window()
    if win:
        import json
        return StepResult(True, json.dumps(win))
    return StepResult(False, "No active window found.")

@register_tool(
    name="find_window",
    description="Find a window by its partial title or application name.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title or app name to search for."}
        },
        "required": ["title"]
    }
)
def tool_find_window(title: str) -> StepResult:
    from scout.ai.window_manager import find_window
    win = find_window(title)
    if win:
        import json
        return StepResult(True, json.dumps(win))
    return StepResult(False, f"No window found matching '{title}'.")

# -- Removed tool_activate_window (now in 'computer') --

@register_tool(
    name="close_window",
    description="Close a window gracefully by its partial title.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the window to close."}
        },
        "required": ["title"]
    }
)
def tool_close_window(title: str) -> StepResult:
    from scout.ai.window_manager import close_window
    if close_window(title):
        return StepResult(True, f"Closed window '{title}'.")
    return StepResult(False, f"Failed to find or close window '{title}'.")


@register_tool(
    name="list_files",
    description="List files in a directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the directory (default: current directory)"}
        }
    }
)
def tool_list_files(path: str = ".") -> StepResult:
    try:
        p = Path(path).resolve()
        if not p.is_dir():
            return StepResult(False, f"{path} is not a directory")
        files = [f.name for f in p.iterdir()]
        return StepResult(True, f"Files in {p}: " + ", ".join(files))
    except Exception as e:
        return StepResult(False, str(e))

@register_tool(
    name="read_file",
    description="Read the contents of a text file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."}
        },
        "required": ["path"]
    }
)
def tool_read_file(path: str) -> StepResult:
    try:
        p = Path(path).resolve()
        if not p.is_file():
            return StepResult(False, f"File {path} does not exist.")
        content = p.read_text(encoding="utf-8")
        # Truncate if too long to save context
        if len(content) > 2000:
            content = content[:2000] + "... [TRUNCATED]"
        return StepResult(True, content)
    except Exception as e:
        return StepResult(False, str(e))

@register_tool(
    name="write_file",
    description="Write content to a file (overwrites).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file."},
            "content": {"type": "string", "description": "Text content to write."}
        },
        "required": ["path", "content"]
    }
)
def tool_write_file(path: str, content: str) -> StepResult:
    try:
        p = Path(path).resolve()
        p.write_text(content, encoding="utf-8")
        return StepResult(True, f"Successfully wrote to {p}")
    except Exception as e:
        return StepResult(False, str(e))

@register_tool(
    name="create_directory",
    description="Create a new directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path of the directory to create."}
        },
        "required": ["path"]
    }
)
def tool_create_directory(path: str) -> StepResult:
    try:
        p = Path(path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return StepResult(True, f"Directory created: {p}")
    except Exception as e:
        return StepResult(False, str(e))

@register_tool(
    name="open_url",
    description="Open a URL in the default browser.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to open."}
        },
        "required": ["url"]
    }
)
def tool_open_url(url: str) -> StepResult:
    import webbrowser
    webbrowser.open(url)
    return StepResult(True, f"Opened URL: {url}")

@register_tool(
    name="complete_task",
    description="Mark the current task as fully completed with a final response.",
    parameters={
        "type": "object",
        "properties": {
            "response": {"type": "string", "description": "Final response to the user."}
        },
        "required": ["response"]
    }
)
def tool_complete_task(response: str) -> StepResult:
    # This is a special tool, handled by the loop to break out.
    return StepResult(True, response)


@register_tool(
    name="verify_screen",
    description="Capture the screen and verify if the expected visual state is met. Use this to verify success of UI actions.",
    parameters={
        "type": "object",
        "properties": {
            "expected_state": {
                "type": "string",
                "description": "A clear description of what should be visible on the screen if the action succeeded. E.g., 'Notepad is open and the text says Hello'."
            }
        },
        "required": ["expected_state"]
    }
)
def tool_verify_screen(expected_state: str) -> StepResult:
    from scout.vision.capture import take_screenshot
    from scout.vision.core import get_vision_provider
    import json
    
    provider = get_vision_provider()
    if not provider:
        return StepResult(False, "Vision provider not configured or available. Cannot verify visually.")
        
    cap = take_screenshot()
    if not cap.get("success"):
        return StepResult(False, f"Failed to capture screen: {cap.get('error')}")
        
    path = cap["path"]
    
    instruction = f"""
    Please verify the current state of the screen.
    EXPECTED STATE: {expected_state}
    
    Respond ONLY with a JSON object in this format:
    {{
      "verified": true/false,
      "observation": "Brief explanation of what you actually see."
    }}
    """
    
    res = provider.analyze(path, instruction)
    if not res.get("success"):
        return StepResult(False, f"Vision analysis failed: {res.get('observation')}")
        
    try:
        raw = res.get("raw", "")
        raw = raw.replace("```json\n", "").replace("```json\r\n", "").replace("```\n", "").replace("```", "").strip()
        data = json.loads(raw)
        verified = data.get("verified", False)
        obs = data.get("observation", "No observation provided.")
        return StepResult(True, f"Verified: {verified}\nObservation: {obs}")
    except json.JSONDecodeError:
        raw = res.get("raw", "")
        verified = "true" in raw.lower() and "false" not in raw.lower()
        return StepResult(True, f"Verified (guessed): {verified}\nRaw Observation: {raw}")

# -- Unified Computer Tool --

@register_tool(
    name="computer",
    description="Unified interface for executing UI/computer actions (mouse, keyboard, window, screenshot).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string", 
                "enum": ["screenshot", "click", "double_click", "move", "drag", "type", "key", "hotkey", "scroll", "activate_window", "minimize_window", "maximize_window", "wait"],
                "description": "The action to perform."
            },
            "x": {"type": "integer", "description": "X coordinate for mouse actions"},
            "y": {"type": "integer", "description": "Y coordinate for mouse actions"},
            "from_x": {"type": "integer", "description": "Starting X for drag"},
            "from_y": {"type": "integer", "description": "Starting Y for drag"},
            "to_x": {"type": "integer", "description": "Ending X for drag"},
            "to_y": {"type": "integer", "description": "Ending Y for drag"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button"},
            "text": {"type": "string", "description": "Text to type (for type action)"},
            "key": {"type": "string", "description": "Key to press (for key action)"},
            "keys": {"type": "array", "items": {"type": "string"}, "description": "List of keys for hotkey (e.g. ['ctrl', 's'])"},
            "amount": {"type": "integer", "description": "Scroll amount (positive up, negative down)"},
            "title": {"type": "string", "description": "Window title to activate/minimize/maximize"},
            "seconds": {"type": "number", "description": "Seconds to wait"}
        },
        "required": ["action"]
    }
)
def tool_computer(**kwargs) -> StepResult:
    from scout.computer.controller import get_computer_controller
    import json
    
    ctrl = get_computer_controller()
    res = ctrl.execute(kwargs)
    
    success = res.get("success", False)
    # Convert result dictionary to formatted string for the model
    msg = json.dumps(res)
    
    return StepResult(success, msg)
