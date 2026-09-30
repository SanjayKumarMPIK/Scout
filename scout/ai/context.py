"""Context gathering for AI requests."""

from __future__ import annotations

import os
from pathlib import Path

from scout.core.project_manager import list_projects



def gather_context() -> str:
    """Gather minimal state information to inject into the system prompt."""
    cwd = Path.cwd()
    projects = list_projects()
    lines = [
        f"Current Directory: {cwd}",
        "Registered Projects:",
    ]
    if projects:
        for name, path in projects.items():
            lines.append(f"- {name}: {path}")
    else:
        lines.append("- (none)")

    return "\n".join(lines)
