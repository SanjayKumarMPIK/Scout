"""Scout Terminal V2 — Header, Identity Area & Telemetry Components.

Features:
- Telemetry Box displaying live runtime state, model, provider, host info, and tools count.
- Distinctive Identity Area with the animated SCOUT NEURAL CORE avatar beside the identity block.
- Quick Directives bar showing helpful system shortcuts.
- Fully auto-detects active configuration (Groq, Dual Engine, Ollama, etc.).
"""

from __future__ import annotations

import platform
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scout import __version__
from scout.ui.avatar import get_neural_core
from scout.ui.theme import THEME_COLORS, scout_theme

console = Console(theme=scout_theme)


def _get_active_runtime_info() -> dict:
    """Retrieve actual active runtime model and provider from configuration."""
    from scout.user_config import load_config
    cfg = load_config()

    has_planner = bool(cfg.get("planner", {}).get("provider"))
    has_executor = bool(cfg.get("executor", {}).get("provider"))

    ai_prov = cfg.get("ai", {}).get("provider", "groq")
    ai_mod = cfg.get("ai", {}).get("model", "openai/gpt-oss-120b")

    planner_prov = cfg.get("planner", {}).get("provider", "groq")
    planner_mod = cfg.get("planner", {}).get("model", "openai/gpt-oss-120b")
    exec_prov = cfg.get("executor", {}).get("provider", "gemini")
    exec_mod = cfg.get("executor", {}).get("model", "gemini-flash-lite-latest")

    return {
        "is_dual": has_planner and has_executor,
        "primary_provider": planner_prov if (has_planner and has_executor) else ai_prov,
        "primary_model": planner_mod if (has_planner and has_executor) else ai_mod,
        "planner_provider": planner_prov,
        "planner_model": planner_mod,
        "executor_provider": exec_prov,
        "executor_model": exec_mod,
    }


def build_telemetry_panel(
    model_name: str,
    provider_name: str,
    is_connected: bool = True,
    voice_mode: bool = False,
    agent_state: str = "ONLINE",
) -> Panel:
    """Build the high-tech System Telemetry box."""
    c_cyan = THEME_COLORS["primary"]
    c_teal = THEME_COLORS["secondary"]
    c_ice = THEME_COLORS["ice"]
    c_dim = THEME_COLORS["dim"]
    c_mint = THEME_COLORS["success"]
    c_border = THEME_COLORS["border"]

    tool_count = 18
    try:
        from scout.ai.tools import get_tools
        tool_count = len(get_tools())
    except Exception:
        pass

    os_info = f"Windows {platform.release()}" if platform.system() == "Windows" else platform.system()
    voice_text = "ON" if voice_mode else "OFF"

    table = Table.grid(padding=(0, 2))
    table.add_column("col1", justify="left")
    table.add_column("sep", justify="center")
    table.add_column("col2", justify="left")

    table.add_row(
        f"[bold {c_cyan}]SCOUT[/] [dim]v{__version__}[/] · [bold {c_mint}]{agent_state.upper()}[/]",
        f"[{c_border}]┆[/{c_border}]",
        f"[dim]ENGINE:[/] [{c_ice}]{model_name}[/{c_ice}] [{c_dim}]({provider_name})[/{c_dim}]"
    )
    table.add_row(
        f"[dim]HOST:[/] [text]{os_info}[/] · [{c_teal}]{tool_count} Tools Active[/{c_teal}]",
        f"[{c_border}]┆[/{c_border}]",
        f"[dim]VOICE:[/] [dim]{voice_text}[/] · [dim]MEMORY:[/] [{c_mint}]Active[/{c_mint}]"
    )

    return Panel(
        table,
        title=f"[bold {c_cyan}]SYSTEM TELEMETRY[/]",
        border_style=c_border,
        padding=(0, 2),
        expand=False,
    )


# Alias for backward compatibility
build_header = build_telemetry_panel


