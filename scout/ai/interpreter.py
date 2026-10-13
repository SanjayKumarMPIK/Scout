"""AI interpreter and autonomous agent loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

from scout.ai.provider import AIProvider
from scout.ai.tools import get_tools, execute_tool

console = Console()

# ── Risk levels ────────────────────────────────────────────────────────

SAFE = {
    "computer", "list_windows", "get_active_window", "find_window", "minimize_window",
    "maximize_window", "list_files", "read_file", "system_info", "project_info",
    "git_status", "git_log", "git_branch", "open_application", "open_url",
    "project_open", "complete_task", "verify_screen", "analyze_screen",
    "web_search", "fetch_webpage", "browser_navigate", "browser_extract", "browser_close",
}
CONFIRM = {
    "close_window", "run_command", "project_run", "git_pull", "git_commit",
    "write_file", "create_directory", "change_directory", "browser_interact",
}
HIGH_RISK = {"git_push"}

def _get_risk_level(action_type: str) -> str:
    if action_type in SAFE:
        return "SAFE"
    if action_type in HIGH_RISK:
        return "HIGH_RISK"
    return "CONFIRM"

SYSTEM_PROMPT = """You are Scout, a VERY FRIENDLY AND CHILL Windows computer automation agent.
You have access to a set of tools to control the computer, read files, and execute commands.
Your objective is to fulfill the user's request.

REMEMBER: You are a very friendly, helpful, direct, and highly efficient agent. Always address the user as "sir" and always have a fun vibe with a fun slang.
REMEMBER: YOU SHOULD NOT START EVERY REPLY WITH A GREETING (like "Hey there, sir", or "Hello there, sir"). ONLY WHENT THE USER IS GREETING YOU, YOU HAVE TO GREET THEM BACK.
YOU HAVE A VOICE COMMAND TOOL, IF A USER ASKS ABOUT IT, YOU MUST REPLY POSITIVELY ABOUT THE VOICE COMMANDS. THE COMMAND TO ENABLE VOICE IS "/voice".
# Modes
- mode="respond": no computer actions are needed - greetings, general knowledge, questions answerable from the
  memory/context below, or requests that are TRULY impossible with the available tools. Put the complete answer for
  the user in the `response` parameter.
- mode="execute": you need to perform computer actions. The `response` parameter is ignored.

# Rules
1. ALWAYS inspect tool results. If a tool fails, try a different approach.
2. NEVER pretend an action succeeded if it did not.
3. DO NOT output conversational filler or explain your plans. Generating text takes time; ONLY output the JSON tool calls unless you are responding to a conversational greeting.
4. When you have successfully completed the user's objective, call the `complete_task` tool with a summary response.
5. NEVER call `complete_task` in the same turn as other tools. You must wait to observe the results of your actions first.
6. Before calling `complete_task`, validate that:
   - A task-relevant action actually occurred and succeeded.
   - You are not claiming success for a UI operation (like search or submit) merely because typing/clicking succeeded. Use `verify_screen` to visually confirm important UI changes.
   - If visual verification is impossible, mark the task as "unverified" rather than falsely claiming verified success.
