"""PyInstaller entry point for Scout.

PyInstaller needs a plain script (not ``python -m scout``) as its entry.
This also keeps the console window open if Scout crashes, so users who
double-clicked the shortcut can actually read the error.
"""

import sys
import traceback


def _run() -> None:
    from scout.cli import main

    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("\nScout crashed unexpectedly. Please report the error above.")
        try:
            input("Press Enter to close...")
        except EOFError:
            pass
        sys.exit(1)


if __name__ == "__main__":
    _run()