def build_identity_block(
    model_name: str = "openai/gpt-oss-120b",
    provider_name: str = "groq",
    is_connected: bool = True,
    voice_mode: bool = False,
    agent_state: str = "IDLE / READY",
    frame: int = 0,
) -> Table:
    """Build the side-by-side Identity Area: Neural Core Avatar + Identity metadata block."""
    c_cyan = THEME_COLORS["primary"]
    c_teal = THEME_COLORS["secondary"]
    c_ice = THEME_COLORS["ice"]
    c_dim = THEME_COLORS["dim"]
    c_mint = THEME_COLORS["success"]
    c_border = THEME_COLORS["border"]

    info = _get_active_runtime_info()

    # Render Neural Core Avatar
    state_key = "idle"
    if "exec" in agent_state.lower():
        state_key = "executing"
    elif "verif" in agent_state.lower():
        state_key = "verifying"
    elif "think" in agent_state.lower():
        state_key = "thinking"
    elif "listen" in agent_state.lower():
        state_key = "listening"
    elif "speak" in agent_state.lower():
        state_key = "speaking"

    avatar_text = get_neural_core(frame=frame, state=state_key)

    tool_count = 18
    try:
        from scout.ai.tools import get_tools
        tool_count = len(get_tools())
    except Exception:
        pass

    os_info = f"Windows {platform.release()}" if platform.system() == "Windows" else platform.system()
    voice_style = c_cyan if voice_mode else c_dim
    voice_status = "Active" if voice_mode else "Disabled"

    # Identity block lines
    if info["is_dual"]:
        id_lines = [
            f"  [bold {c_cyan}]SCOUT NEURAL CORE[/] [dim]v{__version__}[/]",
            f"  [{c_dim}]AUTONOMOUS PERSONAL AI AGENT[/{c_dim}]",
            f"  ",
            f"  [{c_dim}]STATE:[/]    [{c_mint}]● {agent_state}[/{c_mint}]",
            f"  [{c_dim}]PLANNER:[/]  [{c_ice}]{info['planner_model']}[/{c_ice}] [{c_dim}]({info['planner_provider']})[/{c_dim}]",
            f"  [{c_dim}]EXECUTOR:[/] [{c_ice}]{info['executor_model']}[/{c_ice}] [{c_dim}]({info['executor_provider']})[/{c_dim}]",
            f"  [{c_dim}]HOST:[/]     [{c_dim}]{os_info} · {tool_count} Tools Active · Memory Active[/{c_dim}]",
        ]
    else:
        id_lines = [
            f"  [bold {c_cyan}]SCOUT NEURAL CORE[/] [dim]v{__version__}[/]",
            f"  [{c_dim}]AUTONOMOUS PERSONAL AI AGENT[/{c_dim}]",
            f"  ",
            f"  [{c_dim}]STATE:[/]    [{c_mint}]● {agent_state}[/{c_mint}]",
            f"  [{c_dim}]ENGINE:[/]   [{c_ice}]{model_name}[/{c_ice}] [{c_dim}]({provider_name})[/{c_dim}]",
            f"  [{c_dim}]HOST:[/]     [{c_dim}]{os_info} · {tool_count} Tools Active · Memory Active[/{c_dim}]",
            f"  [{c_dim}]VOICE:[/]    [{voice_style}]STT/TTS {voice_status}[/{voice_style}]",
        ]

    id_text = Text.from_markup("\n".join(id_lines))
    divider_text = Text.from_markup("\n".join([f"[{c_border}]│[/{c_border}]"] * 7))

    grid = Table.grid(padding=(0, 2))
    grid.add_column("avatar", justify="left")
    grid.add_column("divider", justify="center")
    grid.add_column("identity", justify="left")

    grid.add_row(avatar_text, divider_text, id_text)
    return grid


def build_directives_bar() -> Panel:
    """Build the Quick Directives shortcut panel."""
    c_cyan = THEME_COLORS["primary"]
    c_dim = THEME_COLORS["dim"]
    c_border = THEME_COLORS["border"]

    items = [
        f"[bold {c_cyan}]/help[/] [dim]info[/]",
        f"[bold {c_cyan}]/voice[/] [dim]toggle[/]",
        f"[bold {c_cyan}]/provider[/] [dim]config[/]",
        f"[bold {c_cyan}]/memory[/] [dim]search[/]",
        f"[bold {c_cyan}]/clear[/] [dim]reset[/]",
        f"[bold {c_cyan}]/exit[/] [dim]quit[/]",
    ]
    sep = f"  [{c_border}]┆[/{c_border}]  "
    bar_content = f"[{c_dim}]DIRECTIVES:[/] " + sep.join(items)

    return Panel(
        bar_content,
        border_style=c_border,
        padding=(0, 2),
        expand=False,
    )


def print_persistent_header(
    model_name: str | None = None,
    provider_name: str | None = None,
    voice_mode: bool | None = None,
    agent_state: str = "IDLE / READY",
) -> None:
    """Print the complete, cohesive V2 terminal interface."""
    info = _get_active_runtime_info()

    if model_name is None or model_name == "unknown":
        model_name = info["primary_model"]

    if provider_name is None:
        provider_name = info["primary_provider"]

    if voice_mode is None:
        try:
            import scout.commands.ai_cmd as ai_cmd
            voice_mode = getattr(ai_cmd, "_voice_mode", False)
        except Exception:
            voice_mode = False

    telemetry_panel = build_telemetry_panel(
        model_name=model_name,
        provider_name=provider_name,
        is_connected=True,
        voice_mode=voice_mode,
        agent_state="ONLINE",
    )

    identity_grid = build_identity_block(
        model_name=model_name,
        provider_name=provider_name,
        is_connected=True,
        voice_mode=voice_mode,
        agent_state=agent_state,
    )

    directives_bar = build_directives_bar()

    console.print()
    console.print(telemetry_panel)
    console.print()
    console.print(identity_grid)
    console.print()
    console.print(directives_bar)
    console.print()
