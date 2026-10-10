"""Scout Neural Core — Terminal-Compatible Animated Avatar."""

from __future__ import annotations
import sys
from rich.text import Text
from scout.ui.theme import THEME_COLORS

C_CYAN = THEME_COLORS["primary"]
C_TEAL = THEME_COLORS["secondary"]
C_DTEAL = THEME_COLORS["teal"]
C_ICE = THEME_COLORS["ice"]
C_GLOW = THEME_COLORS["glow"]
C_DIM = THEME_COLORS["dim"]
C_MINT = THEME_COLORS["success"]
C_AMBER = THEME_COLORS["warning"]
C_CORAL = THEME_COLORS["error"]
C_MAGENTA = THEME_COLORS.get("magenta", "#FF007F")
C_PURPLE = THEME_COLORS.get("purple", "#A855F7")

def _build_frame(lines: list[str]) -> Text:
    return Text.from_markup("\n".join(lines))

def get_neural_core(frame: int = 0, state: str = "idle", ascii_fallback: bool = False) -> Text:
    if ascii_fallback:
        return _render_ascii_core(frame, state)
    state = state.lower()
    if state == "starting": return _render_starting(frame)
    elif state == "listening": return _render_listening(frame)
    elif state == "thinking": return _render_thinking(frame)
    elif state == "executing": return _render_executing(frame)
    elif state == "verifying": return _render_verifying(frame)
    elif state == "speaking": return _render_speaking(frame)
    elif state == "success": return _render_success(frame)
    elif state == "error": return _render_error(frame)
    return _render_idle(frame)


def _build_robot(frame: int, eyes: str, mouth: str, core_symbol: str, arms_type: str, antenna_color: str, eye_color: str, mouth_color: str, outline_color: str = C_CYAN) -> Text:
    """Builds an 11-line fun, vibey robot avatar with a small body. Centered in a 39-char wide block."""
    if arms_type == "up":
        arms_l, arms_r = "╰╮", "╭╯"
    elif arms_type == "down":
        arms_l, arms_r = "╭╯", "╰╮"
    else:
        arms_l, arms_r = "─┤", "├─"
        
    lines = [
        f"                                       ",
        f"              [{antenna_color}]    ▤▤▤    [/{antenna_color}]              ",
        f"              [{antenna_color}]  ╭──┴──╮  [/{antenna_color}]              ",
        f"              [{outline_color}]╭┤[/{outline_color}] [{eye_color}]{eyes}[/{eye_color}] [{outline_color}]├╮[/{outline_color}]              ",
        f"              [{outline_color}]││[/{outline_color}] [{mouth_color}]{mouth}[/{mouth_color}] [{outline_color}]││[/{outline_color}]              ",
        f"              [{outline_color}]╰╰───┬───╯╯[/{outline_color}]              ",
        f"              [{outline_color}] ╭───┴───╮ [/{outline_color}]              ",
        f"              [{outline_color}]{arms_l}[/{outline_color}] [{mouth_color}]{core_symbol}[/{mouth_color}] [{outline_color}]{arms_r}[/{outline_color}]              ",
        f"              [{outline_color}] ╰─┬───┬─╯ [/{outline_color}]              ",
        f"              [{outline_color}]  _│   │_  [/{outline_color}]              ",
        f"                                       ",
    ]
    return _build_frame(lines)

def _render_idle(frame: int) -> Text:
    eyes = "◕   ◕" if frame % 60 != 0 else ">   <" # cute blink
    return _build_robot(frame, eyes, "  ω  ", "  ♥  ", "side", C_DIM, C_TEAL, C_CYAN)

def _render_listening(frame: int) -> Text:
    eyes = "✧   ✧" if frame % 10 < 5 else "◕   ◕"
    mouths = [" ▃▂  ", "  ▂▃ ", " ▃▅  ", "  ▅▃ "]
    m = mouths[frame % 4]
    sym = "  ♪  " if frame % 4 < 2 else "  ♫  "
    return _build_robot(frame, eyes, f"{m}", sym, "up", C_CYAN, C_GLOW, C_CYAN)

