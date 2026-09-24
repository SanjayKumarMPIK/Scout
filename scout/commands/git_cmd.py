"""git commands – Git operations scoped to registered projects."""

from __future__ import annotations

import subprocess

from rich.console import Console
from rich.prompt import Confirm

from scout.core.project_manager import get_project
from scout.core.registry import registry

console = Console()

# Git sub-commands that require confirmation before executing.
_CONFIRM_SUBS = {"push", "reset", "clean", "rebase"}


def _git_cmd(args: list[str]) -> None:
    """Handle git sub-commands."""
    if not args:
        _git_help()
        return

    sub = args[0].lower()
    rest = args[1:]

    dispatch = {
        "status":  _git_status,
        "st":      _git_status,
        "log":     _git_log,
        "branch":  _git_branch,
        "br":      _git_branch,
        "diff":    _git_diff,
        "pull":    _git_pull,
        "push":    _git_push,
        "commit":  _git_commit,
    }

    handler = dispatch.get(sub)
    if handler is None:
        console.print(f"[red]Unknown git sub-command:[/] {sub}")
        _git_help()
        return

    handler(rest)


def _git_help() -> None:
    console.print("[red]Usage:[/] git <sub-command> <project> [args]")
    console.print()
    console.print("[dim]  git status <project>              Show working-tree status[/dim]")
    console.print("[dim]  git log <project>                 Show recent commits[/dim]")
    console.print("[dim]  git branch <project>              List branches[/dim]")
    console.print("[dim]  git diff <project>                Show unstaged changes[/dim]")
    console.print("[dim]  git pull <project>                Pull from remote[/dim]")
    console.print("[dim]  git push <project>                Push to remote (confirm)[/dim]")
    console.print('[dim]  git commit <project> "message"    Commit staged changes[/dim]')


# ── Helpers ────────────────────────────────────────────────────────────

def _resolve_project(args: list[str]) -> tuple[str, str] | None:
    """Extract and validate the project from args. Returns (name, path) or None."""
    if not args:
        console.print("[red]Missing project name.[/]")
        return None

    entry = get_project(args[0])
    if entry is None:
        console.print(f"[red]Project '{args[0]}' not found.[/]")
        return None

    from pathlib import Path
    name, path = entry
    if not (Path(path) / ".git").is_dir():
        console.print(f"[red]Project '{name}' is not a Git repository.[/]")
        return None

    return name, path


def _run_git(path: str, git_args: list[str], confirm: bool = False) -> None:
    """Run a git command in the project directory."""
    cmd = ["git"] + git_args
    cmd_str = " ".join(cmd)

    if confirm:
        console.print(f"\n[bold yellow][!] Git command:[/] {cmd_str}")
        console.print(f"[dim]In: {path}[/dim]")
        if not Confirm.ask("[yellow]Proceed?[/]", default=False):
            console.print("[yellow]Cancelled.[/]")
            return

    try:
        result = subprocess.run(
            cmd,
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=60,
        )
        if result.stdout:
            console.print(result.stdout.rstrip())
        if result.stderr:
            # Git writes some normal output to stderr (e.g. branch info)
            console.print(f"[dim]{result.stderr.rstrip()}[/]")
        if result.returncode != 0:
            console.print(f"\n[red][x][/] git exited with code {result.returncode}")
        else:
            console.print(f"\n[green][+][/] Done")
    except subprocess.TimeoutExpired:
        console.print("[red][x] Git command timed out (60 s).[/]")
    except FileNotFoundError:
        console.print("[red][x] Git executable not found. Is Git installed?[/]")
    except Exception as exc:
        console.print(f"[red][x] Error:[/] {exc}")


# ── Sub-command handlers ───────────────────────────────────────────────

def _git_status(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj
    _run_git(path, ["status", "--short", "--branch"])


def _git_log(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj
    n = args[1] if len(args) > 1 else "10"
    _run_git(path, ["log", f"--oneline", f"-n", n])


def _git_branch(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj
    _run_git(path, ["branch", "-a"])


def _git_diff(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj
    _run_git(path, ["diff", "--stat"])


def _git_pull(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj
    _run_git(path, ["pull"])


def _git_push(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj
    _run_git(path, ["push"], confirm=True)


def _git_commit(args: list[str]) -> None:
    proj = _resolve_project(args)
    if proj is None:
        return
    _, path = proj

    # Collect the commit message from remaining args
    msg_parts = args[1:]
    if not msg_parts:
        console.print("[red]Usage:[/] git commit <project> \"message\"")
        return

    message = " ".join(msg_parts).strip('"').strip("'")
    _run_git(path, ["commit", "-m", message])


# ── Registration ───────────────────────────────────────────────────────

registry.register(
    name="git",
    handler=_git_cmd,
    usage="git <sub-command> <project>",
    description="Git operations on registered projects.",
    group="Git",
)
