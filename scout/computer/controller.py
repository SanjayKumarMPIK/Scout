"""Unified computer control subsystem."""

from __future__ import annotations

import time
from typing import Any, Dict

import pyautogui
from scout.ai.window_manager import activate_window, get_active_window, minimize_window, maximize_window
from scout.vision.capture import take_screenshot

# Safety setup
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1

class ComputerController:
    """Provides a safe, unified interface to control the computer."""

    def __init__(self):
        self.enabled = True
        self.screen_width, self.screen_height = pyautogui.size()
        self.last_screenshot_path = ""
        self.last_screenshot_time = 0.0

    def get_state(self) -> dict[str, Any]:
        """Get the current computer state."""
        active = get_active_window()
        mx, my = pyautogui.position()
        return {
            "enabled": self.enabled,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "active_window": active["title"] if active else "Unknown",
            "mouse_position": {"x": mx, "y": my},
            "last_screenshot_time": self.last_screenshot_time
        }

    def _validate_coords(self, x: int, y: int) -> bool:
        """Ensure coordinates are within screen bounds."""
        return 0 <= x < self.screen_width and 0 <= y < self.screen_height

    def _report(self, success: bool, message: str) -> dict[str, Any]:
        """Standardize the return format."""
        active = get_active_window()
        return {
            "success": success,
            "message": message,
            "active_window": active["title"] if active else "Unknown"
        }

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute a structured computer action."""
        if not self.enabled:
            return self._report(False, "Computer control is currently disabled.")

        act = action.get("action")
        if not act:
            return self._report(False, "No action specified.")

        focus_dependent_actions = {"click", "double_click", "move", "drag", "type", "key", "hotkey", "scroll"}
        if act in focus_dependent_actions:
            from scout.ai.window_manager import get_target_window_manager
            focus_res = get_target_window_manager().ensure_target_focus()
            if not focus_res.get("success"):
                return focus_res

        try:
            if act == "screenshot":
                return self._screenshot()
            elif act == "click":
                return self._click(action)
            elif act == "double_click":
                return self._double_click(action)
            elif act == "move":
                return self._move(action)
            elif act == "drag":
                return self._drag(action)
            elif act == "type":
                return self._type(action)
            elif act == "key":
                return self._key(action)
            elif act == "hotkey":
                return self._hotkey(action)
            elif act == "scroll":
                return self._scroll(action)
            elif act == "activate_window":
                return self._activate_window(action)
            elif act == "minimize_window":
                return self._minimize_window(action)
            elif act == "maximize_window":
                return self._maximize_window(action)
            elif act == "wait":
                return self._wait(action)
            else:
                return self._report(False, f"Unknown computer action: {act}")

        except pyautogui.FailSafeException:
            return self._report(False, "Action aborted by user via mouse failsafe (moved to corner).")
        except KeyboardInterrupt:
            return self._report(False, "Action interrupted by user.")
        except Exception as e:
            return self._report(False, f"Error executing {act}: {str(e)}")

    def _screenshot(self) -> dict[str, Any]:
        cap = take_screenshot()
        if cap.get("success"):
            self.last_screenshot_path = cap["path"]
            self.last_screenshot_time = cap["timestamp"]
            return self._report(True, "Screenshot captured.")
        return self._report(False, f"Screenshot failed: {cap.get('error')}")

    def _click(self, action: dict[str, Any]) -> dict[str, Any]:
        x = action.get("x")
        y = action.get("y")
        button = action.get("button", "left")
        
        if x is not None and y is not None:
            if not self._validate_coords(x, y):
                return self._report(False, f"Coordinates ({x}, {y}) out of bounds ({self.screen_width}x{self.screen_height})")
            pyautogui.click(x=x, y=y, button=button)
            return self._report(True, f"Clicked {button} at ({x}, {y})")
        else:
            pyautogui.click(button=button)
            return self._report(True, f"Clicked {button} at current position")

    def _double_click(self, action: dict[str, Any]) -> dict[str, Any]:
        x = action.get("x")
        y = action.get("y")
        button = action.get("button", "left")
        
        if x is not None and y is not None:
            if not self._validate_coords(x, y):
                return self._report(False, f"Coordinates ({x}, {y}) out of bounds")
            pyautogui.doubleClick(x=x, y=y, button=button)
            return self._report(True, f"Double-clicked {button} at ({x}, {y})")
        else:
            pyautogui.doubleClick(button=button)
            return self._report(True, f"Double-clicked {button} at current position")

    def _move(self, action: dict[str, Any]) -> dict[str, Any]:
        x = action.get("x")
        y = action.get("y")
        if x is None or y is None:
            return self._report(False, "Missing x or y for move")
            
        if not self._validate_coords(x, y):
            return self._report(False, f"Coordinates ({x}, {y}) out of bounds")
            
        pyautogui.moveTo(x, y)
        return self._report(True, f"Moved mouse to ({x}, {y})")

    def _drag(self, action: dict[str, Any]) -> dict[str, Any]:
        fx, fy = action.get("from_x"), action.get("from_y")
        tx, ty = action.get("to_x"), action.get("to_y")
        button = action.get("button", "left")
        
        if None in (fx, fy, tx, ty):
            return self._report(False, "Missing from_x, from_y, to_x, or to_y for drag")
            
        if not (self._validate_coords(fx, fy) and self._validate_coords(tx, ty)):
            return self._report(False, "Drag coordinates out of bounds")
            
        pyautogui.moveTo(fx, fy)
        pyautogui.dragTo(tx, ty, button=button, duration=0.5)
        return self._report(True, f"Dragged from ({fx}, {fy}) to ({tx}, {ty})")

    def _type(self, action: dict[str, Any]) -> dict[str, Any]:
        text = action.get("text")
        if not text:
            return self._report(False, "Missing text to type")
        pyautogui.write(text, interval=0.01)
        return self._report(True, f"Typed text: '{text}'")

    def _key(self, action: dict[str, Any]) -> dict[str, Any]:
        key = action.get("key")
        if not key:
            return self._report(False, "Missing key to press")
        pyautogui.press(key)
        return self._report(True, f"Pressed key: {key}")

    def _hotkey(self, action: dict[str, Any]) -> dict[str, Any]:
        keys = action.get("keys")
        if not keys or not isinstance(keys, list):
            return self._report(False, "Missing or invalid keys array for hotkey")
            
        # Ensure we always release modifiers safely
        try:
            for k in keys:
                pyautogui.keyDown(k)
        finally:
            for k in reversed(keys):
                pyautogui.keyUp(k)
                
        return self._report(True, f"Executed hotkey: {'+'.join(keys)}")

    def _scroll(self, action: dict[str, Any]) -> dict[str, Any]:
        amount = action.get("amount")
        if amount is None:
            return self._report(False, "Missing scroll amount")
        # In pyautogui, positive is up, negative is down usually (OS dependent)
        pyautogui.scroll(amount)
        return self._report(True, f"Scrolled {amount}")

    def _activate_window(self, action: dict[str, Any]) -> dict[str, Any]:
        title = action.get("title")
        if not title:
            return self._report(False, "Missing window title")
        if activate_window(title):
            time.sleep(0.5) # Allow UI to focus
            return self._report(True, f"Activated window '{title}'")
        return self._report(False, f"Could not find or activate window '{title}'")

    def _minimize_window(self, action: dict[str, Any]) -> dict[str, Any]:
        title = action.get("title")
        if not title:
            return self._report(False, "Missing window title")
        if minimize_window(title):
            return self._report(True, f"Minimized window '{title}'")
        return self._report(False, f"Could not find or minimize window '{title}'")
        
    def _maximize_window(self, action: dict[str, Any]) -> dict[str, Any]:
        title = action.get("title")
        if not title:
            return self._report(False, "Missing window title")
        if maximize_window(title):
            return self._report(True, f"Maximized window '{title}'")
        return self._report(False, f"Could not find or maximize window '{title}'")

    def _wait(self, action: dict[str, Any]) -> dict[str, Any]:
        sec = action.get("seconds", 1.0)
        time.sleep(sec)
        return self._report(True, f"Waited {sec} seconds")


_controller = None

def get_computer_controller() -> ComputerController:
    global _controller
    if _controller is None:
        _controller = ComputerController()
    return _controller
