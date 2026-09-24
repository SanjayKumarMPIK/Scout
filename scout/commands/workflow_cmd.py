"""workflow command – CLI front-end for the workflow engine."""

from __future__ import annotations

from rich.console import Console

from scout.core.registry import registry
from scout.workflow.manager import list_workflows, run_workflow, show_workflow

console = Console()


def _workflow_cmd(args: list[str]) -> None:
    """Handle workflow / wf sub-commands."""
    if not args:
        console.print("[red]Usage:[/] workflow <list|show|run> [name]")
        console.print("[dim]  workflow list          - list available workflows[/dim]")
        console.print("[dim]  workflow show <name>   - show workflow steps[/dim]")
        console.print("[dim]  workflow run  <name>   - execute a workflow[/dim]")
        return

    sub = args[0].lower()

    if sub == "list":
        list_workflows()

    elif sub == "show":
        if len(args) < 2:
            console.print("[red]Usage:[/] workflow show <name>")
            return
        show_workflow(args[1])

    elif sub == "run":
        if len(args) < 2:
            console.print("[red]Usage:[/] workflow run <name>")
            return
        run_workflow(args[1])

    else:
        console.print(f"[red]Unknown sub-command:[/] {sub}")
        console.print("[dim]Valid sub-commands: list, show, run[/dim]")


registry.register(
    name="workflow",
    handler=_workflow_cmd,
    usage="workflow <list|show|run>",
    description="Manage and run workflows.",
    aliases=["wf"],
    group="Workflow",
)
