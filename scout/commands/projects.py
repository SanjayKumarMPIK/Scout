"""project commands – register, inspect, and manage development projects."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table

from scout.core.project_manager import (
    add_project,
    get_project,
    get_project_info,
    list_projects,
    remove_project,
)
from scout.core.registry import registry

console = Console()


# ── Sub-command dispatch ───────────────────────────────────────────────

def _project_cmd(args: list[str]) -> None:
    """Handle project sub-commands."""
    if not args:
        _project_help()
        return

    sub = args[0].lower()
    rest = args[1:]

    dispatch = {
        "add":      _project_add,
        "list":     _project_list,
        "ls":       _project_list,
        "show":     _project_show,
        "info":     _project_info,
        "remove":   _project_remove,
        "rm":       _project_remove,
        "open":     _project_open,
        "terminal": _project_terminal,
        "term":     _project_terminal,
        "run":      _project_run,
        "init":     _project_init,
    }

    handler = dispatch.get(sub)
    if handler is None:
        console.print(f"[red]Unknown sub-command:[/] {sub}")
        _project_help()
        return

    handler(rest)


def _project_help() -> None:
    console.print("[red]Usage:[/] project <sub-command> [args]")
    console.print()
    console.print("[dim]  project add <name> <path>        Register a project[/dim]")
    console.print("[dim]  project list                     List projects[/dim]")
    console.print("[dim]  project show <name>              Show project path[/dim]")
    console.print("[dim]  project info <name>              Detect project type & details[/dim]")
    console.print("[dim]  project remove <name>            Unregister a project[/dim]")
    console.print("[dim]  project open <name>              Open in VS Code[/dim]")
    console.print("[dim]  project terminal <name>          Open terminal in project dir[/dim]")
    console.print("[dim]  project run <name> <command>     Run command in project dir[/dim]")
    console.print("[dim]  project init <name> <template>   Initialize a new project[/dim]")


# ── Sub-command handlers ───────────────────────────────────────────────

def _project_add(args: list[str]) -> None:
    if len(args) < 2:
        console.print("[red]Usage:[/] project add <name> <path>")
        return
    name, path = args[0], " ".join(args[1:])
    ok, msg = add_project(name, path)
    if ok:
        console.print(f"[green][+][/] {msg}")
    else:
        console.print(f"[red][x][/] {msg}")


def _project_list(args: list[str]) -> None:
    projects = list_projects()
    if not projects:
        console.print("[dim]No projects registered.[/dim]")
        console.print("[dim]Use [bold]project add <name> <path>[/bold] to register one.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Name", min_width=14)
    table.add_column("Path")

    for name, path in sorted(projects.items()):
        exists = "[green]" if Path(path).is_dir() else "[red]"
        table.add_row(f"[bold]{name}[/]", f"{exists}{path}[/]")

    console.print()
    console.print("[bold cyan]Projects[/]\n")
    console.print(table)
    console.print()


def _project_show(args: list[str]) -> None:
    if not args:
        console.print("[red]Usage:[/] project show <name>")
        return
    entry = get_project(args[0])
    if entry is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return
    name, path = entry
    console.print(f"\n[bold cyan]{name}[/]  {path}\n")


def _project_info(args: list[str]) -> None:
    if not args:
        console.print("[red]Usage:[/] project info <name>")
        return

    info = get_project_info(args[0])
    if info is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", min_width=18)
    table.add_column()

    table.add_row("Project", info.name)
    table.add_row("Path", info.path)
    table.add_row("Type", info.project_type)
    if info.frameworks:
        table.add_row("Framework", ", ".join(info.frameworks))
    table.add_row("Git", "Yes" if info.has_git else "No")
    if info.package_manager:
        table.add_row("Package manager", info.package_manager)

    console.print()
    console.print(table)
    console.print()


def _project_remove(args: list[str]) -> None:
    if not args:
        console.print("[red]Usage:[/] project remove <name>")
        return
    ok, msg = remove_project(args[0])
    if ok:
        console.print(f"[green][+][/] {msg}")
    else:
        console.print(f"[red][x][/] {msg}")


def _project_open(args: list[str]) -> None:
    """Open a project in VS Code."""
    if not args:
        console.print("[red]Usage:[/] project open <name>")
        return
    entry = get_project(args[0])
    if entry is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return
    _, path = entry
    try:
        subprocess.Popen(
            ["code", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        console.print(f"[green][+][/] Opened {args[0]} in VS Code")
    except OSError as exc:
        console.print(f"[red][x] Failed:[/] {exc}")


def _project_terminal(args: list[str]) -> None:
    """Open a terminal in the project directory."""
    if not args:
        console.print("[red]Usage:[/] project terminal <name>")
        return
    entry = get_project(args[0])
    if entry is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return
    _, path = entry
    try:
        subprocess.Popen(
            ["wt", "-d", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        console.print(f"[green][+][/] Terminal opened at {path}")
    except OSError:
        # Fallback to cmd if Windows Terminal not available
        try:
            subprocess.Popen(
                ["cmd", "/k", f"cd /d {path}"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            console.print(f"[green][+][/] Terminal opened at {path}")
        except OSError as exc:
            console.print(f"[red][x] Failed:[/] {exc}")


def _project_run(args: list[str]) -> None:
    """Run a command inside the project's directory via existing executor."""
    if len(args) < 2:
        console.print("[red]Usage:[/] project run <name> <command>")
        return

    entry = get_project(args[0])
    if entry is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return
    _, path = entry
    command = " ".join(args[1:])

    # Delegate to the existing run command logic by importing it
    from scout.core.safety import confirm_destructive, is_blocked, is_destructive

    if is_blocked(command):
        console.print("[bold red][x] Blocked:[/] This command is not allowed.")
        return

    if is_destructive(command):
        if not confirm_destructive(command):
            console.print("[yellow]Cancelled.[/]")
            return

    console.print(f"[dim]Running in {path}:[/] {command}\n")
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=120,
            cwd=path,
        )
        if result.stdout:
            console.print(result.stdout.rstrip())
        if result.stderr:
            console.print(f"[yellow]{result.stderr.rstrip()}[/]")
        if result.returncode == 0:
            console.print(f"\n[green][+][/] Exited with code {result.returncode}")
        else:
            console.print(f"\n[red][x][/] Exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        console.print("[red][x] Command timed out (120 s).[/]")
    except Exception as exc:
        console.print(f"[red][x] Error:[/] {exc}")


# ── Project init ───────────────────────────────────────────────────────

_TEMPLATES: dict[str, dict] = {
    "python": {
        "description": "Python project with pyproject.toml",
        "command": None,  # handled inline
    },
    "node": {
        "description": "Node.js project (npm init)",
        "command": "npm init -y",
    },
    "vite": {
        "description": "Vite project (create-vite)",
        "command": "npm create vite@latest . -- --template vanilla",
    },
    "next": {
        "description": "Next.js project (create-next-app)",
        "command": "npx -y create-next-app@latest . --use-npm --ts --eslint --app --no-tailwind --no-src-dir --no-import-alias --turbopack",
    },
}


def _project_init(args: list[str]) -> None:
    """Initialize a new project from a template."""
    if len(args) < 2:
        console.print("[red]Usage:[/] project init <name> <template>")
        console.print("[dim]Available templates:[/dim]")
        for tname, tinfo in _TEMPLATES.items():
            console.print(f"  [bold]{tname:<12}[/] {tinfo['description']}")
        return

    name = args[0].lower()
    template = args[1].lower()

    if template not in _TEMPLATES:
        console.print(f"[red]Unknown template:[/] {template}")
        console.print(f"[dim]Available: {', '.join(_TEMPLATES)}[/dim]")
        return

    # Determine destination
    if len(args) >= 3:
        dest = Path(" ".join(args[2:]))
    else:
        dest = Path.cwd() / name

    # Check destination
    if dest.exists():
        contents = list(dest.iterdir()) if dest.is_dir() else []
        if contents:
            from rich.prompt import Confirm
            console.print(f"[yellow]Directory is not empty:[/] {dest}")
            if not Confirm.ask("[yellow]Continue anyway?[/]", default=False):
                console.print("[yellow]Cancelled.[/]")
                return
    else:
        dest.mkdir(parents=True)

    tpl = _TEMPLATES[template]

    if template == "python":
        _init_python_project(dest, name)
    else:
        cmd = tpl["command"]
        console.print(f"[dim]Running:[/] {cmd}")
        console.print(f"[dim]In:[/] {dest}\n")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=str(dest),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, text=True, timeout=120,
            )
            if result.stdout:
                console.print(result.stdout.rstrip())
            if result.stderr:
                console.print(f"[yellow]{result.stderr.rstrip()}[/]")
            if result.returncode != 0:
                console.print(f"[red][x] Template command failed (exit {result.returncode})[/]")
                return
        except Exception as exc:
            console.print(f"[red][x] Error:[/] {exc}")
            return

    # Register with Scout
    ok, msg = add_project(name, str(dest))
    if ok:
        console.print(f"\n[green][+][/] {msg}")
    else:
        console.print(f"\n[yellow]{msg}[/]")


def _init_python_project(dest: Path, name: str) -> None:
    """Create a minimal Python project scaffold."""
    pyproject = dest / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n',
            encoding="utf-8",
        )

    src = dest / name
    src.mkdir(exist_ok=True)
    init = src / "__init__.py"
    if not init.exists():
        init.write_text(f'"""Package {name}."""\n', encoding="utf-8")

    readme = dest / "README.md"
    if not readme.exists():
        readme.write_text(f"# {name}\n", encoding="utf-8")

    console.print(f"[green][+][/] Python project created at {dest}")


# ── Registration ───────────────────────────────────────────────────────

registry.register(
    name="project",
    handler=_project_cmd,
    usage="project <sub-command>",
    description="Manage development projects.",
    aliases=["proj", "projects"],
    group="Project",
)
