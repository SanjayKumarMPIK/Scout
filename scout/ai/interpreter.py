"""AI interpreter and autonomous agent loop."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.prompt import Confirm

from scout.ai.provider import AIProvider
from scout.ai.tools import get_tools, execute_tool

console = Console()

# ── Risk levels ────────────────────────────────────────────────────────

SAFE = {"computer", "list_windows", "get_active_window", "find_window", "minimize_window", "maximize_window", "list_files", "read_file", "system_info", "project_info", "git_status", "git_log", "git_branch", "open_application", "open_url", "project_open", "complete_task", "verify_screen"}
CONFIRM = {"close_window", "run_command", "project_run", "git_pull", "git_commit", "write_file", "create_directory", "change_directory"}
HIGH_RISK = {"git_push"}

def _get_risk_level(action_type: str) -> str:
    if action_type in SAFE:
        return "SAFE"
    if action_type in HIGH_RISK:
        return "HIGH_RISK"
    return "CONFIRM"

SYSTEM_PROMPT = """You are Scout, a Windows computer automation agent.
You have access to a set of tools to control the computer, read files, and execute commands.
Your objective is to fulfill the user's request.

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
16. UNIFIED COMPUTER CONTROL: Use the single `computer` tool for all desktop UI actions (screenshot, click, double_click, move, drag, type, key, hotkey, scroll, activate_window). When combining this with vision, use: `computer({action: "screenshot"})` -> Vision provider -> `computer({action: "click", x: ..., y: ...})`.
"""

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

    def _run_loop(self) -> None:
        max_iterations = 15
        invalid_response_retries = 0
        tools = get_tools()

        console.print("[dim]Scout: AI agent online.[/dim]")

        try:
            for _ in range(max_iterations):
                with console.status("[bold cyan]AI is thinking...[/]"):
                    try:
                        response = self.provider.chat_completion(self.system_prompt, self.messages, tools=tools)
                    except Exception as e:
                        console.print(f"[red]Error communicating with AI:[/] {e}")
                        return

                choice = response.get("choices", [{}])[0].get("message", {})
                
                if not choice:
                    choice = {"role": "assistant"}
                elif "role" not in choice:
                    choice["role"] = "assistant"

                # Sanitize content: OpenRouter/Nvidia complains if content is null
                if choice.get("content") is None:
                    choice["content"] = ""
                    
                self.messages.append(choice)

                if choice.get("content"):
                    content = choice["content"].strip()
                    if content:
                        console.print(f"\n[bold cyan]Scout:[/] {content}")
                        if not choice.get("tool_calls"):
                            return  # End of turn

                tool_calls = choice.get("tool_calls", [])
                if not tool_calls:
                    # No tools called and no content? Break.
                    break

                # Filter out premature complete_task calls if accompanied by other tools
                if any(tc["function"]["name"] == "complete_task" for tc in tool_calls) and len(tool_calls) > 1:
                    tool_calls = [tc for tc in tool_calls if tc["function"]["name"] != "complete_task"]
                    console.print("\n[dim]Intercepted premature complete_task. Forcing observation of results...[/dim]")

                # Handle tool calls
                for i, tool_call in enumerate(tool_calls):
                    func_name = tool_call["function"]["name"]
                    args_str = tool_call["function"]["arguments"]
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}

                    console.print(f"\n[bold yellow][TOOL][/] {func_name}({args_str})")

                    if func_name == "complete_task":
                        # Special exit tool
                        msg = args.get("response", "Task completed.")
                        console.print(f"\n[bold cyan]Scout:[/] {msg}")
                        # Add result back to messages to satisfy API expectations
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", "0"),
                            "name": func_name,
                            "content": "Task completed successfully."
                        })
                        return

                    # Check safety
                    risk = _get_risk_level(func_name)
                    proceed = True
                    
                    # Check command safety
                    if func_name == "run_command":
                        cmd = args.get("command", "")
                        from scout.core.safety import is_destructive
                        if is_destructive(cmd):
                            risk = "HIGH_RISK"

                    if risk == "HIGH_RISK":
                        proceed = Confirm.ask(f"[bold red]Allow HIGH RISK action '{func_name}'?[/]", default=False)
                    elif risk == "CONFIRM":
                        proceed = Confirm.ask(f"[yellow]Allow action '{func_name}'?[/]", default=True)

                    if not proceed:
                        console.print("\n[yellow]AI action cancelled by user.[/yellow]")
                        # Cleanup the rest of the pending tool calls
                        for pending_tc in tool_calls[i:]:
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": pending_tc.get("id", "0"),
                                "name": pending_tc["function"]["name"],
                                "content": "ERROR: Action cancelled by user."
                            })
                        return

                    # Execute
                    result = execute_tool(func_name, args)
                    if result.success:
                        console.print(f"[green][RESULT] success:[/green] {result.message}")
                    else:
                        console.print(f"[red][RESULT] failed:[/red] {result.message}")

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "0"),
                        "name": func_name,
                        "content": result.message if result.success else f"ERROR: {result.message}"
                    })

            else:
                console.print("[red]Agent reached maximum iterations without completing the task.[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]AI action cancelled by user.[/yellow]")
            # Cleanup dangling tool calls to keep API history valid
            if self.messages and self.messages[-1].get("tool_calls"):
                for tc in self.messages[-1]["tool_calls"]:
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "0"),
                        "name": tc["function"]["name"],
                        "content": "ERROR: Execution interrupted by user."
                    })
            return


