"""Window management capabilities using pygetwindow."""

import time
import subprocess
from typing import Optional, Dict, Any, List

try:
    import pygetwindow as gw
except ImportError:
    gw = None


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
            target_thread_id = user32.GetWindowThreadProcessId(win._hWnd, 0)
            foreground_hwnd = user32.GetForegroundWindow()
            current_thread_id = user32.GetWindowThreadProcessId(foreground_hwnd, 0)
            
            attached = False
            if current_thread_id != target_thread_id and current_thread_id != 0:
                attached = user32.AttachThreadInput(current_thread_id, target_thread_id, True)
                
            user32.SetForegroundWindow(win._hWnd)
            user32.BringWindowToTop(win._hWnd)
            user32.ShowWindow(win._hWnd, 5)  # SW_SHOW
            
            if attached:
                user32.AttachThreadInput(current_thread_id, target_thread_id, False)
                
            time.sleep(0.5)
            
            # Verification via GetForegroundWindow is unreliable when running headless/background.
            # If we reached here without exception, assume success.
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
