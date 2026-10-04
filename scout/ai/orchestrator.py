"""Planner -> Executor orchestration.

The planner decides what to do; the executor runs each step in isolation,
restricted to the tools the planner assigned. If a step fails, the planner
revises the remaining plan (visibly), so what runs is always what was shown.
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel

from scout.ai.interpreter import AIInterpreter, StepOutcome, _print_response
from scout.ai.planner import Plan, Planner, PlanStep

console = Console()

MAX_REPLANS = 2


def build_context(messages: list[dict], limit: int = 30) -> str:
    """Summarize recent history (requests, tool calls, results) for the planner."""
    lines: list[str] = []
    for msg in messages[-limit:]:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "user":
            if content.startswith(("PLAN STEP", "The plan has finished", "Respond only with tool calls")):
                continue
            if "USER REQUEST:" in content:
                content = content.split("USER REQUEST:", 1)[1]
            content = content.split("(A planner produced", 1)[0].strip()
            lines.append(f"User: {content}")
        elif role == "assistant":
            if content:
                lines.append(f"Scout: {content}")
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                lines.append(f"Executor called {fn.get('name', '')}({fn.get('arguments', '')})")
        elif role == "tool":
            lines.append(f"Tool result: {content[:300]}")
    return "\n".join(lines)


def _show_plan(steps: list[PlanStep], title: str, start: int = 1) -> None:
    rows = []
    for i, step in enumerate(steps, start):
        tools = f"  `{', '.join(step.tools)}`" if step.tools else ""
        rows.append(f"{i}. {step.description}{tools}")
    console.print(Panel(
        Markdown("\n".join(rows)),
        title=f"[magenta]⚙ {title}[/]",
        title_align="left",
        border_style="magenta",
        padding=(0, 2),
    ))


def _report(history: list[tuple[PlanStep, str, str]]) -> str:
    return "\n".join(
        f"{i}. [{status.upper()}] {step.description}\n   Result: {result}"
        for i, (step, status, result) in enumerate(history, 1)
    )


def run_planned_turn(interpreter: AIInterpreter, planner: Planner, request: str) -> None:
    context = build_context(interpreter.messages)
    plan: Plan | None = planner.generate_plan(request, memory_context=context)
    if plan is None:
        console.print("[red]Planner failed to generate a plan.[/]")
        return

    # Direct answer: nothing to execute, so nothing can diverge.
    if plan.mode == "respond":
        _print_response(plan.response)
        interpreter.messages.append({"role": "user", "content": f"USER REQUEST: {request}"})
        interpreter.messages.append({"role": "assistant", "content": plan.response})
        return

    _show_plan(plan.steps, "Execution Plan")
    interpreter.begin_task(request, len(plan.steps))

    history: list[tuple[PlanStep, str, str]] = []
    queue = list(plan.steps)
    replans = 0
    planner_note = ""

    while queue:
        step = queue.pop(0)
        number = len(history) + 1
        total = number + len(queue)

        console.print(f"\n[bold magenta]▸ Step {number}/{total}[/] {escape(step.description)}")
        outcome: StepOutcome = interpreter.run_step(number, total, step.description, step.tools, history=history)
        history.append((step, outcome.status, outcome.result))

        if outcome.status == "done":
            console.print(f"[green]✓ Step {number} done:[/] [dim]{escape(outcome.result)}[/dim]")
            continue

        if outcome.status == "cancelled":
            console.print(f"[yellow]■ Plan stopped at step {number}: {escape(outcome.result)}[/]")
            return

        console.print(f"[red]✗ Step {number} failed:[/] {escape(outcome.result)}")
        if replans >= MAX_REPLANS:
            console.print("[dim]Revision limit reached; stopping the plan.[/dim]")
            break

        replans += 1
        revised = planner.revise_plan(request, history, queue, memory_context=build_context(interpreter.messages))
        if revised is None:
            break
        if revised.mode == "respond":
            planner_note = revised.response
            break
        _show_plan(revised.steps, "Revised Plan", start=number + 1)
        queue = list(revised.steps)

        if not queue and replans < MAX_REPLANS:
            report = _report(history)
            check_prompt = (
                f"Original Request: {request}\n\n"
                f"Execution History:\n{report}\n\n"
                "Was the user's original request fully completed? If yes, use mode='respond' to finalize. "
                "If no, or if new issues arose that need fixing, use mode='execute' and generate the remaining steps."
            )
            with console.status("[bold cyan]Checking if goal was met...[/]"):
                check_plan = planner.generate_plan(check_prompt, memory_context=build_context(interpreter.messages))
            if check_plan and check_plan.mode == "execute" and check_plan.steps:
                console.print("[yellow]Planner determined goal is not fully met. Adding remaining steps...[/yellow]")
                _show_plan(check_plan.steps, "Additional Steps (Goal Verification)", start=len(history) + 1)
                queue = list(check_plan.steps)
                replans += 1
                continue
        
        break

    report = _report(history)
    if planner_note:
        report += f"\n\nPlanner note: {planner_note}"
    
    interpreter.finalize(request, report)
    
    # Automatically learn facts into memory
    with console.status("[bold cyan]Extracting memory...[/]"):
        try:
            from scout.memory.store import get_memory_store
            mem_prompt = (
                f"User Request: {request}\n"
                f"Execution Result:\n{report}\n\n"
                "Did the user state any facts, preferences, or personal details that should be remembered for future interactions? "
                "Respond ONLY with a JSON array of objects in this format: "
                '[{"key": "user_name", "value": "Alice"}, {"key": "likes_dark_mode", "value": "yes"}]. '
                "Return an empty array [] if there is nothing to remember."
            )
            # Use planner's provider for memory extraction
            mem_response = planner.provider.chat_completion(
                "You are a memory extraction assistant. Output strictly JSON.",
                [{"role": "user", "content": mem_prompt}],
                []
            )
            mem_text = mem_response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Find JSON array
            import json
            import re
            match = re.search(r'\[.*\]', mem_text, re.DOTALL)
            if match:
                facts = json.loads(match.group(0))
                if facts:
                    store = get_memory_store()
                    for fact in facts:
                        store.save("preferences", fact["key"], fact["value"])
                    console.print(f"[dim]Learned {len(facts)} new fact(s) into memory.[/dim]")
        except Exception:
            pass # Fail silently for memory extraction

