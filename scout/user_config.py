"""Scout user configuration – loads and provides access to config.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scout.config import APP_DIR

CONFIG_FILE = APP_DIR / "config.json"

# Default config written on first run.
_DEFAULT_CONFIG: dict = {
    "projects": {
        "native": r"C:\PROJECTS\Native\android",
        "web": r"C:\PROJECTS\Web",
    },
    "ai": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "api_key_env": "SCOUT_GROQ_API_KEY",
    },
}


def _ensure_config() -> None:
    """Create the default config.json if it doesn't exist."""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(_DEFAULT_CONFIG, indent=2), encoding="utf-8")


def load_config() -> dict:
    """Load and return the user configuration dictionary."""
    _ensure_config()
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _DEFAULT_CONFIG.copy()


def resolve_variables(text: str, config: dict | None = None) -> str:
    """Replace ``${section.key}`` placeholders with config values.

    Supports one level of nesting: ``${projects.native}`` looks up
    ``config["projects"]["native"]``.  Unknown variables are left as-is.
    """
    if config is None:
        config = load_config()

    def _replacer(match: re.Match) -> str:
        path = match.group(1)
        parts = path.split(".", maxsplit=1)
        try:
            if len(parts) == 2:
                return str(config[parts[0]][parts[1]])
            return str(config[parts[0]])
        except (KeyError, TypeError):
            return match.group(0)  # leave unresolved

    return re.sub(r"\$\{([^}]+)\}", _replacer, text)
