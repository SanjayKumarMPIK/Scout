"""Scout Neural Core — Terminal-Compatible Animated Avatar.

Visual concept:
- Luminous cyan/teal central nucleus with breathing, rotation, and energy pulses.
- Multiple thin orbital rings surrounding the nucleus with orbiting satellites.
- Branching neural connections and peripheral synaptic nodes.
- Energy pulses travelling dynamically between nodes.
- Responsive to real agent states: idle, listening, thinking, executing, verifying, speaking, success, error.
"""

from __future__ import annotations

import sys
from rich.text import Text
from scout.ui.theme import THEME_COLORS

# ANSI / Truecolor tokens
C_CYAN = THEME_COLORS["primary"]       # #42E8D5 Luminous turquoise/cyan
C_TEAL = THEME_COLORS["secondary"]     # #14B8A6 Bluish green / teal
C_DTEAL = THEME_COLORS["teal"]         # #0D9488 Deep teal
C_ICE = THEME_COLORS["ice"]            # #7DD3FC Ice blue
C_GLOW = THEME_COLORS["glow"]          # #DDFBFF White-cyan glow
C_DIM = THEME_COLORS["dim"]            # #64748B Slate / muted
C_MINT = THEME_COLORS["success"]       # #34D399 Mint
C_AMBER = THEME_COLORS["warning"]      # #FBBF24 Amber
C_CORAL = THEME_COLORS["error"]        # #F87171 Coral


def _build_frame(lines: list[str]) -> Text:
    """Helper to convert markup lines to a Rich Text object."""
    return Text.from_markup("\n".join(lines))


def get_neural_core(frame: int = 0, state: str = "idle", ascii_fallback: bool = False) -> Text:
    """Render the SCOUT NEURAL CORE avatar for a specific frame and agent state."""
    if ascii_fallback:
        return _render_ascii_core(frame, state)

    state = state.lower()

    if state == "starting":
        return _render_starting(frame)
    elif state == "listening":
        return _render_listening(frame)
    elif state == "thinking":
        return _render_thinking(frame)
    elif state == "executing":
        return _render_executing(frame)
    elif state == "verifying":
        return _render_verifying(frame)
    elif state == "speaking":
        return _render_speaking(frame)
    elif state == "success":
        return _render_success(frame)
    elif state == "error":
        return _render_error(frame)
    else:
        # Default: idle state (slow breathing and orbital movement)
        return _render_idle(frame)


def _render_idle(frame: int) -> Text:
    """Idle: slow breathing glow and gentle orbital movement."""
    f = frame % 4
    
    # Orbiting satellite positions
    # Clockwise orbit on inner ring
    if f == 0:
        sat_top = f"[{C_ICE}]•[/{C_ICE}]─"
        sat_bot = f"─[{C_ICE}]•[/{C_ICE}]"
        nucleus = f"[{C_GLOW}]✦[/{C_GLOW}]"
        l_bus = f"[{C_CYAN}]──┼┄[/{C_CYAN}]"
        r_bus = f"[{C_CYAN}]┄┼──[/{C_CYAN}]"
        node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        v_pulse = f"[{C_DIM}]│[/{C_DIM}]"
    elif f == 1:
        sat_top = f"─[{C_ICE}]•[/{C_ICE}]"
        sat_bot = f"[{C_ICE}]•[/{C_ICE}]─"
        nucleus = f"[{C_CYAN}]✧[/{C_CYAN}]"
        # Energy moving in
        l_bus = f"[{C_CYAN}]─━┼┄[/{C_CYAN}]"
        r_bus = f"[{C_CYAN}]┄┼━─[/{C_CYAN}]"
        node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        v_pulse = f"[{C_DIM}]│[/{C_DIM}]"
    elif f == 2:
        sat_top = f"──[{C_ICE}]•[/{C_ICE}]"
        sat_bot = f"[{C_ICE}]•[/{C_ICE}]──"
        nucleus = f"[{C_GLOW}]◈[/{C_GLOW}]"
        l_bus = f"[{C_CYAN}]──┼━[/{C_CYAN}]"
        r_bus = f"[{C_CYAN}]━┼──[/{C_CYAN}]"
        node = f"[{C_ICE}]⬢[/{C_ICE}]"
        v_pulse = f"[{C_ICE}]┃[/{C_ICE}]"
    else:  # f == 3
        sat_top = f"[{C_ICE}]•[/{C_ICE}]──"
        sat_bot = f"──[{C_ICE}]•[/{C_ICE}]"
        nucleus = f"[{C_TEAL}]✦[/{C_TEAL}]"
        l_bus = f"[{C_CYAN}]──┼┄[/{C_CYAN}]"
        r_bus = f"[{C_CYAN}]┄┼──[/{C_CYAN}]"
        node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        v_pulse = f"[{C_DIM}]│[/{C_DIM}]"

    lines = [
        f"       [{C_DIM}]·[/{C_DIM}] {node} [{C_DIM}]·[/{C_DIM}]       ",
        f"   [{C_DIM}]╭───╵[/{C_DIM}] {v_pulse} [{C_DIM}]╵───╮[/{C_DIM}]   ",
        f" [{C_DIM}]╭─╯  ╭─[/{C_DIM}]{sat_top}[{C_DIM}]╮  ╰─╮[/{C_DIM}] ",
        f"{node}{l_bus}[{C_DTEAL}]╶┤[/{C_DTEAL}]  {nucleus}  [{C_DTEAL}]├╴[/{C_DTEAL}]{r_bus}{node}",
        f" [{C_DIM}]╰─╮  ╰─[/{C_DIM}]{sat_bot}[{C_DIM}]╯  ╭─╯[/{C_DIM}] ",
        f"   [{C_DIM}]╰───╷[/{C_DIM}] {v_pulse} [{C_DIM}]╷───╯[/{C_DIM}]   ",
        f"       [{C_DIM}]·[/{C_DIM}] {node} [{C_DIM}]·[/{C_DIM}]       ",
    ]
    return _build_frame(lines)


