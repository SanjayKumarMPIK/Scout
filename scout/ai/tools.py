"""AI Tool registry and execution."""

from __future__ import annotations

import inspect
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from bs4 import BeautifulSoup

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


def _resolve_path(path: str) -> Path:
    """Expand user tildes, environment variables, and fallback to home directory for known folders."""
    if not path or not str(path).strip():
        return Path.cwd()
    raw = str(path).strip().strip('"\'')
    expanded = os.path.expandvars(os.path.expanduser(raw))
    p = Path(expanded)
    if not p.is_absolute():
        resolved = (Path.cwd() / p).resolve()
        if resolved.exists():
            return resolved
        home_candidate = (Path.home() / p).resolve()
        if home_candidate.exists():
            return home_candidate
        return resolved
    return p.resolve()


@register_tool(
    name="list_files",
    description="List files in a directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the directory (e.g. 'Downloads', '~/Desktop', or '.')"}
        }
    }
)
def tool_list_files(path: str = ".") -> StepResult:
    try:
        p = _resolve_path(path)
        if not p.is_dir():
            return StepResult(False, f"{path} is not a directory (resolved: {p})")
        files = [f.name for f in p.iterdir()]
        return StepResult(True, f"Files in {p}: " + ", ".join(files))
    except Exception as e:
        return StepResult(False, str(e))


@register_tool(
    name="read_file",
    description="Read the contents of a text or HTML file. Automatically extracts clean readable text from HTML files and handles large files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read."},
            "max_chars": {"type": "integer", "description": "Maximum characters to return (default: 50000)."},
            "offset": {"type": "integer", "description": "Character offset to start reading from (default: 0)."}
        },
        "required": ["path"]
    }
)
def tool_read_file(path: str, max_chars: int = 50000, offset: int = 0) -> StepResult:
    try:
        p = _resolve_path(path)
        if not p.is_file():
            return StepResult(False, f"File {path} does not exist (resolved: {p}).")
        
        raw_content = p.read_text(encoding="utf-8", errors="replace")
        
        # If HTML, clean scripts/styles/head to provide useful textual content
        if p.suffix.lower() in (".html", ".htm") or "<html" in raw_content[:1000].lower():
            try:
                soup = BeautifulSoup(raw_content, "html.parser")
                for s in soup(["script", "style", "head", "noscript", "svg"]):
                    s.decompose()
                clean_text = soup.get_text("\n", strip=True)
                if clean_text:
                    content = f"[HTML converted to clean text - {p.name}]\n" + clean_text
                else:
                    content = raw_content
            except Exception:
                content = raw_content
        else:
            content = raw_content

        total_len = len(content)
        if offset > 0:
            content = content[offset:]
        
        if len(content) > max_chars:
            content = (
                content[:max_chars] 
                + f"\n... [TRUNCATED - Showing {max_chars} chars from offset {offset}. Total length: {total_len} chars. Call read_file with offset={offset + max_chars} to read more.]"
            )
        return StepResult(True, content)
    except Exception as e:
        return StepResult(False, str(e))


@register_tool(
    name="search_file",
    description="Search for a text query or pattern inside a file (text, html, code, logs, csv) and retrieve matching lines, sections, or table rows with surrounding context.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to search in."},
            "query": {"type": "string", "description": "The search term or phrase to look for."},
            "context_chars": {"type": "integer", "description": "Characters of surrounding context to return around matches (default: 500)."}
        },
        "required": ["path", "query"]
    }
)
def tool_search_file(path: str, query: str, context_chars: int = 500) -> StepResult:
    try:
        p = _resolve_path(path)
        if not p.is_file():
            return StepResult(False, f"File {path} does not exist (resolved: {p}).")
        
        raw_content = p.read_text(encoding="utf-8", errors="replace")
        query_strip = query.strip()
        query_lower = query_strip.lower()
        query_words = [w.lower() for w in re.findall(r"\w+", query_strip) if len(w) > 2]

        # 1. Check if it's an HTML file with tables
        if p.suffix.lower() in (".html", ".htm") or "<table" in raw_content.lower():
            try:
                soup = BeautifulSoup(raw_content, "html.parser")
                # Look for table header
                headers = []
                for tr in soup.find_all("tr"):
                    texts = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                    if any(h in " ".join(texts).lower() for h in ["course", "id", "name", "subject", "date", "title", "exam", "s no"]):
                        headers = [t for t in texts if t and not t.isdigit()]
                        if headers:
                            break
                
                matched_rows = []
                for tr in soup.find_all("tr"):
                    row_text = tr.get_text(" ", strip=True)
                    row_lower = row_text.lower()
                    
                    matched = False
                    if query_lower in row_lower:
                        matched = True
                    elif query_words and all(w in row_lower for w in query_words):
                        matched = True
                    
                    if matched:
                        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                        if cells:
                            matched_rows.append(cells)
                
                if matched_rows:
                    output_lines = [f"Found {len(matched_rows)} matching table row(s) in {p.name}:"]
                    for idx, row in enumerate(matched_rows[:15], 1):
                        output_lines.append(f"\n--- Match {idx} ---")
                        if headers and len(headers) == len(row):
                            for h, val in zip(headers, row):
                                output_lines.append(f"{h}: {val}")
                        else:
                            output_lines.append(" | ".join(row))
                    return StepResult(True, "\n".join(output_lines))
            except Exception:
                pass  # Fall back to text search

        # 2. General text / line search
        lines = raw_content.splitlines()
        matched_results = []
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            matched = False
            if query_lower in line_lower:
                matched = True
            elif query_words and all(w in line_lower for w in query_words):
                matched = True
            
            if matched:
                if len(line) > 1000:
                    idx = line_lower.find(query_words[0] if query_words else query_lower)
                    if idx == -1:
                        idx = 0
                    snippet = line[max(0, idx - 200) : min(len(line), idx + 400)]
                    matched_results.append(f"Line {line_num} (snippet): {snippet}")
                else:
                    start_ctx = max(0, line_num - 2)
                    end_ctx = min(len(lines), line_num + 2)
                    ctx = "\n".join(f"  {lines[i]}" for i in range(start_ctx, end_ctx))
                    matched_results.append(f"Line {line_num}:\n{ctx}")
                
                if len(matched_results) >= 10:
                    break

        if matched_results:
            return StepResult(True, f"Found {len(matched_results)} match(es) in {p.name}:\n\n" + "\n\n".join(matched_results))
        
        return StepResult(False, f"No matches found for '{query}' in {p.name}.")
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
        p = _resolve_path(path)
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
        p = _resolve_path(path)
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


