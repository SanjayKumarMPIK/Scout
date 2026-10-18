"""Scout Terminal UI package."""

from scout.ui.theme import THEME_COLORS, scout_theme
from scout.ui.avatar import get_neural_core, get_compact_core
from scout.ui.header import build_header, build_identity_block, print_persistent_header
from scout.ui.chat import (
    print_user_message,
    print_scout_message,
    print_scout_acknowledgment,
    print_scout_status,
    print_command_output,
    print_scout_error,
    print_plan_overview,
    print_status_bar,
    get_prompt_markup,
    prompt_user,
    ScoutPrompt,
)
from scout.ui.activity import scout_activity
from scout.ui.startup import animate_startup

__all__ = [
    "THEME_COLORS",
    "scout_theme",
    "get_neural_core",
    "get_compact_core",
    "build_header",
    "build_identity_block",
    "print_persistent_header",
    "print_user_message",
    "print_scout_message",
    "print_scout_acknowledgment",
    "print_scout_status",
    "print_scout_error",
    "print_plan_overview",
    "print_status_bar",
    "get_prompt_markup",
    "scout_activity",
    "animate_startup",
]
