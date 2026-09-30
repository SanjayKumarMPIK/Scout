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
import scout.commands.projects      # noqa: F401
import scout.commands.git_cmd       # noqa: F401
import scout.commands.development   # noqa: F401
import scout.commands.ai_cmd        # noqa: F401

console = Console()

# ── Help group display order ───────────────────────────────────────────
_GROUP_ORDER = ["AI Agent", "System", "Project", "Development", "Git", "Automation", "General"]


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

    if len(sys.argv) > 1:
        # Run specific command if arguments are provided
        execute(" ".join(sys.argv[1:]))
    else:
        from scout.user_config import load_config, save_config
        config = load_config()
        if "ai" not in config or not config["ai"].get("provider"):
            console.print("\n[bold cyan]Welcome to Scout AI![/]")
            console.print("Please select an AI provider to get started:")
            console.print("1. Ollama (Local, free, requires Ollama running)")
            console.print("2. Groq (Fast, cloud, requires API key)")
            console.print("3. OpenAI (Cloud, requires API key)")
            console.print("4. Gemini (Cloud, requires API key)")
            console.print("5. Anthropic (Cloud, requires API key)")
            console.print("6. Custom OpenAI-compatible (Local/Cloud)")
            
            while True:
                choice = console.input("\n[bold]Select provider (1-6):[/] ").strip()
                mapping = {"1": "ollama", "2": "groq", "3": "openai", "4": "gemini", "5": "anthropic", "6": "custom"}
                if choice in mapping:
                    provider = mapping[choice]
                    break
                console.print("[red]Invalid choice. Please select 1-6.[/red]")
                
            if "ai" not in config:
                config["ai"] = {}
            config["ai"]["provider"] = provider
            
            if provider == "custom":
                endpoint = console.input("[bold]Enter API Endpoint URL (e.g., http://localhost:1234/v1/chat/completions):[/] ").strip()
                config["ai"]["endpoint"] = endpoint
                
            if provider != "ollama":
                from scout.core.auth import set_api_key, prompt_secret
                key = prompt_secret(f"Enter API key for {provider}: ")
                set_api_key(provider, key)
                
            model = console.input(f"[bold]Enter the model name (leave blank for default):[/] ").strip()
            if model:
                config["ai"]["model"] = model
            elif provider == "ollama":
                config["ai"]["model"] = "qwen2.5-coder:7b"
            elif provider == "groq":
                config["ai"]["model"] = "llama-3.1-70b-versatile"
            elif provider == "openai":
                config["ai"]["model"] = "gpt-4o"
            elif provider == "gemini":
                config["ai"]["model"] = "gemini-1.5-pro"
            elif provider == "anthropic":
                config["ai"]["model"] = "claude-3-5-sonnet-20240620"
                
            save_config(config)
            console.print(f"\n[green]Setup complete! Using {provider} with model {config['ai']['model']}[/]\n")
            
        # Start AI agent by default
        from scout.commands.ai_cmd import _chat_cmd
        _chat_cmd([])

if __name__ == "__main__":
    main()
