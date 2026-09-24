"""apps command – open applications by friendly name."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console

from scout.config import APP_ALIASES
from scout.core.registry import registry

console = Console()


def _resolve_app(name: str) -> str | None:
    """Return the first working executable path for *name*, or None."""
    candidates = APP_ALIASES.get(name.lower(), [name])
    for candidate in candidates:
        # Try PATH lookup first
        found = shutil.which(candidate)
        if found:
            return found
    # If nothing on PATH, return the last candidate as-is (might be an
    # absolute path that exists but isn't on PATH).
    from pathlib import Path
    last = candidates[-1]
    if Path(last).exists():
        return last
    return None


def _open_cmd(args: list[str]) -> None:
    """Open an application by name."""
    if not args:
        console.print("[red]Usage:[/] open <application>")
        return

    app_name = args[0].lower()
    exe = _resolve_app(app_name)

    if exe is None:
        console.print(f"[red]Could not find application:[/] {app_name}")
        console.print("[dim]Check the name or add it to scout/config.py APP_ALIASES.[/dim]")
        return

    try:
        subprocess.Popen(  # noqa: S603
            [exe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        console.print(f"[green][+][/] {app_name} opened")
    except OSError as exc:
        console.print(f"[red]Failed to open {app_name}:[/] {exc}")


registry.register(
    name="open",
    handler=_open_cmd,
    usage="open <application>",
    description="Open an application (e.g. chrome, vscode, notepad).",
    group="System",
)