def _render_listening(frame: int) -> Text:
    """Listening: expanding concentric signal rings."""
    f = frame % 4
    if f == 0:
        mid_core = f"[{C_CYAN}]╶┤ [/{C_CYAN}][{C_GLOW}](✦)[/{C_GLOW}][{C_CYAN}] ├╴[/{C_CYAN}]"
        ring_glyph = f"[{C_DIM}]╭───•───╮[/{C_DIM}]"
        ring_bot = f"[{C_DIM}]╰───•───╯[/{C_DIM}]"
    elif f == 1:
        mid_core = f"[{C_CYAN}]╶┤[/{C_CYAN}][{C_ICE}]((✦))[/{C_ICE}][{C_CYAN}]├╴[/{C_CYAN}]"
        ring_glyph = f"[{C_CYAN}]╭──(•)──╮[/{C_CYAN}]"
        ring_bot = f"[{C_CYAN}]╰──(•)──╯[/{C_CYAN}]"
    elif f == 2:
        mid_core = f"[{C_CYAN}]╶┤[/{C_CYAN}][{C_GLOW}]⟨ ✦ ⟩[/{C_GLOW}][{C_CYAN}]├╴[/{C_CYAN}]"
        ring_glyph = f"[{C_GLOW}]╭──⟨•⟩──╮[/{C_GLOW}]"
        ring_bot = f"[{C_GLOW}]╰──⟨•⟩──╯[/{C_GLOW}]"
    else:
        mid_core = f"[{C_CYAN}]╶┤ [/{C_CYAN}][{C_ICE}]✦[/{C_ICE}][{C_CYAN}] ├╴[/{C_CYAN}]"
        ring_glyph = f"[{C_ICE}]╭─( · )─╮[/{C_ICE}]"
        ring_bot = f"[{C_ICE}]╰─( · )─╯[/{C_ICE}]"

    lines = [
        f"     [{C_CYAN}]· ( [/{C_CYAN}][{C_GLOW}]⬡[/{C_GLOW}][{C_CYAN}] ) ·[/{C_CYAN}]     ",
        f"   [{C_DIM}]╭───╵ │ ╵───╮[/{C_DIM}]   ",
        f" [{C_DIM}]╭─╯[/{C_DIM}]  {ring_glyph}  [{C_DIM}]╰─╮[/{C_DIM}] ",
        f"[{C_GLOW}]⬢[/{C_GLOW}][{C_CYAN}]──┼┄[/{C_CYAN}]{mid_core}[{C_CYAN}]┄┼──[/{C_CYAN}][{C_GLOW}]⬢[/{C_GLOW}]",
        f" [{C_DIM}]╰─╮[/{C_DIM}]  {ring_bot}  [{C_DIM}]╭─╯[/{C_DIM}] ",
        f"   [{C_DIM}]╰───╷ │ ╷───╯[/{C_DIM}]   ",
        f"     [{C_CYAN}]· ( [/{C_CYAN}][{C_GLOW}]⬡[/{C_GLOW}][{C_CYAN}] ) ·[/{C_CYAN}]     ",
    ]
    return _build_frame(lines)


