"""Demo and verification of SCOUT Terminal V2 UI."""

import sys
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from scout.ui.avatar import get_neural_core, get_compact_core
from scout.ui.header import print_persistent_header
from scout.ui.chat import (
    print_user_message,
    print_scout_message,
    print_scout_status,
    print_scout_error,
    print_plan_overview,
    print_status_bar,
    get_prompt_markup,
)

console = Console()

def test_v2():
    console.print("\n[bold cyan]=== SCOUT V2 TERMINAL PRESENTATION DEMO ===[/]\n")
    print_persistent_header("gemini-1.5-pro", "gemini", voice_mode=False, agent_state="ONLINE / READY")
    
    print_user_message("Show me git status and system resources")
    
    print_scout_status("Checking git repository status...", "executing")
    print_scout_status("Inspecting active windows and display...", "verifying")
    print_scout_status("Task completed successfully", "success")
    
    print_scout_message(
        "I've verified your environment, sir!\n\n"
        "* **Git Status**: Working branch `master` is clean and up to date.\n"
        "* **System State**: Windows 11 host operating normally.\n"
        "* **Active Tools**: All 18 registered automation tools are ready."
    )
    
    print_plan_overview(
        [
            "Inspect git working directory (`git_status`)",
            "Verify display geometry (`verify_screen`)",
            "Synthesize system summary response",
        ],
        title="Diagnostic Execution Plan",
    )
    
    print_status_bar("IDLE / READY", False, "gemini")
    console.print(get_prompt_markup() + "_")

if __name__ == "__main__":
    test_v2()
