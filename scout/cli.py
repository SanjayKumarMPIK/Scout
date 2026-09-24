"""Scout CLI – interactive shell entry-point."""

from __future__ import annotations

import os
import sys

from rich.console import Console
from rich.text import Text

from scout import __version__
from scout.core.executor import execute
from scout.core.registry import registry

# ── Import command modules so they self-register ───────────────────────
import scout.commands.system        # noqa: F401
import scout.commands.apps          # noqa: F401
import scout.commands.terminal      # noqa: F401
import scout.commands.files         # noqa: F401
import scout.commands.automation    # noqa: F401
import scout.commands.workflow_cmd  # noqa: F401
import scout.commands.projects      # noqa: F401
import scout.commands.git_cmd       # noqa: F401
import scout.commands.development   # noqa: F401
import scout.commands.ai_cmd        # noqa: F401

console = Console()

# ── Help group display order ───────────────────────────────────────────
_GROUP_ORDER = ["AI Agent", "System", "Project", "Development", "Git", "Automation", "Workflow", "General"]


# ── Built-in commands (registered here, not in separate files) ─────────

def _help_cmd(args: list[str]) -> None:
    """Show available commands grouped by category."""
    groups = registry.by_group()

    console.print()
    for group_name in _GROUP_ORDER:
        cmds = groups.pop(group_name, None)
        if not cmds:
            continue
        console.print(f"  [bold cyan]{group_name.upper()}[/]")
        for cmd in cmds:
            aliases = ""
            if cmd.aliases:
                aliases = f" [dim]({', '.join(cmd.aliases)})[/dim]"
            console.print(f"    [bold]{cmd.usage:<28}[/] {cmd.description}{aliases}")
        console.print()

    # Any remaining groups not in _GROUP_ORDER
    for group_name, cmds in sorted(groups.items()):
        console.print(f"  [bold cyan]{group_name.upper()}[/]")
        for cmd in cmds:
            aliases = ""
            if cmd.aliases:
                aliases = f" [dim]({', '.join(cmd.aliases)})[/dim]"
            console.print(f"    [bold]{cmd.usage:<28}[/] {cmd.description}{aliases}")
        console.print()


def _clear_cmd(args: list[str]) -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")  # noqa: S605


def _exit_cmd(args: list[str]) -> None:
    """Exit Scout."""
    console.print("[dim]Goodbye.[/dim]")
    sys.exit(0)


registry.register("help", _help_cmd, "help", "Show this help message.", aliases=["?", "h"])
registry.register("clear", _clear_cmd, "clear", "Clear the terminal.", aliases=["cls"])
registry.register("exit", _exit_cmd, "exit", "Exit Scout.", aliases=["quit", "q"])


# ── Banner ─────────────────────────────────────────────────────────────

def _print_banner() -> None:
    banner = Text()
    banner.append("\n  SCOUT", style="bold cyan")
    banner.append(f"  v{__version__}", style="dim")
    banner.append("\n  Personal Windows Automation Assistant\n", style="dim")
    console.print(banner)
    console.print("  [dim]Type [bold]help[/bold] for available commands.[/dim]\n")


# ── Main loop ──────────────────────────────────────────────────────────

def main() -> None:
    """Launch the interactive Scout shell."""
    _print_banner()

    while True:
        try:
            raw = console.input("[bold cyan]SCOUT >[/] ")
            if not raw.strip():
                continue
            execute(raw)
        except KeyboardInterrupt:
            console.print("\n[dim]Use [bold]exit[/bold] to quit.[/dim]")
        except EOFError:
            _exit_cmd([])


if __name__ == "__main__":
    main()