def _render_thinking(frame: int) -> Text:
    """Thinking: faster internal pulses, circulating energy, spinning nucleus."""
    f = frame % 4
    spinners = ["✦", "✺", "◈", "◉"]
    nucleus = f"[{C_GLOW}]{spinners[f]}[/{C_GLOW}]"
    
    if f % 2 == 0:
        sp_inner = f"[{C_CYAN}]╭─◜ ◝─╮[/{C_CYAN}]"
        sp_bot = f"[{C_CYAN}]╰─◟ ◞─╯[/{C_CYAN}]"
        node = f"[{C_GLOW}]⬢[/{C_GLOW}]"
        wire = f"[{C_CYAN}]━─┼━[/{C_CYAN}]"
        wire_r = f"[{C_CYAN}]━┼─━[/{C_CYAN}]"
    else:
        sp_inner = f"[{C_ICE}]╭─◟ ◞─╮[/{C_ICE}]"
        sp_bot = f"[{C_ICE}]╰─◜ ◝─╯[/{C_ICE}]"
        node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        wire = f"[{C_CYAN}]─━┼┄[/{C_CYAN}]"
        wire_r = f"[{C_CYAN}]┄┼━─[/{C_CYAN}]"

    lines = [
        f"       [{C_ICE}]·[/{C_ICE}] {node} [{C_ICE}]·[/{C_ICE}]       ",
        f"   [{C_DIM}]╭───╵[/{C_DIM}][{C_CYAN}]┃[/{C_CYAN}][{C_DIM}]╵───╮[/{C_DIM}]   ",
        f" [{C_DIM}]╭─╯ [/{C_DIM}]{sp_inner}[{C_DIM}] ╰─╮[/{C_DIM}] ",
        f"{node}[{C_CYAN}]{wire}[/{C_CYAN}][{C_DTEAL}]╶┤[/{C_DTEAL}]  {nucleus}  [{C_DTEAL}]├╴[/{C_DTEAL}][{C_CYAN}]{wire_r}[/{C_CYAN}]{node}",
        f" [{C_DIM}]╰─╮ [/{C_DIM}]{sp_bot}[{C_DIM}] ╭─╯[/{C_DIM}] ",
        f"   [{C_DIM}]╰───╷[/{C_DIM}][{C_CYAN}]┃[/{C_CYAN}][{C_DIM}]╷───╯[/{C_DIM}]   ",
        f"       [{C_ICE}]·[/{C_ICE}] {node} [{C_ICE}]·[/{C_ICE}]       ",
    ]
    return _build_frame(lines)


