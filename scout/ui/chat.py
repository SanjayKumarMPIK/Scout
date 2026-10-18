"""Scout Terminal V2 — Conversation Area & Message Presentation.

Features:
- Borderless, clean typography and spacing instead of large rectangular panels.
- User input prompt: clearly designated as `YOU › ` with no duplicate Scout wordmark.
- Scout responses: clean typography with teal identity marker `SCOUT ✦`, formatted Markdown, and subtle turn completion pill.
- Tool activity: compact, muted, visually secondary (`╶─ ⬡ executing...`, `╶─ ⬢ completed...`).
- Errors: distinct but restrained warning lines.
- Execution plans: clean indented visual hierarchy with subtle fine separators.
"""

from __future__ import annotations

import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.padding import Padding
from rich.text import Text

from scout.ui.theme import THEME_COLORS, scout_theme

# Ensure stdout uses UTF-8 where possible on Windows
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.prompt import Prompt

console = Console(theme=scout_theme)


class ScoutPrompt(Prompt):
    """Custom prompt with clean trailing space and no default colon."""
    prompt_suffix = ""


def get_prompt_markup() -> str:
    """Return the distinctive persistent user prompt markup: YOU › """
    c_cyan = THEME_COLORS["primary"]
    c_teal = THEME_COLORS["secondary"]
    return f"\n  [bold {c_cyan}]YOU[/] [bold {c_teal}]›[/] "


def prompt_user(custom_prompt: str | None = None) -> str:
    """Prompt the user for input without any trailing colon or duplicate tags."""
    markup = custom_prompt if custom_prompt is not None else get_prompt_markup()
    return ScoutPrompt.ask(markup).strip()


def print_user_message(text: str) -> None:
    """Print the user's message clearly marked with a subtle cyan identifier."""
    if not text:
        return
    text = text.strip()
    c_cyan = THEME_COLORS["primary"]
    c_teal = THEME_COLORS["secondary"]
    c_dim = THEME_COLORS["dim"]
    c_border = THEME_COLORS["border"]

    console.print()
    lines = text.split("\n")
    if len(lines) == 1:
        console.print(f"  [bold {c_cyan}]YOU[/] [bold {c_teal}]›[/] [text]{escape(lines[0])}[/]")
    else:
        console.print(f"  [bold {c_cyan}]YOU[/] [bold {c_teal}]›[/]")
        for line in lines:
            console.print(f"  [{c_border}]│[/{c_border}] [text]{escape(line)}[/]")
    console.print()


def print_scout_message(text: str) -> None:
    """Print Scout's response with clean typography, teal identity marker, and no boxed panels."""
    if not text:
        return
    text = text.strip()
    c_teal = THEME_COLORS["teal"]
    c_cyan = THEME_COLORS["primary"]
    c_dim = THEME_COLORS["dim"]

    console.print()
    console.print(f"  [bold {c_teal}]SCOUT[/] [bold {c_cyan}]✦[/]")
    
    # Parse Markdown for rich styling, headers, lists, and code blocks
    try:
        md = Markdown(text, code_theme="monokai", justify="left")
        console.print(Padding(md, (0, 0, 0, 4)))
    except Exception:
        # Fallback to escaped plain text if markdown parser fails
        for line in text.split("\n"):
            console.print(f"    [text]{escape(line)}[/]")

    console.print(f"    [{c_dim}]╺━━ scout[/{c_dim}] [{c_teal}]✦[/{c_teal}] [{c_dim}]turn completed[/{c_dim}]")
    console.print()


def print_scout_acknowledgment(text: str) -> None:
    """Print Scout's brief task acknowledgment before planning and execution begins."""
    if not text:
        return
    text = text.strip()
    c_teal = THEME_COLORS["teal"]
    c_cyan = THEME_COLORS["primary"]

    console.print()
    console.print(f"  [bold {c_teal}]SCOUT[/] [bold {c_cyan}]✦[/] [italic text]{escape(text)}[/]")
    console.print()


