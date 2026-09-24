"""terminal command – run shell commands with safety checks."""

from __future__ import annotations

import subprocess

from rich.console import Console

from scout.core.registry import registry
from scout.core.safety import confirm_destructive, is_blocked, is_destructive

console = Console()


def _run_cmd(args: list[str]) -> None:
    """Run an arbitrary shell command after safety checks."""
    if not args:
        console.print("[red]Usage:[/] run <command>")
        return

    command = " ".join(args)

    # ── Hard-blocked commands ──────────────────────────────────────
    if is_blocked(command):
        console.print("[bold red][x] Blocked:[/] This command is not allowed.")
        return

    # ── Destructive-but-confirmable commands ───────────────────────
    if is_destructive(command):
        if not confirm_destructive(command):
            console.print("[yellow]Cancelled.[/]")
            return

    # ── Execute ────────────────────────────────────────────────────
    console.print(f"[dim]Running:[/] {command}\n")
    try:
        result = subprocess.run(
            command,
            shell=True,  # noqa: S602 – intentional; gated by safety layer
            capture_output=True,
            text=True,
            timeout=120,
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
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red][x] Error:[/] {exc}")


registry.register(
    name="run",
    handler=_run_cmd,
    usage="run <command>",
    description="Run a shell command (with safety checks).",
    group="System",
)
