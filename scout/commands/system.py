"""system command – display host system information."""

from __future__ import annotations

import platform

import psutil
from rich.console import Console
from rich.table import Table

from scout.core.registry import registry

console = Console()


def _system_cmd(args: list[str]) -> None:
    """Print CPU, memory, battery and OS details."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    mem_used_gb = mem.used / (1024 ** 3)
    mem_total_gb = mem.total / (1024 ** 3)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", min_width=10)
    table.add_column()

    table.add_row("CPU", f"{cpu_percent}%")
    table.add_row("Memory", f"{mem_used_gb:.1f} / {mem_total_gb:.1f} GB")

    battery = psutil.sensors_battery()
    if battery is not None:
        plugged = " (plugged in)" if battery.power_plugged else ""
        table.add_row("Battery", f"{battery.percent:.0f}%{plugged}")
    else:
        table.add_row("Battery", "N/A")

    table.add_row("OS", f"{platform.system()} {platform.release()}")
    table.add_row("Host", platform.node())

    console.print()
    console.print(table)
    console.print()


registry.register(
    name="system",
    handler=_system_cmd,
    usage="system",
    description="Display system information (CPU, memory, battery, OS).",
    aliases=["sys", "sysinfo"],
)
