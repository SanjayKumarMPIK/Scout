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
_voice_mode: bool = False

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
    config = load_config()
    
    if "planner" in config and config["planner"].get("provider") and "executor" in config and config["executor"].get("provider"):
        from scout.ai import get_provider
        from scout.ai.planner import Planner
        from scout.ai.interpreter import AIInterpreter, EXECUTOR_PROMPT
        from scout.ai.orchestrator import run_planned_turn
        
        console.print("[bold cyan]Dual Architecture Mode Active[/]")
        planner_prov = get_provider({"ai": config["planner"]})
        planner = Planner(planner_prov)
        
        exec_prov = get_provider({"ai": config["executor"]})
        executor = AIInterpreter(exec_prov, system_prompt=EXECUTOR_PROMPT)
        
        try:
            run_planned_turn(executor, planner, request)
        except Exception as e:
            from rich.markup import escape
            console.print(f"[red]Execution Error:[/] {escape(str(e))}")
    else:
        interpreter = _get_interpreter()
        try:
            interpreter.ask(request)
        except Exception as e:
            from rich.markup import escape
            console.print(f"[red]AI Error:[/] {escape(str(e))}")


def _handle_slash_command(cmd_line: str) -> bool:
    """Handle slash commands. Returns True if the chat session should exit."""
    import os
    from scout.core.auth import set_api_key, delete_api_key, prompt_secret
    from scout.user_config import load_config, save_config
    
    parts = cmd_line.strip().split()
    if not parts:
        return False
        
    cmd = parts[0].lower()
    args = parts[1:]

    config = load_config()
    if "ai" not in config:
        config["ai"] = {}

    if cmd in ("/quit", "/exit", "/q"):
        return True

    elif cmd == "/clear":
        os.system("cls" if os.name == "nt" else "clear")
    
    elif cmd == "/new":
        global _interpreter
        if _interpreter:
            _interpreter.messages = []
        console.print("\n[dim]New chat started.[/dim]")

    elif cmd == "/provider":
        from scout.core.auth import get_api_key
        if not args:
            console.print("\n[bold]Current AI Configuration:[/]")
            p_prov = config.get("planner", {}).get("provider", "Not set")
            p_mod = config.get("planner", {}).get("model", "Not set")
            e_prov = config.get("executor", {}).get("provider", "Not set")
            e_mod = config.get("executor", {}).get("model", "Not set")
            console.print(f"  [cyan]Planner:[/]  {p_prov} / {p_mod}")
            console.print(f"  [cyan]Executor:[/] {e_prov} / {e_mod}")
            
            console.print("\n[bold]Stored API Keys:[/]")
            found = False
            for p in ["openai", "groq", "gemini", "anthropic", "openrouter", "custom", "vision"]:
                if get_api_key(p):
                    console.print(f"  - [green]{p}[/green]: [dim]Stored[/dim]")
                    found = True
            if not found:
                console.print("  [dim]No API keys currently stored.[/dim]")
            
            console.print("\n[dim]To set an API key: /provider key <provider> [key][/dim]")
            console.print("[dim]To remove a key: /provider remove <provider> | all[/dim]")
            return False
            
        sub = args[0].lower()
        if sub == "key":
            if len(args) < 2:
                console.print("\n[red]Usage:[/] /provider key <provider> [optional_key]")
                console.print("Available providers: openai, groq, gemini, anthropic, openrouter, custom, vision")
                return False
                
            prov = args[1].lower()
            if prov == "ollama":
                console.print("\n[yellow]Ollama does not require an API key.[/yellow]")
                return False
                
            if len(args) > 2:
                key = " ".join(args[2:]).strip()
            else:
                key = prompt_secret(f"\nEnter API key for {prov}: ")
                
            if not key:
                console.print("[yellow]No key entered. Cancelled.[/yellow]")
                return False
                
            set_api_key(prov, key)
            masked = key[-4:].rjust(len(key), "*") if len(key) > 4 else "****"
            console.print(f"[dim]API key for {prov} securely stored ({masked}).[/dim]")
            
        elif sub == "remove" and len(args) > 1:
            prov = args[1].lower()
            if prov == "all":
                removed_any = False
                for p in ["openai", "groq", "gemini", "anthropic", "openrouter", "custom", "vision"]:
                    if delete_api_key(p):
                        removed_any = True
                if removed_any:
                    console.print("\n[dim]All stored API keys removed.[/dim]")
                else:
                    console.print("\n[yellow]No stored API keys found to remove.[/yellow]")
            elif delete_api_key(prov):
                console.print(f"\n[dim]Removed API key for {prov}.[/dim]")
            else:
                console.print(f"\n[yellow]No stored key found for {prov}.[/yellow]")
                
        else:
            console.print("\n[red]Unknown provider command.[/red]")

    elif cmd == "/planner":
        if not args:
            p = config.get("planner", {})
            console.print(f"\n[bold]Current Planner:[/] {p.get('provider', 'Not set')} / {p.get('model', 'Not set')}")
        else:
            sub = args[0].lower()
            if sub == "set" and len(args) > 2:
                if "planner" not in config:
                    config["planner"] = {}
                config["planner"]["provider"] = args[1].lower()
                config["planner"]["model"] = args[2]
                save_config(config)
                console.print(f"\n[dim]Planner set to: {config['planner']['provider']} / {config['planner']['model']}[/dim]")

    elif cmd == "/executor":
        if not args:
            p = config.get("executor", {})
            console.print(f"\n[bold]Current Executor:[/] {p.get('provider', 'Not set')} / {p.get('model', 'Not set')}")
        else:
            sub = args[0].lower()
            if sub == "set" and len(args) > 2:
                if "executor" not in config:
                    config["executor"] = {}
                config["executor"]["provider"] = args[1].lower()
                config["executor"]["model"] = args[2]
                save_config(config)
                console.print(f"\n[dim]Executor set to: {config['executor']['provider']} / {config['executor']['model']}[/dim]")
            
    elif cmd == "/memory":
        from scout.memory.store import get_memory_store
        mem_store = get_memory_store()
        
        if not args:
            console.print("\n" + mem_store.get_summary())
        else:
            sub = args[0].lower()
            if sub == "search" and len(args) > 1:
                q = " ".join(args[1:])
                res = mem_store.search(q)
                if not res:
                    console.print(f"\n[yellow]No memories found for '{q}'.[/yellow]")
                else:
                    console.print("\n[bold cyan]Search Results:[/]")
                    for r in res:
                        console.print(f"  [{r['category']}] {r['key']}: {r['value']}")
            elif sub == "list":
                cat = args[1] if len(args) > 1 else None
                conn = mem_store._get_conn()
                if cat:
                    rows = conn.execute("SELECT category, key, value FROM memories WHERE category = ? ORDER BY key", (cat,)).fetchall()
                else:
                    rows = conn.execute("SELECT category, key, value FROM memories ORDER BY category, key").fetchall()
                if not rows:
                    console.print(f"\n[yellow]No memories found{' for category ' + cat if cat else ''}.[/yellow]")
                else:
                    console.print(f"\n[bold cyan]Saved Memories ({len(rows)} total):[/]")
                    current_cat = None
                    for r in rows:
                        if r['category'] != current_cat:
                            current_cat = r['category']
                            console.print(f"\n[bold]{current_cat}[/]")
                        console.print(f"  [green]{r['key']}[/green]: {r['value']}")
            elif sub == "set" and len(args) > 2:
                key = args[1]
                val = " ".join(args[2:])
                mem_store.save("preferences", key, val)
                console.print(f"\n[dim]Memory saved: {key} = {val}[/dim]")
            elif sub == "delete" and len(args) > 1:
                key = args[1]
                # Try deleting from preferences first, then user_profile, etc
                deleted = mem_store.delete("preferences", key)
                if not deleted:
                    deleted = mem_store.delete("user_profile", key)
                if deleted:
                    console.print(f"\n[dim]Memory deleted: {key}[/dim]")
                else:
                    console.print(f"\n[yellow]Memory '{key}' not found.[/yellow]")
            elif sub == "clear":
                from rich.prompt import Confirm
                if Confirm.ask("\n[bold red]Clear all memories?[/]", default=False):
                    cnt = mem_store.clear_all()
                    console.print(f"[dim]Cleared {cnt} memories.[/dim]")
            else:
                console.print("\n[red]Unknown memory command.[/red] Usage: /memory [search <q> | list [cat] | set <k> <v> | delete <k> | clear]")

    elif cmd == "/vision":
        if not args:
            v_prov = config.get("vision", {}).get("provider", "Not configured explicitly")
            v_model = config.get("vision", {}).get("model", "Default")
            console.print(f"\n[bold]Current Vision Settings:[/]")
            console.print(f"Provider: {v_prov}")
            console.print(f"Model: {v_model}")
            from scout.vision.core import get_vision_provider
            p = get_vision_provider(config)
            if p:
                console.print(f"\n[bold green]Active Vision Provider:[/] {p.name} ({p.model})")
            else:
                console.print("\n[yellow]No vision provider active (main model may not support vision, and no explicit vision model set).[/yellow]")
        else:
            sub = args[0].lower()
            if sub == "set":
                if "vision" not in config:
                    config["vision"] = {}
                if len(args) > 2:
                    config["vision"]["provider"] = args[1].lower()
                    config["vision"]["model"] = args[2]
                elif len(args) > 1:
                    # Backwards compatibility: default to ollama if only model provided
                    config["vision"]["provider"] = "ollama"
                    config["vision"]["model"] = args[1]
                else:
                    config["vision"]["provider"] = ""
                    config["vision"]["model"] = ""
                save_config(config)
                console.print(f"\n[dim]Vision model set to: {config['vision'].get('provider')} / {config['vision'].get('model', 'Auto')}[/dim]")
            elif sub == "key":
                key = prompt_secret("Enter API key for dedicated Vision")
                if key:
                    set_api_key("vision", key)
                    console.print("\n[green]API key saved for vision.[/green]")
            elif sub == "test":
                from scout.vision.core import get_vision_provider
                from scout.vision.capture import take_screenshot
                p = get_vision_provider(config)
                if not p:
                    console.print("\n[red]No vision provider configured.[/red]")
                else:
                    with console.status("[bold cyan]Taking screenshot & analyzing...[/]"):
                        cap = take_screenshot()
                        if not cap.get("success"):
                            console.print(f"\n[red]Screenshot failed:[/] {cap.get('error')}")
                        else:
                            res = p.analyze(cap["path"], "Briefly describe what is on the screen.")
                            if res.get("success"):
                                console.print(f"\n[bold green]Vision Test Success![/]\n{res['observation']}")
                            else:
                                console.print(f"\n[red]Vision Test Failed:[/] {res['observation']}")
            else:
                console.print("\n[red]Unknown vision command.[/red] Usage: /vision [set <prov> <model> | key | test]")

    elif cmd == "/voice":
        global _voice_mode
        if not args:
            _voice_mode = not _voice_mode
            console.print(f"\n[dim]Voice mode {'enabled' if _voice_mode else 'disabled'} (STT & TTS).[/dim]")
            if not _voice_mode:
                try:
                    from scout.voice.tts import stop_speaking
                    stop_speaking()
                except ImportError:
                    pass
        else:
            sub = args[0].lower()
            if sub == "on":
                _voice_mode = True
                console.print("\n[dim]Voice mode enabled.[/dim]")
            elif sub == "off":
                _voice_mode = False
                try:
                    from scout.voice.tts import stop_speaking
                    stop_speaking()
                except ImportError:
                    pass
                console.print("\n[dim]Voice mode disabled.[/dim]")
            elif sub == "stt-provider" and len(args) > 1:
                prov = args[1].lower()
                if prov not in ("groq", "local"):
                    console.print("\n[red]Invalid provider.[/red] Use: /voice stt-provider [groq|local]")
                    return False
                if "voice" not in config:
                    config["voice"] = {}
                config["voice"]["provider"] = prov
                save_config(config)
                console.print(f"\n[dim]STT provider set to: {prov}[/dim]")
            elif sub == "tts-profile" and len(args) > 1:
                if "tts" not in config:
                    config["tts"] = {}
                config["tts"]["voice"] = args[1]
                save_config(config)
                console.print(f"\n[dim]TTS voice profile set to: {args[1]}[/dim]")
            elif sub == "tts-speed" and len(args) > 1:
                if "tts" not in config:
                    config["tts"] = {}
                try:
                    config["tts"]["speed"] = float(args[1])
                    save_config(config)
                    console.print(f"\n[dim]TTS speed set to: {args[1]}[/dim]")
                except ValueError:
                    console.print("\n[red]Invalid speed value. Must be a number.[/red]")
            else:
                console.print("\n[red]Unknown voice command.[/red] Usage: /voice [on|off | stt-provider <p> | tts-profile <name> | tts-speed <val>]")
                return False

    elif cmd == "/help":
        console.print("\n[bold]Scout Commands[/]")
        console.print("/quit, /exit, /q         Exit Scout")
        console.print("/clear                   Clear terminal")
        console.print("/new                     Start new chat")
        console.print("/provider                Show configuration and API keys")
        console.print("/provider key <p>        Enter API key for a provider")
        console.print("/provider remove <p>     Remove stored key (or use 'all')")
        console.print("/planner set <p> <m>     Set the high-level reasoning model")
        console.print("/executor set <p> <m>    Set the low-level execution model")
        console.print("/memory                  Show memory summary")
        console.print("/memory list [cat]       List all saved memories or by category")
        console.print("/memory search <q>       Search memories")
        console.print("/memory set <k> <v>      Store a preference/fact")
        console.print("/memory delete <k>       Delete a memory")
        console.print("/memory clear            Clear all memories")
        console.print("/vision                  Show vision status")
        console.print("/vision set <p> <m>      Set vision provider & model")
        console.print("/vision key              Set dedicated vision API key")
        console.print("/vision test             Test vision capabilities")
        console.print("/voice [on|off]          Toggle voice mode (STT & TTS)")
        console.print("/voice stt-provider <p>  Set STT provider (groq | local)")
        console.print("/voice tts-profile <n>   Set TTS voice profile (e.g. af_bella)")
        console.print("/voice tts-speed <val>   Set TTS speech speed (e.g. 1.0)")
        console.print("/help                    Show commands\n")

    else:
        console.print(f"\n[red]Unknown command:[/] {cmd}. Type /help for available commands.\n")

    return False


