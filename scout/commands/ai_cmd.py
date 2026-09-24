"""AI command group: ask, chat, and status."""

from __future__ import annotations

from rich.console import Console

from scout.ai import get_provider
from scout.ai.interpreter import AIInterpreter
from scout.core.registry import registry
from scout.user_config import load_config

console = Console()

# Singleton interpreter to maintain chat memory across a `chat` session or consecutive `ask`s
_interpreter: AIInterpreter | None = None

def _get_interpreter() -> AIInterpreter:
    global _interpreter
    if _interpreter is None:
        config = load_config()
        provider = get_provider(config)
        _interpreter = AIInterpreter(provider)
    return _interpreter


# ── Sub-command handlers ───────────────────────────────────────────────

def _ask_cmd(args: list[str]) -> None:
    """One-shot request to the AI."""
    if not args:
        console.print("[red]Usage:[/] ask <your request>")
        return
    
    request = " ".join(args)
    interpreter = _get_interpreter()
    
    try:
        interpreter.ask(request)
    except Exception as e:
        console.print(f"[red]AI Error:[/] {e}")


def _chat_cmd(args: list[str]) -> None:
    """Interactive conversational session with the AI."""
    console.print("[bold cyan]SCOUT AI Chat[/] (type 'exit' or 'quit' to end)")
    interpreter = _get_interpreter()
    
    while True:
        try:
            req = console.input("\n[bold green]You:[/] ")
            req = req.strip()
            if not req:
                continue
            if req.lower() in ("exit", "quit"):
                break
            
            interpreter.chat_turn(req)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Chat session ended.[/dim]")
            break
        except Exception as e:
            console.print(f"[red]AI Error:[/] {e}")


def _ai_status_cmd(args: list[str]) -> None:
    """Check AI configuration and connection status."""
    config = load_config()
    ai_config = config.get("ai", {})
    provider_name = ai_config.get("provider", "groq")
    model = ai_config.get("model", "unknown")
    api_key_env = ai_config.get("api_key_env", "")

    console.print()
    console.print(f"[bold cyan]AI Provider:[/] {provider_name.title()}")
    console.print(f"[bold cyan]Model:[/] {model}")
    if api_key_env:
        console.print(f"[bold cyan]Auth Env Var:[/] {api_key_env}")
    
    with console.status("[bold cyan]Testing connection...[/]"):
        try:
            provider = get_provider(config)
            success, msg = provider.test_connection()
            if success:
                console.print(f"[bold cyan]Status:[/] [green]Connected[/] ({msg})")
            else:
                console.print(f"[bold cyan]Status:[/] [red]Disconnected[/] ({msg})")
        except Exception as e:
            console.print(f"[bold cyan]Status:[/] [red]Error[/] ({e})")
    console.print()


def _ai_cmd(args: list[str]) -> None:
    """AI configuration and status group."""
    if not args:
        _ai_help()
        return

    sub = args[0].lower()
    if sub == "status":
        _ai_status_cmd(args[1:])
    else:
        console.print(f"[red]Unknown ai sub-command:[/] {sub}")
        _ai_help()

def _ai_help() -> None:
    console.print("[red]Usage:[/] ai <sub-command>")
    console.print()
    console.print("[dim]  ai status           Check AI connection status[/dim]")


# ── Registration ───────────────────────────────────────────────────────

registry.register(
    name="ask",
    handler=_ask_cmd,
    usage="ask <request>",
    description="Ask the AI to perform a task.",
    group="AI Agent",
)

registry.register(
    name="chat",
    handler=_chat_cmd,
    usage="chat",
    description="Start an interactive AI chat session.",
    group="AI Agent",
)

registry.register(
    name="ai",
    handler=_ai_cmd,
    usage="ai <status>",
    description="Manage AI configuration and view status.",
    group="AI Agent",
)