def _render_thinking(frame: int) -> Text:
    eyes = "◉   ◉" if frame % 4 < 2 else "○   ○"
    sym = "  ?  " if frame % 4 < 2 else "  ¿  "
    return _build_robot(frame, eyes, "  ~  ", sym, "down", C_MAGENTA, C_PURPLE, C_DIM, C_PURPLE)

def _render_executing(frame: int) -> Text:
    eyes = "⬢   ⬢" if frame % 2 == 0 else "⬡   ⬡"
    mouth = " ━━━ " if frame % 2 == 0 else " ─── "
    sym = "  ⚙  " if frame % 2 == 0 else "  ⛭  "
    return _build_robot(frame, eyes, f"{mouth}", sym, "side", C_ICE, C_ICE, C_ICE, C_CYAN)

def _render_verifying(frame: int) -> Text:
    eyes = "◎   ◎"
    mouth = "  ▤  " if frame % 2 == 0 else "  ▥  "
    sym = "  O  " if frame % 2 == 0 else "  o  "
    return _build_robot(frame, eyes, mouth, sym, "side", C_GLOW, C_CYAN, C_GLOW)

def _render_speaking(frame: int) -> Text:
    mouths = ["  ▽  ", "  ○  ", "  o  ", "  ▽  "]
    m = mouths[frame % 4]
    return _build_robot(frame, "◕   ◕", f"{m}", "  ♥  ", "up", C_TEAL, C_CYAN, C_TEAL)

def _render_success(frame: int) -> Text:
    return _build_robot(frame, "^   ^", "  U  ", "  ★  ", "up", C_MINT, C_MINT, C_MINT, C_MINT)

def _render_error(frame: int) -> Text:
    return _build_robot(frame, "x   x", "  △  ", "  !  ", "down", C_CORAL, C_CORAL, C_AMBER, C_CORAL)

def _render_starting(frame: int) -> Text:
    if frame <= 0:
        return _build_robot(frame, "     ", "     ", "     ", "side", C_DIM, C_DIM, C_DIM, C_DIM)
    elif frame == 1:
        return _build_robot(frame, "─   ─", "     ", "  -  ", "side", C_DIM, C_DIM, C_DIM, C_DIM)
    else:
        return _render_idle(frame)


def _render_ascii_core(frame: int, state: str) -> Text:
    """Graceful ASCII fallback when Unicode characters are unsupported."""
    lines = [
        "                                       ",
        "               ###               ",
        "             .--|--.             ",
        "           -| o   o |-           ",
        "            |   w   |            ",
        "            '---|---'            ",
        "             .---.             ",
        "           --| * |--           ",
        "             '-|-|-'             ",
        "              _I I_              ",
        "                                       ",
    ]
    return Text("\n".join(lines), style=f"bold {C_CYAN}")

def get_compact_core(state: str = "idle") -> Text:
    """A compact single-line neural badge for inline status bars or prompts."""
    state = state.lower()
    if state == "executing":
        return Text.from_markup(f"[{C_ICE}][>_>][/{C_ICE}]")
    elif state == "verifying":
        return Text.from_markup(f"[{C_GLOW}][O_O][/{C_GLOW}]")
    elif state == "listening":
        return Text.from_markup(f"[{C_CYAN}][~_~][/{C_CYAN}]")
    elif state == "speaking":
        return Text.from_markup(f"[{C_TEAL}][o_o][/{C_TEAL}]")
    elif state == "thinking":
        return Text.from_markup(f"[{C_PURPLE}][-_-][/{C_PURPLE}]")
    elif state == "success":
        return Text.from_markup(f"[{C_MINT}][^_^][/{C_MINT}]")
    elif state == "error":
        return Text.from_markup(f"[{C_CORAL}][x_x][/{C_CORAL}]")
    else:
        return Text.from_markup(f"[{C_DIM}][•_•][/{C_DIM}]")