@register_tool(
    name="ocr_read_screen",
    description="Capture the screen and extract all visible text and UI element positions using fast, zero-latency, offline Windows OCR. Use this to read on-screen text, inspect dialogs, or verify visible UI state without cloud vision costs.",
    parameters={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Optional path to a specific image file to read. If omitted, captures the live screen."
            }
        }
    }
)
def tool_ocr_read_screen(image_path: str = "") -> StepResult:
    from scout.vision.ocr import ocr_image, ocr_screen

    if image_path and image_path.strip():
        result = ocr_image(image_path)
    else:
        result = ocr_screen()

    if not result.success:
        return StepResult(False, f"Windows OCR failed: {result.error}")

    return StepResult(True, result.to_formatted_text())


@register_tool(
    name="ocr_find_element",
    description="Locate a specific button, label, link, or text element on screen using native Windows OCR. Returns exact center coordinates (X, Y) and bounding box so you can immediately click or interact with it using the computer tool.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The exact or partial text of the button or UI element to find (e.g. 'Submit', 'Login', 'Cancel', 'Save', 'Next')."
            },
            "image_path": {
                "type": "string",
                "description": "Optional path to a specific image file to inspect. If omitted, captures the live screen."
            }
        },
        "required": ["text"]
    }
)
def tool_ocr_find_element(text: str, image_path: str = "") -> StepResult:
    from scout.vision.ocr import ocr_image, ocr_screen

    if not text or not text.strip():
        return StepResult(False, "No target text provided to find.")

    if image_path and image_path.strip():
        result = ocr_image(image_path)
    else:
        result = ocr_screen()

    if not result.success:
        return StepResult(False, f"Windows OCR failed: {result.error}")

    match = result.find_element(text)
    if not match:
        preview = [f"'{l.text}'" for l in result.lines[:8]]
        preview_text = ", ".join(preview) if preview else "no text detected"
        return StepResult(
            False,
            f"Element '{text}' was not found on screen. Visible text elements include: {preview_text}."
        )

    cx = match["center_x"]
    cy = match["center_y"]
    rect = match["rect"]
    matched_text = match["text"]
    match_type = match["type"]

    msg = (
        f"Found '{matched_text}' ({match_type}) on screen at center coordinates: ({cx}, {cy}).\n"
        f"Bounding box: x={rect['x']}, y={rect['y']}, width={rect['width']}, height={rect['height']}.\n"
        f"To click this element, use: computer(action='click', x={cx}, y={cy})."
    )
    return StepResult(True, msg)


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


