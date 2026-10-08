"""Scout Startup Sequence & Session Initializer."""

import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align

from scout import __version__
from scout.ui.avatar import get_neural_core
from scout.ui.header import print_persistent_header as _print_persistent_header
from scout.ui.theme import THEME_COLORS, scout_theme

# Ensure UTF-8 on Windows
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(theme=scout_theme)


def get_scout_core(frame: int, state: str = "idle") -> Text:
    """Return the stylized SCOUT NEURAL CORE (preserves backward compatibility)."""
    return get_neural_core(frame=frame, state=state)


def animate_startup() -> None:
    """Display the cinematic startup sequence with the Scout Neural Core."""
    c_cyan = THEME_COLORS["primary"]
    c_dim = THEME_COLORS["dim"]
    c_border = THEME_COLORS["border"]

    # 1. Clear screen
    console.clear()

    # 2. Subsystem verification sequence
    messages = [
        "Intelligence engine ........ [bold #34D399]READY[/]",
        "Computer interface ......... [bold #34D399]READY[/]",
        "Memory system .............. [bold #34D399]READY[/]",
        "Voice interface ............ [bold #34D399]READY[/]",
    ]

    with Live(refresh_per_second=12, console=console, transient=True) as live:
        # Phase 1: Core neural spinup
        for i in range(6):
            header = Text.from_markup(f"\n[bold {c_cyan}]SCOUT[/] [dim]v{__version__}[/]\n[{c_dim}]PERSONAL AI AGENT[/{c_dim}]\n")
            core = get_neural_core(i, "starting" if i < 3 else "idle")

            panel = Panel(
                Align.center(Text.assemble(header, "\n", core, "\n\n", "SYSTEM INITIALIZING...")),
                border_style=c_border,
                padding=(1, 4)
            )
            live.update(Align.center(panel, vertical="middle"))
            time.sleep(0.12)

        # Phase 2: Subsystem illumination
        current_msgs = []
        for msg in messages:
            current_msgs.append(msg)
            msg_text = "\n".join(current_msgs)

            header = Text.from_markup(f"\n[bold {c_cyan}]SCOUT[/] [dim]v{__version__}[/]\n[{c_dim}]PERSONAL AI AGENT[/{c_dim}]\n")
            core = get_neural_core(len(current_msgs), "idle")

            content = Text.assemble(header, "\n", core, "\n\n", Text.from_markup(msg_text))

            panel = Panel(
                Align.center(content),
                border_style=c_border,
                padding=(1, 4)
            )
            live.update(Align.center(panel, vertical="middle"))
            time.sleep(0.18)

        time.sleep(0.3)


def print_persistent_header(model_name: str) -> None:
    """Print the persistent session header and identity area."""
    _print_persistent_header(model_name=model_name)
