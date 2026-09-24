"""AI interpreter and execution loop."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.prompt import Confirm

from scout.ai.context import gather_context
from scout.ai.prompts import SYSTEM_PROMPT
from scout.ai.provider import AIProvider
from scout.ai.schemas import AIAction, AIPlan, parse_and_validate_plan
from scout.core.safety import confirm_destructive, is_destructive
from scout.workflow.actions import StepResult, execute_step
from scout.workflow.parser import WorkflowStep

console = Console()

# ── Risk levels ────────────────────────────────────────────────────────

SAFE = {"system_info", "project_info", "git_status", "git_log", "git_diff", "git_branch", "open_app", "screenshot", "open_url", "project_open"}
CONFIRM = {"run_command", "project_run", "git_pull", "git_commit", "workflow_run", "type", "press", "wait", "change_directory"}
HIGH_RISK = {"git_push"}

def _get_risk_level(action_type: str) -> str:
    if action_type in SAFE:
        return "SAFE"
    if action_type in HIGH_RISK:
        return "HIGH_RISK"
    # Default to CONFIRM for anything unknown or in CONFIRM set
    return "CONFIRM"


# ── Interpreter ────────────────────────────────────────────────────────

class AIInterpreter:
    def __init__(self, provider: AIProvider):
        self.provider = provider
        self.messages: list[dict[str, Any]] = []

    def _build_system_prompt(self) -> str:
        ctx = gather_context()
        return SYSTEM_PROMPT.replace("{context}", ctx)

    def ask(self, request: str) -> None:
        """One-shot request."""
        self.messages = [{"role": "user", "content": request}]
        self._run_loop()

    def chat_turn(self, request: str) -> None:
        """A single turn in an ongoing chat session."""
        self.messages.append({"role": "user", "content": request})
        self._run_loop()

    def _run_loop(self) -> None:
        """The core AI execution loop."""
        sys_prompt = self._build_system_prompt()
        max_turns = 5
        
        with console.status("[bold cyan]AI is thinking...[/]"):
            raw_response = self.provider.generate_plan(sys_prompt, self.messages)
            self.messages.append({"role": "assistant", "content": raw_response})

        for _ in range(max_turns):
            try:
                plan = parse_and_validate_plan(raw_response)
            except ValueError as e:
                console.print(f"[red]AI returned invalid plan schema:[/] {e}")
                # Inform AI of schema error
                self.messages.append({"role": "user", "content": f"Schema Error: {e}\nPlease correct the format and try again."})
                with console.status("[bold cyan]AI is correcting format...[/]"):
                    raw_response = self.provider.generate_plan(sys_prompt, self.messages)
                    self.messages.append({"role": "assistant", "content": raw_response})
                continue
            
            # 1. Show AI's message
            console.print(f"\n[bold cyan]SCOUT AI:[/] {plan.message}")

            if not plan.actions:
                # No actions to execute, turn is complete.
                break

            # 2. Iterate actions and confirm if needed
            for i, act in enumerate(plan.actions):
                console.print(f"\n[bold yellow]Action {i+1}:[/] {act.action_type}")
                if act.params:
                    console.print(f"[dim]{json.dumps(act.params, indent=2)}[/dim]")

                risk = _get_risk_level(act.action_type)
                proceed = True

                # Additional dynamic risk check for shell commands
                if act.action_type in ("run_command", "project_run"):
                    cmd = act.params.get("command", "")
                    if is_destructive(cmd):
                        risk = "HIGH_RISK"

                if risk == "HIGH_RISK":
                    console.print("[bold red][!] HIGH RISK ACTION[/]")
                    proceed = Confirm.ask("[bold red]Execute this action?[/]", default=False)
                elif risk == "CONFIRM":
                    proceed = Confirm.ask("[yellow]Execute this action?[/]", default=True)

                if not proceed:
                    console.print("[yellow]Action cancelled by user.[/]")
                    self.messages.append({
                        "role": "user", 
                        "content": f"Action {act.action_type} was cancelled by the user. Stop this plan."
                    })
                    return  # abort the whole plan on cancellation

                # 3. Execute
                result = self._execute_action(act)
                
                # Report result back to user
                if result.success:
                    console.print(f"[green]✓ Success:[/] {result.message}")
                else:
                    console.print(f"[red]✗ Failed:[/] {result.message}")
                    
                # 4. Report result back to AI so it can chain actions
                self.messages.append({
                    "role": "user", 
                    "content": f"Result of {act.action_type}: {'SUCCESS' if result.success else 'FAILED'} - {result.message}"
                })

                if not result.success:
                    break # Stop executing further actions in this plan if one fails

            # Loop back to AI to let it synthesize results or plan next steps
            with console.status("[bold cyan]AI is evaluating results...[/]"):
                raw_response = self.provider.generate_plan(sys_prompt, self.messages)
                self.messages.append({"role": "assistant", "content": raw_response})

    def _execute_action(self, act: AIAction) -> StepResult:
        """Map an AIAction to a WorkflowStep and execute it."""
        # For specials that aren't strictly workflow actions, we handle them here or map them.
        
        # Git commands mapping
        if act.action_type.startswith("git_"):
            sub = act.action_type.split("_", 1)[1]
            proj = act.params.get("project")
            msg = act.params.get("message")
            cmd = f"git {sub}"
            if msg:
                cmd += f" -m '{msg}'"
            # Map it to a project_run to reuse executor safety logic
            step = WorkflowStep(1, "project_run", {"project": proj, "command": cmd}, {})
            return execute_step(step)

        # system_info mapping
        if act.action_type == "system_info":
            from scout.commands.system import _system_cmd
            _system_cmd([])
            return StepResult(True, "Displayed system info")

        # project_info mapping
        if act.action_type == "project_info":
            proj = act.params.get("project")
            from scout.commands.projects import _project_info
            _project_info([proj])
            return StepResult(True, f"Displayed info for {proj}")

        # Normal workflow action
        step = WorkflowStep(1, act.action_type, act.params, {})
        return execute_step(step)

