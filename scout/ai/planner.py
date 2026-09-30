"""The Planner agent, responsible for high-level reasoning and generating an execution plan."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from scout.ai.provider import AIProvider

console = Console()

PLANNER_PROMPT = """You are Scout Planner, the high-level reasoning engine for a Windows computer automation agent.
Your objective is to take the user's ambiguous request and translate it into a strict, step-by-step execution plan.
You have access to a single tool: `submit_plan`. You MUST use this tool to output your plan.

# Available Execution Tools (for your reference)
The execution agent (which will receive your plan) has access to the following tools:
- computer(action: str, [title: str], [text: str], [x: int], [y: int], [hotkey: str]) - Controls mouse, keyboard, and windows.
- list_windows() - Returns a list of all visible window titles.
- list_files(directory: str) - Lists files in a directory.
- read_file(path: str) - Reads the contents of a file.
- write_file(path: str, content: str) - Creates or overwrites a file.
- run_command(command: str) - Executes a PowerShell command.
- verify_screen(expected_state: str) - Captures a screenshot and visually verifies if the expected state is true.

# Planning Rules
1. Break down the user's objective into a logical sequence of discrete steps.
2. The executor agent is "blind" by default and only follows your instructions. You must instruct it to verify its state (e.g., using `list_windows`, `verify_screen`, or `run_command` to check output) if needed.
3. Keep the plan as simple and linear as possible.
4. Output the plan by calling `submit_plan` with a list of step descriptions. Be highly specific in your descriptions (e.g., "Open notepad using run_command", "Type 'hello world' using computer type_text").

Example of a good plan step: "Use run_command to execute 'start notepad'. Then use computer to activate the 'Untitled - Notepad' window."
"""

def get_planner_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "submit_plan",
                "description": "Submit the finalized step-by-step execution plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "description": "A specific, actionable step for the executor."
                            },
                            "description": "The sequential list of steps to execute."
                        }
                    },
                    "required": ["steps"]
                }
            }
        }
    ]

class Planner:
    def __init__(self, provider: AIProvider):
        self.provider = provider
        
    def generate_plan(self, request: str, memory_context: str = "") -> list[str]:
        """Generate a plan from the user's request."""
        system_prompt = PLANNER_PROMPT
        if memory_context:
            system_prompt += f"\n\n# Relevant Context/Memory\n{memory_context}"
            
        messages = [{"role": "user", "content": request}]
        tools = get_planner_tools()
        
        try:
            with console.status(f"[dim]Planner ({self.provider.__class__.__name__}) is generating execution plan...[/dim]"):
                response = self.provider.chat_completion(system_prompt, messages, tools)
            choice = response.get("choices", [{}])[0].get("message", {})
            
            tool_calls = choice.get("tool_calls", [])
            for call in tool_calls:
                if call.get("function", {}).get("name") == "submit_plan":
                    args = call["function"]["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            console.print("[red]Planner returned invalid JSON for the plan.[/]")
                            return []
                    return args.get("steps", [])
                    
            # If no tool call, maybe the model just outputted text. We could parse it, but for now:
            console.print("[yellow]Planner did not use the submit_plan tool. Falling back to treating its response as a single step.[/yellow]")
            return [choice.get("content", "")]
            
        except Exception as e:
            console.print(f"[red]Planner failed:[/] {e}")
            return []
