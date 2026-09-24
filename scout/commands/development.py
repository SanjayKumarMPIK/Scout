"""development commands – developer environment info, project shortcuts, and package-manager helpers."""

from __future__ import annotations

import platform
import shutil
import subprocess

from rich.console import Console
from rich.table import Table

from scout.core.project_manager import (
    detect_package_manager,
    get_pm_command,
    get_project,
    get_project_info,
)
from scout.core.registry import registry

console = Console()


# ── Sub-command dispatch ───────────────────────────────────────────────

def _dev_cmd(args: list[str]) -> None:
    """Handle dev sub-commands."""
    if not args:
        _dev_help()
        return

    sub = args[0].lower()
    rest = args[1:]

    dispatch = {
        "info":     _dev_info,
        "install":  lambda a: _dev_pm_action(a, "install"),
        "start":    lambda a: _dev_pm_action(a, "start"),
        "build":    lambda a: _dev_pm_action(a, "build"),
        "test":     lambda a: _dev_pm_action(a, "test"),
        "run":      _dev_run,
        "vscode":   _dev_vscode,
        "terminal": _dev_terminal,
        "term":     _dev_terminal,
    }

    handler = dispatch.get(sub)
    if handler is None:
        console.print(f"[red]Unknown dev sub-command:[/] {sub}")
        _dev_help()
        return

    handler(rest)


def _dev_help() -> None:
    console.print("[red]Usage:[/] dev <sub-command> [args]")
    console.print()
    console.print("[dim]  dev info                          Development environment info[/dim]")
    console.print("[dim]  dev install <project>             Install dependencies[/dim]")
    console.print("[dim]  dev start <project>               Start dev server[/dim]")
    console.print("[dim]  dev build <project>               Build project[/dim]")
    console.print("[dim]  dev test <project>                Run tests[/dim]")
    console.print("[dim]  dev run <project> <command>       Run command in project dir[/dim]")
    console.print("[dim]  dev vscode <project>              Open project in VS Code[/dim]")
    console.print("[dim]  dev terminal <project>            Open terminal in project dir[/dim]")


# ── dev info ───────────────────────────────────────────────────────────

def _get_version(cmd: list[str]) -> str | None:
    """Run a command and return its first output line, or None."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _dev_info(args: list[str]) -> None:
    """Display development environment information."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", min_width=14)
    table.add_column()

    table.add_row("OS", f"{platform.system()} {platform.release()}")

    tools = [
        ("Python",  ["python", "--version"]),
        ("Node",    ["node", "--version"]),
        ("npm",     ["npm", "--version"]),
        ("pnpm",    ["pnpm", "--version"]),
        ("yarn",    ["yarn", "--version"]),
        ("Git",     ["git", "--version"]),
        ("Java",    ["java", "-version"]),  # java writes to stderr
        ("Docker",  ["docker", "--version"]),
        ("Rust",    ["rustc", "--version"]),
        ("Go",      ["go", "version"]),
    ]

    for label, cmd in tools:
        ver = _get_version(cmd)
        # java -version writes to stderr
        if ver is None and label == "Java":
            try:
                r = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL, text=True, timeout=10,
                )
                if r.stderr.strip():
                    ver = r.stderr.strip().splitlines()[0]
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass

        if ver is not None:
            table.add_row(label, ver)

    console.print()
    console.print(table)
    console.print()


# ── Package-manager helpers ────────────────────────────────────────────

def _dev_pm_action(args: list[str], action: str) -> None:
    """Run a package-manager action (install/start/build/test) for a project."""
    if not args:
        console.print(f"[red]Usage:[/] dev {action} <project>")
        return

    entry = get_project(args[0])
    if entry is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return

    name, path = entry
    pm = detect_package_manager(path)
    if not pm:
        console.print(f"[red]Unable to determine project type for '{name}'.[/]")
        return

    cmd = get_pm_command(pm, action)
    if not cmd:
        console.print(f"[red]No '{action}' command available for {pm} projects.[/]")
        return

    console.print(f"[dim]{pm}:[/] {cmd}")
    console.print(f"[dim]In:[/] {path}\n")

    from scout.core.safety import confirm_destructive, is_blocked, is_destructive

    if is_blocked(cmd):
        console.print("[bold red][x] Blocked.[/]")
        return
    if is_destructive(cmd):
        if not confirm_destructive(cmd):
            console.print("[yellow]Cancelled.[/]")
            return

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, text=True, timeout=120,
        )
        if result.stdout:
            console.print(result.stdout.rstrip())
        if result.stderr:
            console.print(f"[yellow]{result.stderr.rstrip()}[/]")
        if result.returncode == 0:
            console.print(f"\n[green][+][/] {action} completed")
        else:
            console.print(f"\n[red][x][/] {action} failed (exit {result.returncode})")
    except subprocess.TimeoutExpired:
        console.print("[red][x] Command timed out (120 s).[/]")
    except Exception as exc:
        console.print(f"[red][x] Error:[/] {exc}")


# ── Shortcuts ──────────────────────────────────────────────────────────

def _dev_vscode(args: list[str]) -> None:
    """Open a project in VS Code."""
    if not args:
        console.print("[red]Usage:[/] dev vscode <project>")
        return
    # Reuse project open command
    from scout.commands.projects import _project_open
    _project_open(args)


def _dev_terminal(args: list[str]) -> None:
    """Open a terminal in the project directory."""
    if not args:
        console.print("[red]Usage:[/] dev terminal <project>")
        return
    from scout.commands.projects import _project_terminal
    _project_terminal(args)


def _dev_run(args: list[str]) -> None:
    """Run an arbitrary command in a project directory."""
    if len(args) < 2:
        console.print("[red]Usage:[/] dev run <project> <command>")
        return
    from scout.commands.projects import _project_run
    _project_run(args)


# ── Registration ───────────────────────────────────────────────────────

registry.register(
    name="dev",
    handler=_dev_cmd,
    usage="dev <sub-command>",
    description="Developer tools and project shortcuts.",
    group="Development",
)
