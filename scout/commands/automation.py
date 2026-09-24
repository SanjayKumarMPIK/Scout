"""automation commands – keyboard/mouse automation and screenshots."""

from __future__ import annotations

import datetime

import pyautogui
from rich.console import Console

from scout.config import SCREENSHOT_DIR
from scout.core.registry import registry

console = Console()

# Disable PyAutoGUI's built-in pause between calls for snappier feel.
pyautogui.PAUSE = 0.05


# ── type command ───────────────────────────────────────────────────────

def _type_cmd(args: list[str]) -> None:
    """Type text using the keyboard."""
    if not args:
        console.print("[red]Usage:[/] type <text>")
        return

    text = " ".join(args)
    pyautogui.typewrite(text, interval=0.02)
    console.print(f"[green][+][/] Text entered ({len(text)} chars)")


registry.register(
    name="type",
    handler=_type_cmd,
    usage="type <text>",
    description="Type text via the keyboard.",
    group="Automation",
)


# ── press command ──────────────────────────────────────────────────────

# Map common friendly names to PyAutoGUI key names.
_KEY_ALIASES: dict[str, str] = {
    "enter":     "enter",
    "return":    "enter",
    "tab":       "tab",
    "escape":    "escape",
    "esc":       "escape",
    "space":     "space",
    "backspace": "backspace",
    "delete":    "delete",
    "up":        "up",
    "down":      "down",
    "left":      "left",
    "right":     "right",
    "home":      "home",
    "end":       "end",
    "pageup":    "pageup",
    "pagedown":  "pagedown",
    "ctrl":      "ctrl",
    "alt":       "alt",
    "shift":     "shift",
    "win":       "win",
    "f1":  "f1",  "f2":  "f2",  "f3":  "f3",  "f4":  "f4",
    "f5":  "f5",  "f6":  "f6",  "f7":  "f7",  "f8":  "f8",
    "f9":  "f9",  "f10": "f10", "f11": "f11", "f12": "f12",
}


def _press_cmd(args: list[str]) -> None:
    """Press a key or key combination (e.g. `press ctrl+c`)."""
    if not args:
        console.print("[red]Usage:[/] press <key> (e.g. enter, ctrl+c)")
        return

    raw = args[0].lower()
    keys = [_KEY_ALIASES.get(k, k) for k in raw.split("+")]

    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)

    console.print(f"[green][+][/] Pressed {raw}")


registry.register(
    name="press",
    handler=_press_cmd,
    usage="press <key|combo>",
    description="Press a key or combination (e.g. enter, ctrl+c, alt+tab).",
    group="Automation",
)


# ── screenshot command ─────────────────────────────────────────────────

def _screenshot_cmd(args: list[str]) -> None:
    """Take a screenshot and save it to the screenshots directory."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"

    img = pyautogui.screenshot()
    img.save(str(filename))
    console.print(f"[green][+][/] Screenshot saved -> {filename}")


registry.register(
    name="screenshot",
    handler=_screenshot_cmd,
    usage="screenshot",
    description="Take a screenshot and save it.",
    aliases=["ss"],
    group="Automation",
)