def _render_executing(frame: int) -> Text:
    """Executing: energy travelling dynamically between nodes."""
    f = frame % 4
    
    if f == 0:
        # Left node spark
        l_node = f"[{C_GLOW}]⬢[/{C_GLOW}]"
        r_node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        bus_l = f"[{C_GLOW}]━─┼┄[/{C_GLOW}]"
        bus_r = f"[{C_DIM}]┄┼──[/{C_DIM}]"
        inner_sat = f"[{C_ICE}]◆──[/{C_ICE}]"
    elif f == 1:
        # Energy moving across junction
        l_node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        r_node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        bus_l = f"[{C_CYAN}]─━┼━[/{C_CYAN}]"
        bus_r = f"[{C_CYAN}]━┼──[/{C_CYAN}]"
        inner_sat = f"[{C_GLOW}]─◆─[/{C_GLOW}]"
    elif f == 2:
        # Energy energizing core
        l_node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        r_node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        bus_l = f"[{C_DIM}]──┼━[/{C_DIM}]"
        bus_r = f"[{C_CYAN}]━┼━─[/{C_CYAN}]"
        inner_sat = f"[{C_ICE}]──◆[/{C_ICE}]"
    else:  # f == 3
        # Right node spark
        l_node = f"[{C_TEAL}]⬡[/{C_TEAL}]"
        r_node = f"[{C_GLOW}]⬢[/{C_GLOW}]"
        bus_l = f"[{C_DIM}]──┼┄[/{C_DIM}]"
        bus_r = f"[{C_GLOW}]┄┼─━[/{C_GLOW}]"
        inner_sat = f"[{C_ICE}]─•─[/{C_ICE}]"

    nucleus = f"[{C_MINT}]✦[/{C_MINT}]" if f % 2 == 1 else f"[{C_GLOW}]◈[/{C_GLOW}]"

    lines = [
        f"       [{C_DIM}]·[/{C_DIM}] [{C_MINT}]⬢[/{C_MINT}] [{C_DIM}]·[/{C_DIM}]       ",
        f"   [{C_DIM}]╭───╵[/{C_DIM}][{C_CYAN}]┃[/{C_CYAN}][{C_DIM}]╵───╮[/{C_DIM}]   ",
        f" [{C_DIM}]╭─╯  ╭─[/{C_DIM}]{inner_sat}[{C_DIM}]─╮  ╰─╮[/{C_DIM}] ",
        f"{l_node}{bus_l}[{C_DTEAL}]╶┤[/{C_DTEAL}]  {nucleus}  [{C_DTEAL}]├╴[/{C_DTEAL}]{bus_r}{r_node}",
        f" [{C_DIM}]╰─╮  ╰─[/{C_DIM}]{inner_sat}[{C_DIM}]─╯  ╭─╯[/{C_DIM}] ",
        f"   [{C_DIM}]╰───╷[/{C_DIM}][{C_CYAN}]┃[/{C_CYAN}][{C_DIM}]╷───╯[/{C_DIM}]   ",
        f"       [{C_DIM}]·[/{C_DIM}] [{C_MINT}]⬢[/{C_MINT}] [{C_DIM}]·[/{C_DIM}]       ",
    ]
    return _build_frame(lines)


def _render_verifying(frame: int) -> Text:
    """Verifying: scanning pulse moving vertically through the core."""
    f = frame % 5
    
    # 21 chars wide
    l0 = f"[{C_CYAN}]   ─── · ⬡ · ───   [/{C_CYAN}]" if f == 0 else f"[{C_DIM}]       · ⬡ ·       [/{C_DIM}]"
    l1 = f"[{C_GLOW}]   ╭═══╵ │ ╵═══╮   [/{C_GLOW}]" if f == 1 else f"[{C_DIM}]   ╭───╵ │ ╵───╮   [/{C_DIM}]"
    l2 = f"[{C_ICE}]  ╭═╯  ╭═•═╮  ╰═╮  [/{C_ICE}]" if f == 2 else f"[{C_DIM}]  ╭─╯  ╭─•─╮  ╰─╮  [/{C_DIM}]"
    
    if f == 3:
        l3 = f"[{C_GLOW}]⬢══╬═╶╡  ✦  ╞╴═╬══⬢[/{C_GLOW}]"
    else:
        l3 = f"[{C_TEAL}]⬡──┼┄[/{C_TEAL}][{C_DTEAL}]╶┤[/{C_DTEAL}]  [{C_CYAN}]✦[/{C_CYAN}]  [{C_DTEAL}]├╴[/{C_DTEAL}][{C_TEAL}]┄┼──⬡[/{C_TEAL}]"
        
    l4 = f"[{C_ICE}]  ╰═╮  ╰═•═╯  ╭═╯  [/{C_ICE}]" if f == 4 else f"[{C_DIM}]  ╰─╮  ╰─•─╯  ╭─╯  [/{C_DIM}]"
    l5 = f"[{C_GLOW}]   ╰═══╷ │ ╷═══╯   [/{C_GLOW}]" if f == 0 else f"[{C_DIM}]   ╰───╷ │ ╷───╯   [/{C_DIM}]"
    l6 = f"[{C_CYAN}]   ─── · ⬡ · ───   [/{C_CYAN}]" if f == 1 else f"[{C_DIM}]       · ⬡ ·       [/{C_DIM}]"

    lines = [l0, l1, l2, l3, l4, l5, l6]
    return _build_frame(lines)


