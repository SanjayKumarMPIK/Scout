"""Terminal logging for Scout web operations."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from scout.ui.theme import THEME_COLORS, scout_theme

console = Console(theme=scout_theme)


def log_web_event(message: str, event_type: str = "info") -> None:
    """Print clean, faded web activity updates without cluttering the screen."""
    symbols = {
        "search": "⌕",
        "fetch": "↓",
        "browser": "🌐",
        "extract": "⚡",
        "success": "✔",
        "error": "▲",
    }
    symbol = symbols.get(event_type, "•")
    console.print(f"  [dim][WEB] {symbol} {escape(message)}[/dim]")
