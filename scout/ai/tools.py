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

def _resolve_app(name: str) -> str | None:
    """Return the first working executable path for *name*, or None."""
    import shutil
    from scout.config import APP_ALIASES

    name_lower = name.lower()
    candidates = APP_ALIASES.get(name_lower)

    # Substring match if exact match fails
    if not candidates:
        for alias, paths in APP_ALIASES.items():
            if alias in name_lower or name_lower in alias:
                candidates = paths
                break

    if not candidates:
        candidates = [name]

    for candidate in candidates:
        # Try PATH lookup first
        found = shutil.which(candidate)
        if found:
            return found
    # Absolute paths that exist but aren't on PATH
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None

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
        import subprocess
        exe = _resolve_app(app)
        try:
            if exe:
                subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                # Fall back to the Windows shell (resolves App Paths like 'winword', 'spotify').
                os.startfile(app)  # type: ignore[attr-defined]
        except OSError as exc:
            return StepResult(False, f"Could not find or open application '{app}': {exc}")
        
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
            "cwd": {"type": "string", "description": "Optional working directory."},
            "background": {"type": "boolean", "description": "Set to true for long-running servers/daemons (e.g. npm run dev, python -m http.server). Returns immediately after capturing initial output."}
        },
        "required": ["command"]
    }
)
def tool_run_command(command: str, cwd: str = "", background: bool = False) -> StepResult:
    from scout.core.safety import is_blocked, is_destructive, confirm_destructive
    import subprocess
    import time
    import tempfile
    import os
    
    if is_blocked(command):
        return StepResult(False, f"Blocked: {command}")
    if is_destructive(command) and not confirm_destructive(command):
        return StepResult(False, "Cancelled by user")

    ps_cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    
    if background:
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
            os.close(fd)
            
            with open(temp_path, "w") as out_f:
                p = subprocess.Popen(
                    ps_cmd, 
                    stdout=out_f, 
                    stderr=subprocess.STDOUT, 
                    stdin=subprocess.DEVNULL,
                    cwd=cwd or None, 
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            
            # Wait a short moment to capture startup logs
            time.sleep(3)
            
            ret = p.poll()
            with open(temp_path, "r", encoding="utf-8", errors="replace") as in_f:
                out = in_f.read()
                
            try:
                os.remove(temp_path)
            except OSError:
                pass
                
            if ret is not None and ret != 0:
                return StepResult(False, f"Background command exited early with code {ret}\nOutput:\n{out}")
                
            return StepResult(True, f"Started in background (PID {p.pid}).\nInitial Output:\n{out.strip()}")
        except Exception as exc:
            return StepResult(False, f"Failed to start background command: {exc}")

    try:
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
        return StepResult(False, "Command timed out (120 s). If this is a server, set background=true.")
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
    description="Close a window gracefully by its partial title. WARNING: If the window is a web browser (e.g. Chrome, Edge), this will close the ENTIRE browser and ALL tabs. To close a single tab, DO NOT use this tool; use the `computer` tool to activate the window and press `ctrl+w` instead.",
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

@register_tool(
    name="analyze_screen",
    description="Capture the screen and ask the vision model a question or instruction about it (e.g., 'What am I looking at?', 'Find the coordinates of the login button').",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The question or instruction for analyzing the screen."
            }
        },
        "required": ["prompt"]
    }
)
def tool_analyze_screen(prompt: str) -> StepResult:
    from scout.vision.capture import take_screenshot
    from scout.vision.core import get_vision_provider
    
    provider = get_vision_provider()
    if not provider:
        return StepResult(False, "Vision provider not configured or available.")
        
    cap = take_screenshot()
    if not cap.get("success"):
        return StepResult(False, f"Failed to capture screen: {cap.get('error')}")
        
    res = provider.analyze(cap["path"], prompt)
    if not res.get("success"):
        return StepResult(False, f"Vision analysis failed: {res.get('observation')}")
        
    return StepResult(True, res.get("observation", "No observation provided."))

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

# -- Web Research & Browser Automation Tools --

@register_tool(
    name="web_search",
    description="Search the web for information, documentation, news, or answers. Supports multiple queries for complex research. Returns titles, URLs, snippets, and publication dates.",
    parameters={
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One or more search queries to research the topic thoroughly."
            },
            "query": {
                "type": "string",
                "description": "Optional single query string (alternative to queries)."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 6)."
            }
        }
    }
)
def tool_web_search(queries: list[str] | None = None, query: str = "", max_results: int = 6) -> StepResult:
    from scout.web.search import search_web, SearchProviderError
    try:
        search_inputs = []
        if queries:
            search_inputs.extend(queries)
        if query:
            search_inputs.append(query)
        if not search_inputs:
            return StepResult(False, "No search query provided. Please specify 'queries' or 'query'.")

        results = search_web(search_inputs, max_results=max_results)
        if not results:
            return StepResult(True, "Web search returned no matching results for the specified queries.")

        import json
        formatted_list = [r.to_dict() for r in results]
        return StepResult(True, json.dumps(formatted_list, indent=2))
    except SearchProviderError as e:
        return StepResult(False, f"Search provider error: {e}")
    except Exception as e:
        return StepResult(False, f"Web search failed: {e}")