def _render_speaking(frame: int) -> Text:
    """Speaking: subtle rhythmic audio/synapse vibration."""
    f = frame % 4
    bars = ["╻✦╻", "┃✦┃", "█✦█", "┃✦┃"]
    meter = bars[f]
    
    node = f"[{C_CYAN}]⬡[/{C_CYAN}]"
    lines = [
        f"       [{C_DIM}]·[/{C_DIM}] {node} [{C_DIM}]·[/{C_DIM}]       ",
        f"   [{C_DIM}]╭───╵ │ ╵───╮[/{C_DIM}]   ",
        f" [{C_DIM}]╭─╯  ╭─[/{C_DIM}][{C_TEAL}]~[/{C_TEAL}][{C_DIM}]─╮  ╰─╮[/{C_DIM}] ",
        f"{node}[{C_CYAN}]──┼┄[/{C_CYAN}][{C_TEAL}]╶┤[/{C_TEAL}] [{C_GLOW}]{meter}[/{C_GLOW}] [{C_TEAL}]├╴[/{C_TEAL}][{C_CYAN}]┄┼──[/{C_CYAN}]{node}",
        f" [{C_DIM}]╰─╮  ╰─[/{C_DIM}][{C_TEAL}]~[/{C_TEAL}][{C_DIM}]─╯  ╭─╯[/{C_DIM}] ",
        f"   [{C_DIM}]╰───╷ │ ╷───╯[/{C_DIM}]   ",
        f"       [{C_DIM}]·[/{C_DIM}] {node} [{C_DIM}]·[/{C_DIM}]       ",
    ]
    return _build_frame(lines)


def _render_success(frame: int) -> Text:
    """Success: radiant mint/cyan burst with locked solid nodes."""
    node = f"[{C_MINT}]⬢[/{C_MINT}]"
    lines = [
        f"       [{C_MINT}]· ⬢ ·[/{C_MINT}]       ",
        f"   [{C_TEAL}]╭───╵ │ ╵───╮[/{C_TEAL}]   ",
        f" [{C_TEAL}]╭─╯  ╭─[/{C_TEAL}][{C_MINT}]✦[/{C_MINT}][{C_TEAL}]─╮  ╰─╮[/{C_TEAL}] ",
        f"{node}[{C_MINT}]━━━[/{C_MINT}][{C_CYAN}]╶┤[/{C_CYAN}] [{C_GLOW}]✦ ✦ ✦[/{C_GLOW}] [{C_CYAN}]├╴[/{C_CYAN}][{C_MINT}]━━━[/{C_MINT}]{node}",
        f" [{C_TEAL}]╰─╮  ╰─[/{C_TEAL}][{C_MINT}]✦[/{C_MINT}][{C_TEAL}]─╯  ╭─╯[/{C_TEAL}] ",
        f"   [{C_TEAL}]╰───╷ │ ╷───╯[/{C_TEAL}]   ",
        f"       [{C_MINT}]· ⬢ ·[/{C_MINT}]       ",
    ]
    return _build_frame(lines)


def _render_error(frame: int) -> Text:
    """Error: restrained amber/coral warning pulse."""
    node = f"[{C_AMBER}]▲[/{C_AMBER}]"
    nucleus = f"[{C_CORAL}]✖[/{C_CORAL}]"
    lines = [
        f"       [{C_AMBER}]· ▲ ·[/{C_AMBER}]       ",
        f"   [{C_DIM}]╭───╵ ┆ ╵───╮[/{C_DIM}]   ",
        f" [{C_DIM}]╭─╯  ╭─!─╮  ╰─╮[/{C_DIM}] ",
        f"{node}[{C_CORAL}]──┼┄[/{C_CORAL}][{C_CORAL}]╶┤[/{C_CORAL}]  {nucleus}  [{C_CORAL}]├╴[/{C_CORAL}][{C_CORAL}]┄┼──[/{C_CORAL}]{node}",
        f" [{C_DIM}]╰─╮  ╰─!─╯  ╭─╯[/{C_DIM}] ",
        f"   [{C_DIM}]╰───╷ ┆ ╷───╯[/{C_DIM}]   ",
        f"       [{C_AMBER}]· ▲ ·[/{C_AMBER}]       ",
    ]
    return _build_frame(lines)


