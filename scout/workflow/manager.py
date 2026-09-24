"""Workflow manager – discovers, lists, and runs workflows.

Architecture:
    CLI  ->  WorkflowManager  ->  WorkflowParser  ->  ActionExecutor
                                                        ->  Existing SCOUT Commands
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from scout.workflow.actions import StepResult, execute_step
from scout.workflow.parser import Workflow, WorkflowParseError, parse_workflow

console = Console()

# Default search paths for workflow JSON files.
_WORKFLOW_DIRS: list[Path] = []


def _discover_dirs() -> list[Path]:
    """Return the list of directories to search for workflow files."""
    if _WORKFLOW_DIRS:
        return _WORKFLOW_DIRS

    from scout.config import APP_DIR

    # 1. Project-local workflows/ directory (relative to cwd)
    local = Path.cwd() / "workflows"
    # 2. Global ~/.scout/workflows/
    global_dir = APP_DIR / "workflows"
    global_dir.mkdir(exist_ok=True)

    dirs = []
    if local.is_dir():
        dirs.append(local)
    dirs.append(global_dir)
    return dirs


def set_workflow_dirs(dirs: list[Path]) -> None:
    """Override workflow search directories (useful for testing)."""
    global _WORKFLOW_DIRS  # noqa: PLW0603
    _WORKFLOW_DIRS = list(dirs)


def discover_workflows() -> dict[str, Path]:
    """Return a mapping of workflow name (stem) -> file path.

    Files in earlier directories shadow later ones with the same stem.
    """
    seen: dict[str, Path] = {}
    for d in _discover_dirs():
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            stem = f.stem
            if stem not in seen:
                seen[stem] = f
    return seen


def load_workflow(name: str) -> Workflow:
    """Load a workflow by name. Raises WorkflowParseError on failure."""
    available = discover_workflows()
    path = available.get(name)
    if path is None:
        raise WorkflowParseError(
            f"Workflow '{name}' not found. "
            f"Available: {', '.join(sorted(available)) or '(none)'}"
        )
    return parse_workflow(path)


# ── Public operations ──────────────────────────────────────────────────

def list_workflows() -> None:
    """Print a table of available workflows."""
    available = discover_workflows()
    if not available:
        console.print("[dim]No workflows found.[/dim]")
        console.print(
            "[dim]Place .json workflow files in [bold]workflows/[/bold] "
            "or [bold]~/.scout/workflows/[/bold][/dim]"
        )
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Name")
    table.add_column("Location", style="dim")

    for name, path in sorted(available.items()):
        table.add_row(name, str(path.parent))

    console.print()
    console.print("[bold cyan]Available workflows[/]\n")
    console.print(table)
    console.print()


def show_workflow(name: str) -> None:
    """Print the steps of a workflow."""
    try:
        wf = load_workflow(name)
    except WorkflowParseError as exc:
        console.print(f"[red]{exc}[/]")
        return

    console.print()
    console.print(f"[bold cyan]{wf.name}[/]")
    if wf.description:
        console.print(f"[dim]{wf.description}[/]")
    console.print()

    for step in wf.steps:
        console.print(f"  [bold]{step.index}.[/] {step.summary}")
    console.print()


def run_workflow(name: str) -> bool:
    """Execute all steps of a workflow. Returns True if all succeed."""
    try:
        wf = load_workflow(name)
    except WorkflowParseError as exc:
        console.print(f"[red]{exc}[/]")
        return False

    console.print(f"\n[bold cyan]Running workflow:[/] {wf.name}")
    if wf.description:
        console.print(f"[dim]{wf.description}[/]")
    console.print()

    for step in wf.steps:
        console.print(f"  [dim]Step {step.index}:[/] {step.summary}")
        result: StepResult = execute_step(step)

        if result.success:
            console.print(f"  [green][+][/] {result.message}")
        else:
            console.print(f"  [red][x] Failed at step {step.index}:[/] {step.summary}")
            console.print(f"  [red]    Error: {result.message}[/]")
            console.print(f"\n[red][x] Workflow '{wf.name}' aborted.[/]")
            return False

    console.print(f"\n[green][+] Workflow '{wf.name}' completed successfully.[/]")
    return True
