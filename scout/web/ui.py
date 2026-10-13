"""Terminal logging for Scout web operations."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from scout.ui.theme import THEME_COLORS, scout_theme

console = Console(theme=scout_theme)


def log_web_event(message: str, event_type: str = "info") -> None:
    """Print clean, concise web activity updates without cluttering the screen."""
    c_cyan = THEME_COLORS.get("primary", "cyan")
    c_teal = THEME_COLORS.get("secondary", "teal")
    c_ice = THEME_COLORS.get("ice", "bright_white")
    c_mint = THEME_COLORS.get("success", "green")
    c_coral = THEME_COLORS.get("error", "red")
    c_dim = THEME_COLORS.get("dim", "dim")

    if event_type == "search":
        prefix = f"  [bold {c_cyan}][WEB][/] [bold {c_teal}]⌕[/]"
        text = f"[{c_ice}]{escape(message)}[/{c_ice}]"
    elif event_type == "fetch":
        prefix = f"  [bold {c_cyan}][WEB][/] [bold {c_teal}]↓[/]"
        text = f"[{c_ice}]{escape(message)}[/{c_ice}]"
    elif event_type == "browser":
        prefix = f"  [bold {c_cyan}][WEB][/] [bold {c_teal}]🌐[/]"
        text = f"[{c_ice}]{escape(message)}[/{c_ice}]"
    elif event_type == "extract":
        prefix = f"  [bold {c_cyan}][WEB][/] [bold {c_teal}]⚡[/]"
        text = f"[{c_ice}]{escape(message)}[/{c_ice}]"
    elif event_type == "success":
        prefix = f"  [bold {c_mint}][WEB][/] [bold {c_mint}]✔[/]"
        text = f"[{c_dim}]{escape(message)}[/{c_dim}]"
    elif event_type == "error":
        prefix = f"  [bold {c_coral}][WEB][/] [bold {c_coral}]▲[/]"
        text = f"[{c_coral}]{escape(message)}[/{c_coral}]"
    else:
        prefix = f"  [bold {c_cyan}][WEB][/]"
        text = f"[{c_dim}]{escape(message)}[/{c_dim}]"

    console.print(f"{prefix} {text}")