7. Computer actions must be performed in the correct target application. Before keyboard or mouse actions, determine the relevant target window. If the target is not active, use `computer({action: 'activate_window', title: '...'})` and verify it before interacting.
8. Never assume the terminal is the intended target.
9. Maintain the current task's target application/window across turns unless the user explicitly switches applications.
10. DO NOT output XML tags like <tool_response>. If a task fails, reason about it and perform a corrective action using registered tools.
11. CONVERSATION VS ACTION: If the user says a simple greeting (like "Hello", "Hi", "How are you?"), DO NOT call any tools. Just respond with normal plain text (e.g. "Hello! How can I help you?"). ONLY use tools if the user actually asks you to do something, check something, or get information.
12. PREFER HEADLESS TOOLS: If you need to create, read, or edit a file (especially writing code), ALWAYS use `write_file`, `read_file`, or `run_command`. NEVER use UI automation (like opening Notepad and typing) to create files unless explicitly requested. UI automation is slow and brittle.
13. WINDOWS ENVIRONMENT: You are running on Windows. When using `run_command`, you MUST use valid Windows command prompt or PowerShell syntax (e.g., use `move` instead of `mv`, `copy` instead of `cp`, `dir` instead of `ls`).
14. SCREEN VERIFICATION: Do not verify trivial headless actions (like reading a file). Only use `verify_screen` for high-value visual changes (opening apps, navigating browsers, checking UI state after a click).
15. DO NOT INSTRUCT THE USER: NEVER tell the user how to do something manually (e.g. "Please open Task Manager"). You are an automation agent. You must execute the necessary tools yourself to fulfill the request. If you don't know how to do it, say so, but do not give the user instructions to perform the task manually.
16. UNIFIED COMPUTER CONTROL: Use the single `computer` tool for all desktop UI actions (screenshot, click, double_click, move, drag, type, key, hotkey, scroll, activate_window). When combining this with vision, use: `analyze_screen` to find coordinates or information, then use `computer({action: "click", x: ..., y: ...})` to interact.
17. DANGEROUS ACTION PREVENTION: NEVER use destructive keyboard/mouse actions (like `Ctrl+A`, `Delete`, `Ctrl+C`) to "read", "check", or "test" the state of an application or document. To extract information visually, you MUST use `analyze_screen` or `verify_screen`.
18. MOBILE DEVICE AUTOMATION: While you are a Windows agent, you CAN control connected Android devices by running `adb` commands via the `run_command` tool (e.g., `adb shell input tap x y`, `adb shell input text ...`, `adb shell am start ...`). DO NOT claim you cannot control a phone if the user asks you to interact with one. Assume `adb` is available and formulate the necessary commands.
"""

# Appended to SYSTEM_PROMPT when the executor runs a planner-generated plan.
EXECUTOR_PROMPT = SYSTEM_PROMPT + """
# PLAN EXECUTION MODE (overrides rules 4-6 and 11)
You are the EXECUTOR. A planner has already decided what to do. You receive the plan ONE STEP AT A TIME.
- Execute ONLY the current step, exactly as written. Do not skip it, merge it with other steps, reorder, or add extra actions.
- Use ONLY the tools offered for the current step.
- When the step is finished, call `step_done` with the FULL, detailed result of the step (include ALL exact data, observations, or text obtained so the planner can see them). Do not summarize away important details.
- If the step cannot be completed after a reasonable corrective attempt, call `step_failed` with the reason. Never fake success.
- Never call `step_done`/`step_failed` in the same response as other tools - observe the results first.
- Do not write prose while executing steps; only make tool calls.
"""

# Control tools offered only while executing a plan step.
_STEP_CONTROL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "step_done",
            "description": "Report that the CURRENT plan step is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "description": "The complete, detailed result of this step. Include all extracted data and full observations; do not summarize."}
                },
                "required": ["result"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "step_failed",
            "description": "Report that the CURRENT plan step cannot be completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why the step failed."}
                },
                "required": ["reason"],
            },
        },
    },
]
_CONTROL_NAMES = {"step_done", "step_failed", "complete_task"}


@dataclass
class StepOutcome:
    status: str  # "done" | "failed" | "cancelled"
    result: str


class _Cancelled(Exception):
    """Raised when the user declines a tool confirmation."""


def _print_response(text: str) -> None:
    from scout.ui.chat import print_scout_message
    if not text:
        return
    print_scout_message(text)
    
    try:
        import scout.commands.ai_cmd as ai_cmd
        if getattr(ai_cmd, "_voice_mode", False):
            from scout.voice.tts import speak
            speak(text)
    except ImportError:
        pass


class AIInterpreter:
    def __init__(self, provider: AIProvider, system_prompt: str = SYSTEM_PROMPT):
        self.provider = provider
        self.messages: list[dict[str, Any]] = []
        self.system_prompt = system_prompt

    def _inject_memory(self, request: str) -> None:
        from scout.memory.store import get_memory_store
        mem_store = get_memory_store()
        mem_block = mem_store.get_relevant_memories(request)
        
        if mem_block:
            # We wrap the user's request with the memory context
            request = f"{mem_block}\n\nUSER REQUEST:\n{request}"
            
        self.messages.append({"role": "user", "content": request})

    def ask(self, request: str) -> None:
        self.messages = []
        self._inject_memory(request)
        self._run_loop()

    def chat_turn(self, request: str) -> None:
        self._inject_memory(request)
        self._run_loop()

    # ── Shared helpers ─────────────────────────────────────────────────

    def _completion(self, tools: list[dict], status: str = "Neural core processing...") -> dict:
        """Call the provider and append the (sanitized) assistant message to history."""
        from scout.ui.activity import scout_activity
        with scout_activity("Neural core processing...", "thinking"):
            response = self.provider.chat_completion(self.system_prompt, self.messages, tools=tools)

        choice = response.get("choices", [{}])[0].get("message", {})
        if not choice:
            choice = {"role": "assistant"}
        elif "role" not in choice:
            choice["role"] = "assistant"

        # Sanitize content: OpenRouter/Nvidia complains if content is null
        if choice.get("content") is None:
            choice["content"] = ""

        self.messages.append(choice)
        return choice

    def _add_tool_result(self, tool_call: dict, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call.get("id", "0"),
            "name": tool_call["function"]["name"],
            "content": content,
        })

    def _close_pending(self, tool_calls: list[dict], content: str) -> None:
        """Give every unanswered tool call a result so the API history stays valid."""
        answered = {m.get("tool_call_id") for m in self.messages if m.get("role") == "tool"}
        for tc in tool_calls:
            if tc.get("id", "0") not in answered:
                self._add_tool_result(tc, content)

    @staticmethod
    def _parse_args(tool_call: dict) -> tuple[dict, str]:
        args_str = tool_call["function"].get("arguments", "")
        if isinstance(args_str, dict):
            return args_str, json.dumps(args_str)
        try:
            return json.loads(args_str or "{}"), args_str
        except json.JSONDecodeError:
            return {}, args_str

    @staticmethod
    def _format_action_summary(func_name: str, args: dict) -> tuple[str, str]:
        """Return (summary_for_status, detail_for_confirmation_and_output)."""
        if func_name == "run_command":
            cmd = str(args.get("command") or "").strip()
            return (f"run_command › {cmd}" if cmd else "run_command", cmd)
        elif func_name in ("write_file", "read_file", "create_directory"):
            path = str(args.get("path") or "").strip()
            return (f"{func_name} › {path}" if path else func_name, path)
        elif func_name == "open_application":
            app = str(args.get("name") or args.get("path") or "").strip()
            return (f"open_application › {app}" if app else func_name, app)
        elif func_name == "open_url":
            url = str(args.get("url") or "").strip()
            return (f"open_url › {url}" if url else func_name, url)
        elif func_name == "computer":
            action = str(args.get("action") or "").strip()
            if action in ("click", "double_click", "move"):
                detail = f"{action} at ({args.get('x', '?')}, {args.get('y', '?')})"
            elif action == "type":
                txt = str(args.get("text") or "")
                detail = f'type "{txt[:40]}..."' if len(txt) > 40 else f'type "{txt}"'
            elif action in ("key", "hotkey"):
                detail = f"{action} {args.get('key') or args.get('keys', '')}"
            elif action == "activate_window":
                detail = f"activate window '{args.get('title', '')}'"
            else:
                detail = action
            return (f"computer › {detail}", detail)
        elif func_name in ("verify_screen", "analyze_screen"):
            prompt = str(args.get("prompt") or "").strip()
            trunc = f"{prompt[:40]}..." if len(prompt) > 40 else prompt
            return (f"{func_name} › {trunc}" if prompt else func_name, prompt)
        elif func_name == "web_search":
            queries = args.get("queries") or args.get("query") or ""
            q_text = ", ".join(queries) if isinstance(queries, list) else str(queries)
            return (f"web_search › {q_text[:40]}", q_text)
        elif func_name == "fetch_webpage":
            url = str(args.get("url") or "")
            return (f"fetch_webpage › {url[:40]}", url)
        elif func_name == "browser_navigate":
            url = str(args.get("url") or "")
            return (f"browser_navigate › {url[:40]}", url)
        elif func_name == "browser_extract":
            ext_type = str(args.get("extract_type") or "all")
            sel = str(args.get("selector") or "")
            detail = f"{ext_type} ({sel})" if sel else ext_type
            return (f"browser_extract › {detail}", detail)
        elif func_name == "browser_interact":
            act = str(args.get("action") or "")
            target = str(args.get("selector") or args.get("text") or args.get("direction") or "")
            detail = f"{act} on {target}" if target else act
            return (f"browser_interact › {detail}", detail)
        else:
            if args:
                first_val = next(iter(args.values()), None)
                if isinstance(first_val, str) and first_val:
                    return (f"{func_name} › {first_val[:40]}", first_val)
            return (func_name, "")

    def _run_tool(self, tool_call: dict) -> None:
        """Display, safety-check, execute one tool call and record its result.

        Raises _Cancelled if the user declines a confirmation.
        """
        from rich.panel import Panel

        func_name = tool_call["function"]["name"]
        args, args_str = self._parse_args(tool_call)

        summary, detail = self._format_action_summary(func_name, args)

        from scout.ui.chat import print_scout_status
        tool_state = "verifying" if func_name in ("verify_screen", "analyze_screen") else "executing"
        print_scout_status(f"Running {summary}...", tool_state)

        # Check safety
        risk = _get_risk_level(func_name)

        # Check command safety
        if func_name == "run_command":
            from scout.core.safety import is_destructive
            if is_destructive(args.get("command", "")):
                risk = "HIGH_RISK"
        elif func_name == "browser_interact":
            if args.get("action") in ("scroll", "wait"):
                risk = "SAFE"
            else:
                risk = "CONFIRM"


        # IMPORTANT: Before prompting the user (which steals focus to the terminal),
        # capture the current active window (e.g. a Save As dialog that opened recently)
        # and update the target manager, so we can restore focus to it after approval!
        from scout.ai.window_manager import get_active_window, get_target_window_manager
        active_win = get_active_window()
        if active_win and active_win.get("handle"):
            title = active_win.get("title", "")
            if "Scout" not in title and "Windows PowerShell" not in title and "Command Prompt" not in title:
                get_target_window_manager().set_target(active_win["handle"], title)

        proceed = True
        if risk == "HIGH_RISK":
            prompt = (
                f"\n  [bold red]⚠️  Allow HIGH RISK action '{func_name}'?[/]\n"
                f"  [bold red]Target:[/]  [bold white]{escape(detail or summary)}[/]\n"
                f"  [dim red]Authorize HIGH RISK execution?[/dim red]"
            )
            proceed = Confirm.ask(prompt, default=False)
        elif risk == "CONFIRM":
            if func_name == "run_command":
                prompt = (
                    f"\n  [bold yellow]Allow command execution?[/]\n"
                    f"  [bold cyan]Command:[/] [bold white]{escape(detail)}[/]\n"
                    f"  [dim]Authorize command?[/dim]"
                )
            elif detail:
                prompt = (
                    f"\n  [bold yellow]Allow action '{func_name}'?[/]\n"
                    f"  [bold cyan]Target:[/] [bold white]{escape(detail)}[/]\n"
                    f"  [dim]Authorize?[/dim]"
                )
            else:
                prompt = f"\n  [yellow]Allow action '{func_name}'?[/]"
            proceed = Confirm.ask(prompt, default=True)

        if not proceed:
            raise _Cancelled()
        console.print()

        # Execute
        result = execute_tool(func_name, args)
        if result.success:
            print_scout_status(f"Completed {summary}", "success")
            if func_name == "run_command" and result.message.strip():
                from scout.ui.chat import print_command_output
                print_command_output(detail, result.message)
        else:
            from scout.ui.chat import print_scout_error
            print_scout_error(f"{func_name} failed: {result.message}")

        self._add_tool_result(tool_call, result.message if result.success else f"ERROR: {result.message}")

    # ── Free-form agent loop (single-model mode) ───────────────────────

    def _run_loop(self) -> None:
        max_iterations = 15
        tools = get_tools()

        try:
            for _ in range(max_iterations):
                try:
                    choice = self._completion(tools)
                except Exception as e:
                    console.print(f"[red]Error communicating with AI:[/] {escape(str(e))}")
                    return

                content = (choice.get("content") or "").strip()
                tool_calls = choice.get("tool_calls") or []

                if content:
                    _print_response(content)
                    if not tool_calls:
                        return  # End of turn

                if not tool_calls:
                    # No tools called and no content? Break.
                    break

                # Filter out premature complete_task calls if accompanied by other tools
                if any(tc["function"]["name"] == "complete_task" for tc in tool_calls) and len(tool_calls) > 1:
                    for tc in tool_calls:
                        if tc["function"]["name"] == "complete_task":
                            self._add_tool_result(tc, "Ignored: observe the results of your other actions first.")
                    tool_calls = [tc for tc in tool_calls if tc["function"]["name"] != "complete_task"]
                    console.print("\n[dim]Intercepted premature complete_task. Forcing observation of results...[/dim]")

                # Handle tool calls
                for tool_call in tool_calls:
                    if tool_call["function"]["name"] == "complete_task":
                        # Special exit tool
                        args, _ = self._parse_args(tool_call)
                        _print_response(args.get("response", "Task completed."))
                        # Add result back to messages to satisfy API expectations
                        self._add_tool_result(tool_call, "Task completed successfully.")
                        return

                    try:
                        self._run_tool(tool_call)
                    except _Cancelled:
                        console.print("\n[yellow]AI action cancelled by user.[/yellow]")
                        # Cleanup the rest of the pending tool calls
                        self._close_pending(tool_calls, "ERROR: Action cancelled by user.")
                        return

            else:
                console.print("[red]Agent reached maximum iterations without completing the task.[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]AI action cancelled by user.[/yellow]")
            # Cleanup dangling tool calls to keep API history valid
            if self.messages and self.messages[-1].get("tool_calls"):
                self._close_pending(self.messages[-1]["tool_calls"], "ERROR: Execution interrupted by user.")
            return

    # ── Plan execution (planner/executor mode) ─────────────────────────

    def begin_task(self, request: str, total_steps: int) -> None:
        """Record the user's request before executing a plan step by step."""
        self._inject_memory(request)
        self.messages[-1]["content"] += (
            f"\n\n(A planner produced a {total_steps}-step plan for this request. "
            "You will receive the steps one at a time.)"
        )

    def run_step(self, number: int, total: int, description: str, allowed: list[str], history: list[tuple[Any, str, str]] = None, max_iterations: int = 8) -> StepOutcome:
        """Execute exactly one plan step, restricted to the tools the planner assigned."""
        from scout.ai.tools import get_tools
        
        all_tools = [t for t in get_tools() if t["function"]["name"] != "complete_task"]
        if allowed:
            step_tools = [t for t in all_tools if t["function"]["name"] in allowed]
        else:
            step_tools = all_tools
        allowed_names = {t["function"]["name"] for t in step_tools}
        tools = step_tools + _STEP_CONTROL_TOOLS

        names_text = ", ".join(sorted(allowed_names))
        
        history_text = ""
        if history:
            history_text = "Results of previous steps:\n"
            for i, (h_step, h_status, h_result) in enumerate(history, 1):
                history_text += f"{i}. [{h_status.upper()}] {h_step.description}\n   Result: {h_result}\n"
            history_text += "\n"

        self.messages.append({
            "role": "user",
            "content": (
                f"PLAN STEP {number}/{total}: {description}\n\n"
                f"{history_text}"
                f"Allowed tools for this step: {names_text}.\n"
                "Execute exactly this step - nothing from other steps, nothing extra. "
                "When it is finished call `step_done` with the result; if it cannot be done call `step_failed`."
            ),
        })

        nudged = False
        try:
            for _ in range(max_iterations):
                try:
                    choice = self._completion(tools, status=f"[bold cyan]Executing step {number}/{total}...[/]")
                except Exception as e:
                    return StepOutcome("failed", f"AI error: {e}")

                tool_calls = choice.get("tool_calls") or []
                content = (choice.get("content") or "").strip()

                if not tool_calls:
                    if not nudged:
                        nudged = True
                        self.messages.append({
                            "role": "user",
                            "content": "Respond only with tool calls: perform the step, or call `step_done` / `step_failed`.",
                        })
                        continue
                    # Model insists on prose - treat it as the step's result.
                    return StepOutcome("done", content or "No result reported.")

                control = [tc for tc in tool_calls if tc["function"]["name"] in _CONTROL_NAMES]
                actions = [tc for tc in tool_calls if tc["function"]["name"] not in _CONTROL_NAMES]

                for tc in actions:
                    name = tc["function"]["name"]
                    if name not in allowed_names:
                        console.print(f"[dim]Blocked '{name}': not part of step {number}.[/dim]")
                        self._add_tool_result(tc, f"ERROR: '{name}' is not allowed for this step. Allowed tools: {names_text}.")
                        continue
                    self._run_tool(tc)

                if control:
                    if actions:
                        # Premature: must observe the action results first.
                        for tc in control:
                            self._add_tool_result(tc, "Ignored: observe the results of your actions before reporting.")
                        continue
                    tc = control[0]
                    for extra in control[1:]:
                        self._add_tool_result(extra, "Ignored.")
                    args, _ = self._parse_args(tc)
                    name = tc["function"]["name"]
                    if name == "step_failed":
                        reason = str(args.get("reason") or "No reason given.")
                        self._add_tool_result(tc, "Step marked as failed.")
                        return StepOutcome("failed", reason)
                    result = str(args.get("result") or args.get("response") or "Done.")
                    self._add_tool_result(tc, "Step marked as done.")
                    return StepOutcome("done", result)

            return StepOutcome("failed", f"Step did not finish within {max_iterations} attempts.")

        except _Cancelled:
            self._close_pending(self.messages[-1].get("tool_calls") or [], "ERROR: Action cancelled by user.")
            return StepOutcome("cancelled", "Cancelled by user.")
        except KeyboardInterrupt:
            last = next((m for m in reversed(self.messages) if m.get("role") == "assistant"), {})
            self._close_pending(last.get("tool_calls") or [], "ERROR: Execution interrupted by user.")
            return StepOutcome("cancelled", "Interrupted by user.")

    def finalize(self, request: str, report: str) -> None:
        """Write the final answer from the step results. No further actions are allowed."""
        complete_tool = [t for t in get_tools() if t["function"]["name"] == "complete_task"]
        self.messages.append({
            "role": "user",
            "content": (
                f"The plan has finished. Step results:\n{report}\n\n"
                f"Now call `complete_task` with the final response to the original request: \"{request}\".\n"
                "CRITICAL VERBOSITY RULE: If the request asks for an analysis, description, summary, or data extraction (e.g., 'What am I looking at?', 'Summarize this file', 'Find the errors'), your final response MUST be highly detailed and include all relevant information from the step results. Do not truncate or over-summarize.\n"
                "If the request was just a simple action (e.g., 'Open notepad', 'Click the button'), keep the response short and concise.\n"
                "Base it ONLY on the step results above; clearly state anything that failed. Do not perform new actions."
            ),
        })
        try:
            choice = self._completion(complete_tool, status="[bold cyan]Summarizing...[/]")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Error communicating with AI:[/] {escape(str(e))}")
            _print_response(report)
            return report

        text = (choice.get("content") or "").strip()
        for tc in choice.get("tool_calls") or []:
            if tc["function"]["name"] == "complete_task" and not text:
                args, _ = self._parse_args(tc)
                text = str(args.get("response") or "").strip()
            self._add_tool_result(tc, "Task completed successfully.")
        final_answer = text or report
        _print_response(final_answer)
        return final_answer