@register_tool(
    name="fetch_webpage",
    description="Fetch a publicly accessible webpage using fast direct HTTP and extract its readable text, headings, links, and metadata. Detects if the page requires JavaScript rendering. Prefer this over browser automation for static pages.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP or HTTPS URL of the webpage to fetch."
            }
        },
        "required": ["url"]
    }
)
def tool_fetch_webpage(url: str) -> StepResult:
    from scout.web.fetcher import fetch_webpage
    from scout.web.security import SecurityError
    try:
        page = fetch_webpage(url)
        return StepResult(True, page.to_formatted_text())
    except SecurityError as e:
        return StepResult(False, f"Security restriction: {e}")
    except Exception as e:
        return StepResult(False, f"Failed to fetch webpage '{url}': {e}")


@register_tool(
    name="browser_navigate",
    description="Open a URL in a real browser session. Use when JavaScript rendering, dynamic content, or browser interaction is required.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to navigate to in the browser."
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Optional navigation timeout in milliseconds (default 25000)."
            }
        },
        "required": ["url"]
    }
)
def tool_browser_navigate(url: str, timeout_ms: int | None = None) -> StepResult:
    from scout.web.browser import get_browser_session, BrowserSessionError
    from scout.web.security import SecurityError
    try:
        session = get_browser_session()
        res = session.navigate(url, timeout_ms=timeout_ms)
        if res.get("success"):
            return StepResult(True, res["formatted"])
        return StepResult(False, f"Browser navigation failed: {res.get('error')}")
    except SecurityError as e:
        return StepResult(False, f"Security restriction: {e}")
    except BrowserSessionError as e:
        return StepResult(False, f"Browser session error: {e}")
    except Exception as e:
        return StepResult(False, f"Browser error: {e}")


@register_tool(
    name="browser_extract",
    description="Extract structured information from the active browser page: text, headings, links, tables, lists, specific selector elements, or named structured fields.",
    parameters={
        "type": "object",
        "properties": {
            "extract_type": {
                "type": "string",
                "enum": ["all", "text", "links", "tables", "lists", "elements"],
                "description": "The type of information to extract (default 'all')."
            },
            "selector": {
                "type": "string",
                "description": "Optional CSS selector to extract specific elements (used with extract_type='elements' or alongside other types)."
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of specific named fields to extract (e.g. ['price', 'title', 'rating', 'availability'])."
            },
            "next_selector": {
                "type": "string",
                "description": "Optional selector for next-page button when extracting across paginated pages."
            },
            "max_pages": {
                "type": "integer",
                "description": "Maximum pages to navigate across during pagination (default 1)."
            }
        }
    }
)
def tool_browser_extract(
    extract_type: str = "all",
    selector: str = "",
    fields: list[str] | None = None,
    next_selector: str = "",
    max_pages: int = 1,
) -> StepResult:
    from scout.web.browser import get_browser_session, BrowserSessionError
    try:
        session = get_browser_session()
        res = session.extract(
            extract_type=extract_type,
            selector=selector,
            fields=fields,
            next_selector=next_selector,
            max_pages=max_pages,
        )
        return StepResult(True, res["formatted"])
    except BrowserSessionError as e:
        return StepResult(False, str(e))
    except Exception as e:
        return StepResult(False, f"Browser extraction failed: {e}")


@register_tool(
    name="browser_interact",
    description="Interact with the active browser page: click a visible element, type into an input field, select a dropdown option, scroll, navigate, or wait. Returns updated page state.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["click", "type", "select_option", "scroll", "navigate", "wait"],
                "description": "The browser action to perform."
            },
            "selector": {
                "type": "string",
                "description": "Target element selector (CSS, text=..., role=..., or label=...)."
            },
            "text": {
                "type": "string",
                "description": "Text to type into fields or URL to navigate."
            },
            "value": {
                "type": "string",
                "description": "Option value or label for select_option."
            },
            "direction": {
                "type": "string",
                "enum": ["down", "up", "top", "bottom"],
                "description": "Scroll direction (default 'down')."
            },
            "amount": {
                "type": "integer",
                "description": "Scroll distance in pixels (default 500)."
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds for element readiness (default 10000)."
            }
        },
        "required": ["action"]
    }
)
def tool_browser_interact(
    action: str,
    selector: str = "",
    text: str = "",
    value: str = "",
    direction: str = "down",
    amount: int = 500,
    timeout_ms: int = 10000,
) -> StepResult:
    from scout.web.browser import get_browser_session, BrowserSessionError
    from scout.web.security import SecurityError
    import json
    try:
        session = get_browser_session()
        res = session.interact(
            action=action,
            selector=selector,
            text=text,
            value=value,
            direction=direction,
            amount=amount,
            timeout_ms=timeout_ms,
        )
        success = res.get("success", False)
        if success:
            return StepResult(True, res.get("observation", json.dumps(res)))
        return StepResult(False, f"Browser interaction failed: {res.get('error', 'unknown error')}")
    except SecurityError as e:
        return StepResult(False, f"Security restriction: {e}")
    except BrowserSessionError as e:
        return StepResult(False, str(e))
    except Exception as e:
        return StepResult(False, f"Browser interaction error: {e}")


@register_tool(
    name="browser_close",
    description="Close the active browser session and release browser resources.",
    parameters={
        "type": "object",
        "properties": {}
    }
)
def tool_browser_close() -> StepResult:
    from scout.web.browser import get_browser_session
    try:
        session = get_browser_session()
        session.close()
        return StepResult(True, "Browser session closed successfully.")
    except Exception as e:
        return StepResult(False, f"Failed to close browser: {e}")