def print_scout_status(status: str, state: str = "idle") -> None:
    """Print compact, muted, visually secondary tool/progress activity."""
    c_cyan = THEME_COLORS["primary"]
    c_ice = THEME_COLORS["ice"]
    c_mint = THEME_COLORS["success"]
    c_coral = THEME_COLORS["error"]
    c_dim = THEME_COLORS["dim"]

    state_lower = state.lower()
    if state_lower == "executing":
        icon = f"[{c_cyan}]⬡[/{c_cyan}]"
        label = f"[{c_dim}]executing[/{c_dim}]"
        detail = f"[{c_ice}]{escape(status)}[/{c_ice}]"
    elif state_lower == "verifying":
        icon = f"[{c_ice}]◎[/{c_ice}]"
        label = f"[{c_cyan}]verifying[/{c_cyan}]"
        detail = f"[{c_dim}]{escape(status)}[/{c_dim}]"
    elif state_lower == "success":
        icon = f"[{c_mint}]⬢[/{c_mint}]"
        label = f"[{c_mint}]completed[/{c_mint}]"
        detail = f"[{c_dim}]{escape(status)}[/{c_dim}]"
    elif state_lower == "error":
        icon = f"[{c_coral}]▲[/{c_coral}]"
        label = f"[{c_coral}]failed[/{c_coral}]"
        detail = f"[{c_dim}]{escape(status)}[/{c_dim}]"
    elif state_lower == "listening":
        icon = f"[{c_ice}]⬡[/{c_ice}]"
        label = f"[{c_ice}]listening[/{c_ice}]"
        detail = f"[{c_dim}]{escape(status)}[/{c_dim}]"
    else:
        icon = f"[{c_dim}]⬡[/{c_dim}]"
        label = f"[{c_dim}]info[/{c_dim}]"
        detail = f"[{c_dim}]{escape(status)}[/{c_dim}]"

    console.print(f"    [{c_dim}]╺━━[/{c_dim}] {icon} {label} {detail}")


def print_command_output(command: str, output: str, max_lines: int = 12) -> None:
    """Display command execution output so the user can verify what happened."""
    if not output or not output.strip():
        return
    c_dim = THEME_COLORS["dim"]
    c_border = THEME_COLORS["border"]
    c_text = THEME_COLORS["text_muted"]
    c_ice = THEME_COLORS["ice"]

    text = output.strip()
    if text.startswith("Command completed (exit 0)\n"):
        text = text[len("Command completed (exit 0)\n"):].strip()
    elif text == "Command completed (exit 0)":
        return

    if not text:
        return

    lines = text.split("\n")
    display_lines = lines[:max_lines]

    cmd_label = f"[{c_ice}]{escape(command)}[/{c_ice}]" if command else "output"
    console.print(f"    [{c_border}]┌─ output ({cmd_label}) ────────────────────────[/{c_border}]")
    for line in display_lines:
        console.print(f"    [{c_border}]│[/{c_border}] [{c_text}]{escape(line)}[/{c_text}]")
    if len(lines) > max_lines:
        console.print(f"    [{c_border}]│[/{c_border}] [{c_dim}]... ({len(lines) - max_lines} more lines)[/{c_dim}]")
    console.print(f"    [{c_border}]└─────────────────────────────────────────────────[/{c_border}]")


def print_scout_error(error: str) -> None:
    """Print a distinct but restrained error line without large bulky panels."""
    c_coral = THEME_COLORS["error"]
    console.print()
    console.print(f"  [bold {c_coral}]▲ SYSTEM ERROR:[/] [{c_coral}]{escape(error)}[/{c_coral}]")
    console.print()


def print_plan_overview(steps: list[str], title: str = "Execution Plan") -> None:
    """Display an execution plan with clean hierarchy and subtle dividers."""
    c_cyan = THEME_COLORS["primary"]
    c_ice = THEME_COLORS["ice"]
    c_border = THEME_COLORS["border"]

    console.print()
    console.print(f"  [bold {c_cyan}]⬡ {title.upper()}[/]  [{c_border}]" + "─" * 45 + f"[/{c_border}]")
    for i, step in enumerate(steps, 1):
        console.print(f"    [{c_cyan}]{i}.[/{c_cyan}] [{c_ice}]{escape(step)}[/{c_ice}]")
    console.print(f"  [{c_border}]" + "─" * (len(title) + 50) + f"[/{c_border}]")
    console.print()


def print_status_bar(state: str = "IDLE", voice_mode: bool = False, provider: str = "groq") -> None:
    """Print a minimal status line at the footer."""
    c_mint = THEME_COLORS["success"]
    c_cyan = THEME_COLORS["primary"]
    c_dim = THEME_COLORS["dim"]

    st_color = c_mint if state.upper() in ("IDLE", "READY") else c_cyan
    v_text = "ON" if voice_mode else "OFF"
    
    console.print(f"  [dim]STATUS:[/] [{st_color}]{state.lower()}[/]  [dim]┆ PROVIDER:[/] [dim]{provider}[/]  [dim]┆ VOICE:[/] [dim]{v_text}[/dim]")
