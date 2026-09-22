"""Safety layer – classifies and gates potentially destructive actions."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm

from scout.config import BLOCKED_PATTERNS, DESTRUCTIVE_TOKENS

console = Console()


def is_blocked(command: str) -> bool:
    """Return True if the command matches a hard-blocked pattern."""
    lower = command.lower()
    return any(pat in lower for pat in BLOCKED_PATTERNS)


def is_destructive(command: str) -> bool:
    """Return True if the command looks potentially destructive."""
    lower = command.lower()
    return any(tok in lower for tok in DESTRUCTIVE_TOKENS)


def confirm_destructive(command: str) -> bool:
    """Prompt the user to confirm a destructive action. Returns True if approved."""
    console.print(
        f"\n[bold yellow][!] Potentially destructive command:[/] {command}"
    )
    return Confirm.ask("[yellow]Are you sure you want to run this?[/]", default=False)
