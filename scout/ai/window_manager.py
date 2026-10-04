"""Window management capabilities using pygetwindow."""

import time
import subprocess
from typing import Optional, Dict, Any, List

try:
    import pygetwindow as gw
except ImportError:
    gw = None

class TargetWindowManager:
    def __init__(self):
        self.target_hwnd: Optional[int] = None
        self.target_title: Optional[str] = None

    def set_target(self, hwnd: int, title: str) -> None:
        self.target_hwnd = hwnd
        self.target_title = title
        import logging
        logging.info(f"[FOCUS] Target set: {title} (HWND={hwnd})")

    def get_target(self) -> tuple[Optional[int], Optional[str]]:
        return self.target_hwnd, self.target_title

    def ensure_target_focus(self) -> Dict[str, Any]:
        """Ensure the target window is foreground, recovering if necessary."""
        import ctypes
        import time
        from rich.console import Console
        console = Console()
        
        if not self.target_hwnd:
            return {"success": True, "message": "No target window set."}
            
        user32 = ctypes.windll.user32
        
        # Check if HWND is still valid
        if not user32.IsWindow(self.target_hwnd):
            # Target window no longer valid, try to recover by title
            if not self.target_title:
                return {"success": False, "error": "Target window lost and no title to recover."}
            console.print(f"[dim][FOCUS] Target window invalid, searching for '{self.target_title}'...[/dim]")
            win = find_window(self.target_title)
            if not win:
                return {"success": False, "error": f"Target window lost and could not be found by title '{self.target_title}'"}
            self.target_hwnd = win["handle"]
            self.target_title = win["title"]
            console.print(f"[dim][FOCUS] Target recovered: {self.target_title} (HWND={self.target_hwnd})[/dim]")
            
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd == self.target_hwnd:
            return {"success": True, "message": "Target is already foreground."}
            
        console.print(f"[dim][FOCUS] Restoring target focus: {self.target_title}[/dim]")
        
        for attempt in range(3):
            # Try to bring to foreground
            # Use ALT key trick to bypass foreground lock cleanly without messing up thread queues/focus
            user32.keybd_event(0x12, 0, 0, 0) # ALT down
            user32.keybd_event(0x12, 0, 2, 0) # ALT up
            
            if user32.IsIconic(self.target_hwnd):
                user32.ShowWindow(self.target_hwnd, 9) # SW_RESTORE
            else:
                user32.SetForegroundWindow(self.target_hwnd)
                
            time.sleep(0.5)
            
            new_fg = user32.GetForegroundWindow()
            if new_fg == self.target_hwnd:
                console.print(f"[dim][FOCUS] Verified foreground: {self.target_title}[/dim]")
                return {"success": True, "message": "Target focus restored."}
                
            # If new_fg is 0, we might be headless. But let's try gw.Window().activate() as a fallback
            try:
                if gw:
                    win_obj = gw.Window(self.target_hwnd)
                    win_obj.activate()
                    time.sleep(0.5)
                    if user32.GetForegroundWindow() == self.target_hwnd:
                        console.print(f"[dim][FOCUS] Verified foreground via fallback: {self.target_title}[/dim]")
                        return {"success": True, "message": "Target focus restored via fallback."}
            except Exception:
                pass
                
        # If we exhausted attempts and new_fg is 0, we might be headless where SetForegroundWindow fails but input works
        if user32.GetForegroundWindow() == 0:
            console.print(f"[dim][FOCUS] Warning: Foreground is 0 (headless). Assuming success for {self.target_title}.[/dim]")
            return {"success": True, "message": "Headless mode detected, assuming target focus."}
            
        return {"success": False, "error": "Target window could not be focused", "action_blocked": True}

_target_manager = TargetWindowManager()

def get_target_window_manager() -> TargetWindowManager:
    return _target_manager


def get_window_info(win) -> Dict[str, Any]:
    """Extract standard information from a pygetwindow Window object."""
    if not win:
        return {}
    return {
        "title": win.title,
        "handle": win._hWnd,
        "active": win.isActive,
        "visible": win.visible,
    }


def list_windows() -> List[Dict[str, Any]]:
    """Return a list of all visible windows."""
    if not gw:
        return []
    windows = []
    for win in gw.getAllWindows():
        if win.visible and win.title.strip():
            windows.append(get_window_info(win))
    return windows


def get_active_window() -> Optional[Dict[str, Any]]:
    """Return the currently active/focused window."""
    if not gw:
        return None
    win = gw.getActiveWindow()
    if win and win.title.strip():
        return get_window_info(win)
    return None


def find_window(title_or_app: str) -> Optional[Dict[str, Any]]:
    """Find a window by partial title match."""
    if not gw:
        return None
    windows = gw.getWindowsWithTitle(title_or_app)
    visible_windows = [w for w in windows if w.visible and w.title.strip()]
    if visible_windows:
        return get_window_info(visible_windows[0])
    return None


def activate_window(title_or_app: str) -> bool:
    """Activate (focus) a window by title."""
    if not gw:
        return False
    windows = gw.getWindowsWithTitle(title_or_app)
    visible_windows = [w for w in windows if w.visible and w.title.strip()]
    
    if not visible_windows:
        return False
        
    win = visible_windows[0]
    
    # Try multiple times to ensure activation
    for _ in range(3):
        try:
            if win.isMinimized:
                win.restore()
                
            # Use native Windows API to bypass foreground lock cleanly
            import ctypes
            user32 = ctypes.windll.user32
            # Use ALT key trick to bypass foreground lock cleanly without messing up thread queues/focus
            user32.keybd_event(0x12, 0, 0, 0) # ALT down
            user32.keybd_event(0x12, 0, 2, 0) # ALT up
            
            user32.SetForegroundWindow(win._hWnd)
                
            time.sleep(0.5)
            
            get_target_window_manager().set_target(win._hWnd, win.title)
            return True
        except Exception:
            pass
        time.sleep(0.5)
        
    return False


def minimize_window(title_or_app: str) -> bool:
    if not gw:
        return False
    windows = gw.getWindowsWithTitle(title_or_app)
    if windows:
        windows[0].minimize()
        return True
    return False


def maximize_window(title_or_app: str) -> bool:
    if not gw:
        return False
    windows = gw.getWindowsWithTitle(title_or_app)
    if windows:
        windows[0].maximize()
        return True
    return False


def close_window(title_or_app: str) -> bool:
    if not gw:
        return False
    windows = gw.getWindowsWithTitle(title_or_app)
    if windows:
        windows[0].close()
        return True
    return False
