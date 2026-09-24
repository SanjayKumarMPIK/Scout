"""Scout configuration constants."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
APP_NAME = "Scout"
APP_VERSION = "0.1.0"
APP_DIR = Path.home() / ".scout"
SCREENSHOT_DIR = APP_DIR / "screenshots"

# Ensure directories exist on import
APP_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)

# ── Application aliases ────────────────────────────────────────────────
# Maps user-friendly names to Windows executable names or paths.
# Entries are tried in order: first as a bare executable (via PATH),
# then as an absolute path.
APP_ALIASES: dict[str, list[str]] = {
    "chrome":   ["chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
    "firefox":  ["firefox", r"C:\Users\rhino\.cache\selenium\firefox\win64\155.0\firefox.exe"],
    "edge":     ["msedge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
    "vscode":   ["code"],
    "code":     ["code"],
    "notepad":  ["notepad"],
    "explorer": ["explorer"],
    "cmd":      ["cmd"],
    "powershell": ["powershell"],
    "terminal": ["wt"],               # Windows Terminal
    "calc":     ["calc"],
    "paint":    ["mspaint"],
    "word":     ["winword"],
    "excel":    ["excel"],
    "spotify":  ["spotify"],
}

# ── Safety ─────────────────────────────────────────────────────────────
# Shell tokens that make a `run` command potentially destructive.
DESTRUCTIVE_TOKENS: list[str] = [
    "rm ", "rm\t", "rmdir", "del ", "del\t",
    "format ", "format\t",
    "shutdown", "restart",
    "reg delete", "reg add",
    "takeown", "icacls",
    "diskpart",
    "bcdedit",
    "sfc ",
    "dism ",
    "net stop", "net start",
    "taskkill",
    "powershell -command remove",
    "powershell -c remove",
    "rd ", "rd\t",
]

# Patterns that are always blocked even if the user confirms.
BLOCKED_PATTERNS: list[str] = [
    "format c:",
    "format d:",
    ":(){ :|:& };:",     # fork-bomb (unlikely on Windows, but safe-guard)
]
