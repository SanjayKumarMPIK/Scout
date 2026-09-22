"""files command – list files in the current working directory."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from scout.core.registry import registry

console = Console()

_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]


def _human_size(nbytes: int) -> str:
    size = float(nbytes)
    for unit in _SIZE_UNITS[:-1]:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} {_SIZE_UNITS[-1]}"


def _files_cmd(args: list[str]) -> None:
    """List files and directories in the current (or given) directory."""
    target = Path(args[0]) if args else Path.cwd()
    if not target.is_dir():
        console.print(f"[red]Not a directory:[/] {target}")
        return

    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    if not entries:
        console.print("[dim]Directory is empty.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Name")
    table.add_column("Type", width=6)
    table.add_column("Size", justify="right", width=10)

    for entry in entries:
        if entry.is_dir():
            table.add_row(f"[bold blue]{entry.name}/[/]", "dir", "")
        else:
            table.add_row(entry.name, "file", _human_size(entry.stat().st_size))

    console.print()
    console.print(f"[dim]{target.resolve()}[/dim]")
    console.print(table)
    console.print(f"\n[dim]{len(entries)} items[/dim]")


registry.register(
    name="files",
    handler=_files_cmd,
    usage="files [directory]",
    description="List files in the current or specified directory.",
    aliases=["ls", "dir"],
)
