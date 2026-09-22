"""Executor – dispatches parsed input to the appropriate command handler."""

from __future__ import annotations

from rich.console import Console

from scout.core.registry import registry

console = Console()


def execute(raw_input: str) -> None:
    """Parse *raw_input* and dispatch to the matching command handler."""
    parts = raw_input.strip().split(maxsplit=1)
    if not parts:
        return

    cmd_name = parts[0].lower()
    args = parts[1].split() if len(parts) > 1 else []

    command = registry.get(cmd_name)
    if command is None:
        console.print(f"[red]Unknown command:[/] {cmd_name}")
        console.print("[dim]Type [bold]help[/bold] to see available commands.[/dim]")
        return

    try:
        command.handler(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error running '{cmd_name}':[/] {exc}")
