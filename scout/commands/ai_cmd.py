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
    config = load_config()
    
    if "planner" in config and config["planner"].get("provider") and "executor" in config and config["executor"].get("provider"):
        from scout.ai import get_provider
        from scout.ai.planner import Planner
        from scout.ai.interpreter import AIInterpreter, SYSTEM_PROMPT
        
        console.print("[bold cyan]Dual Architecture Mode Active[/]")
        planner_prov = get_provider({"ai": config["planner"]})
        planner = Planner(planner_prov)
        
        exec_prov = get_provider({"ai": config["executor"]})
        executor_prompt = SYSTEM_PROMPT + "\n\n17. STRICT EXECUTION: You are an executor. You MUST follow the exact plan provided in your instructions. Execute the steps precisely. Do not deviate."
        executor = AIInterpreter(exec_prov, system_prompt=executor_prompt)
        
        plan = planner.generate_plan(request)
        if not plan:
            console.print("[red]Planner failed to generate a plan. Aborting.[/]")
            return
            
        plan_md = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
        from rich.panel import Panel
        from rich.markdown import Markdown
        console.print(Panel(Markdown(plan_md), title="[dim magenta]⚙ Execution Plan[/]", title_align="left", border_style="dim magenta", padding=(0, 2), style="dim"))
            
        plan_str = f"USER REQUEST: {request}\n\nEXECUTOR PLAN TO FOLLOW:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
        
        try:
            executor.ask(plan_str)
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

    elif cmd == "/model":
        if not args:
            if "planner" in config and config["planner"].get("provider") and "executor" in config and config["executor"].get("provider"):
                p_prov = config["planner"].get("provider", "Not set")
                p_mod = config["planner"].get("model", "Not set")
                e_prov = config["executor"].get("provider", "Not set")
                e_mod = config["executor"].get("model", "Not set")
                console.print("\n[bold cyan]Dual Architecture Active[/]")
                console.print(f"Planner:  {p_prov} / {p_mod}")
                console.print(f"Executor: {e_prov} / {e_mod}\n")
            else:
                provider = config["ai"].get("provider", "Not set")
                model = config["ai"].get("model", "Not set")
                console.print(f"\nCurrent Monolithic Model:\nProvider: {provider}\nModel: {model}\n")
        else:
            if "planner" in config and config["planner"].get("provider") and "executor" in config and config["executor"].get("provider"):
                console.print("[yellow]Dual architecture is active. Use '/planner set <p> <m>' or '/executor set <p> <m>' instead of '/model'.[/yellow]")
            else:
                model_name = args[0]
                config["ai"]["model"] = model_name
                save_config(config)
                if _interpreter:
                    _interpreter.provider.model = model_name
                console.print(f"\n[dim]Model changed to: {model_name}[/dim]")

    elif cmd == "/provider":
        if not args:
            provider = config["ai"].get("provider", "Not set")
            console.print(f"\n[bold]Current Provider:[/] {provider}")
            console.print("Available: ollama, groq, openai, gemini, anthropic, openrouter, custom\n")
            return False
            
        sub = args[0].lower()
        if sub == "set" and len(args) > 1:
            prov = args[1].lower()
            if prov not in ["ollama", "groq", "openai", "gemini", "anthropic", "openrouter", "custom"]:
                console.print(f"\n[red]Unknown provider:[/] {prov}")
                return False
                
            config["ai"]["provider"] = prov
            save_config(config)
            console.print(f"\n[dim]Provider set to {prov}. Use '/model <model_name>' to update the model.[/dim]")
            
            if _interpreter:
                from scout.ai import get_provider
                try:
                    _interpreter.provider = get_provider(config)
                    console.print(f"[dim]Interpreter re-initialized with {prov}.[/dim]")
                except Exception as e:
                    console.print(f"[red]Failed to initialize {prov}:[/] {e}")

        elif sub == "key":
            prov = config["ai"].get("provider", "groq")
            if prov == "ollama":
                console.print("\n[yellow]Ollama does not require an API key.[/yellow]")
                return False
            # Allow: /provider key sk-xxxxxxx  (direct paste)
            if len(args) > 1:
                key = " ".join(args[1:]).strip()
            else:
                key = prompt_secret(f"\nEnter API key for {prov}: ")
            if not key:
                console.print("[yellow]No key entered. Cancelled.[/yellow]")
                return False
            set_api_key(prov, key)
            masked = key[-4:].rjust(len(key), "*") if len(key) > 4 else "****"
            console.print(f"[dim]API key for {prov} securely stored ({masked}).[/dim]")
            
        elif sub == "keys":
            from scout.core.auth import get_api_key
            console.print("\n[bold]Stored API Keys:[/]")
            found = False
            for p in ["openai", "groq", "gemini", "anthropic", "openrouter", "custom", "vision"]:
                if get_api_key(p):
                    console.print(f"  - [green]{p}[/green]: [dim]Stored[/dim]")
                    found = True
            if not found:
                console.print("  [dim]No API keys currently stored.[/dim]")
            console.print("\n[dim]Use '/provider remove <provider>' or '/provider remove all' to delete keys.[/dim]")
            
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
                
        elif sub == "test":
            if _interpreter:
                success, msg = _interpreter.provider.test_connection()
            else:
                from scout.ai import get_provider
                try:
                    p = get_provider(config)
                    success, msg = p.test_connection()
                except Exception as e:
                    success, msg = False, str(e)
            
            if success:
                console.print(f"\n[green]Test passed:[/] {msg}")
            else:
                console.print(f"\n[red]Test failed:[/] {msg}")
                
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
                console.print("\n[red]Unknown memory command.[/red] Usage: /memory [search <q> | set <k> <v> | delete <k> | clear]")

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

    elif cmd == "/computer":
        from scout.computer.controller import get_computer_controller
        ctrl = get_computer_controller()
        if not args:
            state = ctrl.get_state()
            enabled_str = "[green]enabled[/green]" if state["enabled"] else "[red]disabled[/red]"
            console.print(f"\n[bold]Computer Control:[/] {enabled_str}")
            console.print(f"Active Window: {state['active_window']}")
            console.print(f"Screen: {state['screen_width']}x{state['screen_height']}")
            console.print(f"Mouse: ({state['mouse_position']['x']}, {state['mouse_position']['y']})")
        else:
            sub = args[0].lower()
            if sub == "on":
                ctrl.enabled = True
                console.print("\n[dim]Computer control enabled.[/dim]")
            elif sub == "off":
                ctrl.enabled = False
                console.print("\n[dim]Computer control disabled.[/dim]")
            else:
                console.print("\n[red]Unknown computer command.[/red] Usage: /computer [on|off]")

    elif cmd == "/help":
        console.print("\n[bold]Scout Commands[/]")
        console.print("/quit, /exit, /q     Exit Scout")
        console.print("/clear               Clear terminal")
        console.print("/new                 Start new chat")
        console.print("/model               Show current provider & model")
        console.print("/model <name>        Switch to a specific model")
        console.print("/provider            Show current and available providers")
        console.print("/provider set <prov> Select a provider")
        console.print("/provider key        Enter API key (interactive prompt)")
        console.print("/provider key <key>  Set API key directly (paste)")
        console.print("/provider keys       List all stored API keys")
        console.print("/provider remove <p> Remove stored key (or use 'all')")
        console.print("/provider test       Test provider connection")
        console.print("/planner set <p> <m> Set the high-level reasoning model")
        console.print("/executor set <p> <m> Set the low-level execution model")
        console.print("/memory              Show memory summary")
        console.print("/memory search <q>   Search memories")
        console.print("/memory set <k> <v>  Store a preference/fact")
        console.print("/memory delete <k>   Delete a memory")
        console.print("/memory clear        Clear all memories")
        console.print("/vision              Show vision status")
        console.print("/vision set <p> <m>  Set vision provider & model")
        console.print("/vision key          Set dedicated vision API key")
        console.print("/vision test         Test vision capabilities")
        console.print("/computer            Show computer control state")
        console.print("/computer on|off     Enable or disable computer control")
        console.print("/help                Show commands\n")

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
            req = Prompt.ask("\n[bold green]❯ You[/]").strip()
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
                from scout.ai.interpreter import AIInterpreter, SYSTEM_PROMPT
                
                planner_prov = get_provider({"ai": config["planner"]})
                planner = Planner(planner_prov)
                
                exec_prov = get_provider({"ai": config["executor"]})
                executor_prompt = SYSTEM_PROMPT + "\n\n17. STRICT EXECUTION: You are an executor. You MUST follow the exact plan provided in your instructions. Execute the steps precisely. Do not deviate."
                
                # If we don't already have an executor, create one. Otherwise, reuse it to keep context.
                if not getattr(interpreter, "is_executor", False):
                    interpreter = AIInterpreter(exec_prov, system_prompt=executor_prompt)
                    interpreter.is_executor = True
                else:
                    interpreter.provider = exec_prov
                
                # Get a comprehensive recent execution log for the planner
                mem_context = "Recent Execution Log (Context for planning):\n"
                for msg in interpreter.messages[-20:]:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if role == "user":
                        # The user message usually contains "USER REQUEST: ... \n\n EXECUTOR PLAN..."
                        # We just want to remind the planner of the raw user request if possible
                        if "USER REQUEST:" in content:
                            req_part = content.split("EXECUTOR PLAN TO FOLLOW:")[0].strip()
                            mem_context += f"User: {req_part}\n"
                        else:
                            mem_context += f"User: {content}\n"
                    elif role == "assistant":
                        if content:
                            mem_context += f"Executor (Spoke): {content}\n"
                        if "tool_calls" in msg:
                            for tc in msg["tool_calls"]:
                                func = tc.get("function", {}).get("name", "")
                                args = tc.get("function", {}).get("arguments", "")
                                mem_context += f"Executor (Tool Call): {func}({args})\n"
                    elif role == "tool":
                        mem_context += f"System (Tool Result): {content[:300]}...\n"
                
                plan = planner.generate_plan(req, memory_context=mem_context)
                if not plan:
                    console.print("[red]Planner failed to generate a plan.[/]")
                    continue
                    
                plan_md = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
                from rich.panel import Panel
                from rich.markdown import Markdown
                console.print(Panel(Markdown(plan_md), title="[dim magenta]⚙ Execution Plan[/]", title_align="left", border_style="dim magenta", padding=(0, 2), style="dim"))
                    
                plan_str = f"USER REQUEST: {req}\n\nEXECUTOR PLAN TO FOLLOW:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
                interpreter.chat_turn(plan_str)
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