def _render_starting(frame: int) -> Text:
    """Starting: progressive spinup sequence."""
    if frame <= 0:
        lines = [
            f"       [{C_DIM}]·   ·[/{C_DIM}]       ",
            f"                       ",
            f"            [{C_DIM}]·[/{C_DIM}]        ",
            f"        [{C_DIM}]·[/{C_DIM}] [{C_CYAN}]✦[/{C_CYAN}] [{C_DIM}]·[/{C_DIM}]        ",
            f"            [{C_DIM}]·[/{C_DIM}]        ",
            f"                       ",
            f"       [{C_DIM}]·   ·[/{C_DIM}]       ",
        ]
    elif frame == 1:
        lines = [
            f"       [{C_DIM}]·[/{C_DIM}] [{C_TEAL}]⬡[/{C_TEAL}] [{C_DIM}]·[/{C_DIM}]       ",
            f"     [{C_DIM}].       .[/{C_DIM}]     ",
            f"   [{C_DIM}].    ╭───╮    .[/{C_DIM}]   ",
            f" [{C_TEAL}]⬡[/{C_TEAL}]      [{C_DIM}]│[/{C_DIM}] [{C_CYAN}]✦[/{C_CYAN}] [{C_DIM}]│[/{C_DIM}]      [{C_TEAL}]⬡[/{C_TEAL}] ",
            f"   [{C_DIM}].    ╰───╯    .[/{C_DIM}]   ",
            f"     [{C_DIM}].       .[/{C_DIM}]     ",
            f"       [{C_DIM}]·[/{C_DIM}] [{C_TEAL}]⬡[/{C_TEAL}] [{C_DIM}]·[/{C_DIM}]       ",
        ]
    else:
        return _render_idle(frame)
    return _build_frame(lines)


def _render_ascii_core(frame: int, state: str) -> Text:
    """Graceful ASCII fallback when Unicode characters are unsupported."""
    f = frame % 3
    nucleus = "*" if f == 0 else "o"
    lines = [
        "       . - o - .       ",
        "    .-'    |    '-.    ",
        "  o-┤   .-'-'.   ├-o  ",
        f" ---+--(   {nucleus}   )--+--- ",
        "  o-┤   '-.-.'   ├-o  ",
        "    '-.    |    .-'    ",
        "       ' - o - '       ",
    ]
    return Text("\n".join(lines), style=f"bold {C_CYAN}")


def get_compact_core(state: str = "idle") -> Text:
    """A compact single-line neural badge for inline status bars or prompts."""
    state = state.lower()
    if state == "executing":
        return Text.from_markup(f"[{C_CYAN}]⬢[/{C_CYAN}][{C_ICE}]━[/{C_ICE}][{C_GLOW}]✦[/{C_GLOW}][{C_ICE}]━[/{C_ICE}][{C_CYAN}]⬢[/{C_CYAN}]")
    elif state == "verifying":
        return Text.from_markup(f"[{C_ICE}]⬡[/{C_ICE}][{C_GLOW}]═[/{C_GLOW}][{C_CYAN}]✦[/{C_CYAN}][{C_GLOW}]═[/{C_GLOW}][{C_ICE}]⬡[/{C_ICE}]")
    elif state == "listening":
        return Text.from_markup(f"[{C_CYAN}]⬡[/{C_CYAN}][{C_ICE}]((✦))[/{C_ICE}][{C_CYAN}]⬡[/{C_CYAN}]")
    elif state == "speaking":
        return Text.from_markup(f"[{C_TEAL}]⬡[/{C_TEAL}][{C_GLOW}]┃✦┃[/{C_GLOW}][{C_TEAL}]⬡[/{C_TEAL}]")
    elif state == "success":
        return Text.from_markup(f"[{C_MINT}]⬢[/{C_MINT}][{C_GLOW}]✦✦✦[/{C_GLOW}][{C_MINT}]⬢[/{C_MINT}]")
    elif state == "error":
        return Text.from_markup(f"[{C_AMBER}]▲[/{C_AMBER}][{C_CORAL}]─✖─[/{C_CORAL}][{C_AMBER}]▲[/{C_AMBER}]")
    else:
        return Text.from_markup(f"[{C_TEAL}]⬡[/{C_TEAL}][{C_DIM}]┄[/{C_DIM}][{C_CYAN}]✦[/{C_CYAN}][{C_DIM}]┄[/{C_DIM}][{C_TEAL}]⬡[/{C_TEAL}]")
