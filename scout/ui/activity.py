"""Scout Terminal V2 — Compact Animated Activity Indicator.

Features:
- Non-intrusive activity indicator during long tasks or LLM thinking.
- Animated neural-pulse glyphs (⬡┄✦┄⬡).
- Clean exit without interfering with prompts, confirmations, or computer control.
"""

from __future__ import annotations

import contextlib
from typing import Generator
from rich.console import Console
from scout.ui.theme import THEME_COLORS, scout_theme

console = Console(theme=scout_theme)


def get_activity_markup(status_text: str, state: str = "thinking") -> str:
    """Format the compact animated activity indicator line."""
    c_cyan = THEME_COLORS["primary"]
    c_teal = THEME_COLORS["secondary"]
    c_glow = THEME_COLORS["glow"]
    c_ice = THEME_COLORS["ice"]
    c_dim = THEME_COLORS["dim"]

    state_lower = state.lower()
    if state_lower == "executing":
        badge = f"[{c_cyan}]⬢[/{c_cyan}][{c_ice}]━[/{c_ice}][{c_glow}]✦[/{c_glow}][{c_ice}]━[/{c_ice}][{c_cyan}]⬢[/{c_cyan}]"
    elif state_lower == "verifying":
        badge = f"[{c_ice}]⬡[/{c_ice}][{c_glow}]═[/{c_glow}][{c_cyan}]✦[/{c_cyan}][{c_glow}]═[/{c_glow}][{c_ice}]⬡[/{c_ice}]"
    elif state_lower == "listening":
        badge = f"[{c_cyan}]⬡[/{c_cyan}][{c_ice}]((✦))[/{c_ice}][{c_cyan}]⬡[/{c_cyan}]"
    else:
        badge = f"[{c_cyan}]⬡[/{c_cyan}][{c_teal}]┄[/{c_teal}][{c_glow}]✦[/{c_glow}][{c_teal}]┄[/{c_teal}][{c_cyan}]⬡[/{c_cyan}]"

    return f"  {badge} [{c_dim}]{status_text}[/{c_dim}]"


@contextlib.contextmanager
def scout_activity(status_text: str, state: str = "thinking") -> Generator[None, None, None]:
    """Context manager for long tasks or LLM thinking with compact spinner."""
    markup = get_activity_markup(status_text, state)
    with console.status(markup, spinner="dots"):
        yield