@register_tool(
    name="search_emails",
    description="Search for emails in the user's Gmail inbox. Supports filtering by unread status, sender, subject, or query keywords. Returns a list of matching emails with their IDs, subjects, senders, and dates.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional search term or keyword to find in email text."
            },
            "unread_only": {
                "type": "boolean",
                "description": "If true, only returns unread (unseen) emails."
            },
            "sender": {
                "type": "string",
                "description": "Optional sender email address or name to filter by."
            },
            "subject": {
                "type": "string",
                "description": "Optional subject keyword to filter by."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of emails to retrieve (default is 5, max 20)."
            },
            "folder": {
                "type": "string",
                "description": "IMAP mailbox folder to search (default is 'INBOX')."
            }
        }
    }
)
def tool_search_emails(
    query: str | None = None,
    unread_only: bool = False,
    sender: str | None = None,
    subject: str | None = None,
    limit: int = 5,
    folder: str = "INBOX",
) -> StepResult:
    import json
    try:
        from scout.mail.client import search_emails
        results = search_emails(
            query=query,
            unread_only=unread_only,
            sender=sender,
            subject=subject,
            limit=min(limit, 20),
            folder=folder,
        )
        if not results:
            crit = []
            if unread_only: crit.append("unread")
            if sender: crit.append(f"from '{sender}'")
            if subject: crit.append(f"subject '{subject}'")
            if query: crit.append(f"containing '{query}'")
            desc = " (" + ", ".join(crit) + ")" if crit else ""
            return StepResult(True, f"No emails found in {folder}{desc}.")

        summary_lines = [f"Found {len(results)} email(s) in {folder}:"]
        for email_info in results:
            unread_tag = " [UNREAD]" if email_info.get("unread") else ""
            summary_lines.append(
                f"- [ID: {email_info['id']}]{unread_tag} From: {email_info['from']} | "
                f"Subject: {email_info['subject']} | Date: {email_info['date']}"
            )
        return StepResult(True, "\n".join(summary_lines))
    except Exception as e:
        return StepResult(False, f"Email search failed: {e}")


@register_tool(
    name="read_email",
    description="Read the full body text and headers of a specific email by its ID.",
    parameters={
        "type": "object",
        "properties": {
            "email_id": {
                "type": "string",
                "description": "The ID of the email to read (obtained from search_emails)."
            },
            "folder": {
                "type": "string",
                "description": "The IMAP mailbox folder containing the email (default is 'INBOX')."
            }
        },
        "required": ["email_id"]
    }
)
def tool_read_email(email_id: str, folder: str = "INBOX") -> StepResult:
    try:
        from scout.mail.client import read_email
        data = read_email(email_id=email_id, folder=folder)

        lines = [
            f"**Subject:** {data['subject']}",
            f"**From:** {data['from']}",
            f"**To:** {data.get('to', '')}",
            f"**Date:** {data.get('date', '')}",
        ]
        if data.get("attachments"):
            lines.append(f"**Attachments:** {', '.join(data['attachments'])}")
        lines.append("\n**Body:**\n" + data.get("body", "(Empty body)"))

        return StepResult(True, "\n".join(lines))
    except Exception as e:
        return StepResult(False, f"Failed to read email {email_id}: {e}")


@register_tool(
    name="adb_command",
    description=(
        "Execute an Android Debug Bridge (ADB) command to interact with, control, or inspect the user's connected Android phone/device. "
        "Supports any ADB command (e.g. 'devices', 'shell dumpsys battery', 'shell input tap <x> <y>', 'shell input text <string>', "
        "'shell input keyevent <keycode>', 'shell monkey -p <package> 1', 'shell am start ...', 'shell screencap -p /sdcard/s.png', 'pull ...'). "
        "The leading 'adb ' is optional and added automatically if omitted."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The ADB sub-command or shell command to run (e.g. 'devices', 'shell dumpsys battery', 'shell input tap 500 1000', 'shell am start -a android.media.action.STILL_IMAGE_CAMERA', 'shell monkey -p com.whatsapp 1')."
            },
            "device_id": {
                "type": "string",
                "description": "Optional specific device ID/serial if multiple Android devices are connected."
            }
        },
        "required": ["command"]
    }
)
def tool_adb_command(command: str, device_id: str | None = None) -> StepResult:
    import shutil
    import subprocess
    import shlex

    adb_bin = shutil.which("adb")
    if not adb_bin:
        for candidate in [
            r"C:\platform-tools\adb.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        ]:
            if os.path.exists(candidate):
                adb_bin = candidate
                break

    if not adb_bin:
        return StepResult(False, "ADB binary ('adb.exe') not found. Please install Android platform-tools or add adb to your PATH.")

    clean_cmd = command.strip()
    if clean_cmd.lower().startswith("adb.exe "):
        clean_cmd = clean_cmd[8:].strip()
    elif clean_cmd.lower().startswith("adb "):
        clean_cmd = clean_cmd[4:].strip()

    args = [adb_bin]
    if device_id:
        args.extend(["-s", device_id.strip()])

    try:
        sub_args = shlex.split(clean_cmd, posix=False)
    except Exception:
        sub_args = clean_cmd.split()

    full_args = args + sub_args

    try:
        proc = subprocess.run(
            full_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if proc.returncode != 0:
            err_msg = stderr or stdout or f"Command failed with exit code {proc.returncode}"
            return StepResult(False, f"ADB error: {err_msg}")

        output = stdout or stderr or "Command executed successfully (no output)."
        return StepResult(True, output)
    except subprocess.TimeoutExpired:
        return StepResult(False, "ADB command timed out after 25 seconds.")
    except Exception as e:
        return StepResult(False, f"Failed to execute ADB command: {e}")



