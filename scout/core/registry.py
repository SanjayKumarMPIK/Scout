"""Command registry – maps command names to handler functions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Command:
    """Metadata for a registered command."""
    name: str
    handler: Callable[[list[str]], None]
    usage: str
    description: str
    aliases: list[str] = field(default_factory=list)
    group: str = "General"


class Registry:
    """Central store of all available commands."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    # ── public API ─────────────────────────────────────────────────────
    def register(
        self,
        name: str,
        handler: Callable[[list[str]], None],
        usage: str = "",
        description: str = "",
        aliases: list[str] | None = None,
        group: str = "General",
    ) -> None:
        cmd = Command(
            name=name,
            handler=handler,
            usage=usage or name,
            description=description,
            aliases=aliases or [],
            group=group,
        )
        self._commands[name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def all_unique(self) -> list[Command]:
        """Return each command once (no alias duplicates), sorted by name."""
        seen: set[str] = set()
        out: list[Command] = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                out.append(cmd)
        return sorted(out, key=lambda c: c.name)

    def by_group(self) -> dict[str, list[Command]]:
        """Return commands grouped by their group label, each list sorted by name."""
        groups: dict[str, list[Command]] = defaultdict(list)
        seen: set[str] = set()
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                groups[cmd.group].append(cmd)
        for cmds in groups.values():
            cmds.sort(key=lambda c: c.name)
        return dict(groups)


# Singleton used throughout Scout.
registry = Registry()
