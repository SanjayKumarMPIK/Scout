"""Screenshot capture utility for Scout."""

from __future__ import annotations

import time
from pathlib import Path

from scout.config import APP_DIR


CAPTURE_DIR = APP_DIR / "captures"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

# Max screenshots to keep (auto-cleanup)
MAX_CAPTURES = 20


def _cleanup_old_captures() -> None:
    """Remove oldest captures if we exceed MAX_CAPTURES."""
    files = sorted(CAPTURE_DIR.glob("*.png"), key=lambda f: f.stat().st_mtime)
    while len(files) > MAX_CAPTURES:
        files[0].unlink(missing_ok=True)
        files.pop(0)


def take_screenshot() -> dict:
    """Capture the screen and return metadata.
    
    Returns dict with:
        success: bool
        path: str (absolute path to screenshot)
        active_window: str
        timestamp: float
    """
    try:
        import pyautogui
        from scout.ai.window_manager import get_active_window

        timestamp = time.time()
        filename = f"capture_{int(timestamp)}.png"
        filepath = CAPTURE_DIR / filename

        img = pyautogui.screenshot()
        img.save(str(filepath))

        active = get_active_window()
        active_title = active["title"] if active else "Unknown"

        _cleanup_old_captures()

        return {
            "success": True,
            "path": str(filepath),
            "active_window": active_title,
            "timestamp": timestamp,
        }
    except Exception as e:
        return {
            "success": False,
            "path": "",
            "active_window": "",
            "timestamp": 0,
            "error": str(e),
        }
