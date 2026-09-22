"""Parser – splits raw user input into (command, args).

Currently a thin shim; will become the natural-language intent layer in Phase 4.
"""

from __future__ import annotations


def parse(raw: str) -> tuple[str, list[str]]:
    """Return (command_name, arg_list) from raw input."""
    parts = raw.strip().split()
    if not parts:
        return ("", [])
    return (parts[0].lower(), parts[1:])