def _chat_cmd(args: list[str]) -> None:
    """Interactive conversational session with the AI."""
    console.print("[bold cyan]SCOUT AI Chat[/] (type 'exit' or 'quit' to end)")
    interpreter = _get_interpreter()
    
    while True:
        try:
            from rich.prompt import Prompt
            global _voice_mode
            
            if _voice_mode:
                req = Prompt.ask("\n[bold green]❯ You[/] [dim](Press Enter to talk, or type a command)[/dim]").strip()
                try:
                    from scout.voice.tts import stop_speaking
                    stop_speaking()
                except ImportError:
                    pass
                if not req:
                    from scout.voice.stt import transcribe_audio
                    req = transcribe_audio()
                    if not req:
                        continue
                    console.print(f"\n[bold green]❯ You said:[/] {req}")
            else:
                req = Prompt.ask("\n[bold green]❯ You[/]").strip()
                try:
                    from scout.voice.tts import stop_speaking
                    stop_speaking()
                except ImportError:
                    pass
                
            if not req:
                continue
                
            if req.startswith("/"):
                should_exit = _handle_slash_command(req)
                if should_exit:
                    console.print("\n[dim]Chat session ended.[/dim]")
                    break
                continue
                
            if req.lower() in ("exit", "quit"):
                console.print("\n[dim]Chat session ended.[/dim]")
                break
            
            config = load_config()
            if "planner" in config and config["planner"].get("provider") and "executor" in config and config["executor"].get("provider"):
                from scout.ai import get_provider
                from scout.ai.planner import Planner
                from scout.ai.interpreter import AIInterpreter, EXECUTOR_PROMPT
                from scout.ai.orchestrator import run_planned_turn
                
                planner_prov = get_provider({"ai": config["planner"]})
                planner = Planner(planner_prov)
                
                exec_prov = get_provider({"ai": config["executor"]})
                
                # If we don't already have an executor, create one. Otherwise, reuse it to keep context.
                if not getattr(interpreter, "is_executor", False):
                    interpreter = AIInterpreter(exec_prov, system_prompt=EXECUTOR_PROMPT)
                    interpreter.is_executor = True
                else:
                    interpreter.provider = exec_prov
                
                # Plan -> show plan -> execute each step exactly as shown.
                run_planned_turn(interpreter, planner, req)
            else:
                interpreter.chat_turn(req)
        except KeyboardInterrupt:
            console.print("\n[yellow]Input cancelled.[/yellow]")
            continue
        except EOFError:
            console.print("\n[dim]Chat session ended.[/dim]")
            break
        except Exception as e:
            from rich.markup import escape
            console.print(f"[red]AI Error:[/] {escape(str(e))}")

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
