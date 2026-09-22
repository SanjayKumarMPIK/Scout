# Scout

**Personal Windows Automation Assistant** — a lightweight, terminal-first automation system.

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Run Scout
python -m scout.cli
```

## Available commands (V1)

| Command              | Description                                    |
| -------------------- | ---------------------------------------------- |
| `help`               | Show available commands                        |
| `system`             | Display CPU, memory, battery and OS info       |
| `open <app>`         | Open an application (chrome, vscode, notepad…) |
| `run <command>`      | Run a shell command (with safety checks)       |
| `type <text>`        | Type text via the keyboard                     |
| `press <key\|combo>` | Press a key or combo (enter, ctrl+c, alt+tab)  |
| `screenshot`         | Take a screenshot                              |
| `files [dir]`        | List files in a directory                      |
| `clear`              | Clear the terminal                             |
| `exit`               | Exit Scout                                     |

## Safety

Commands classified as **potentially destructive** (delete, format, shutdown, etc.)
require explicit user confirmation before execution. Some patterns are hard-blocked
entirely.

## Architecture

```
scout/
├── cli.py             # Interactive shell / REPL
├── parser.py          # Input parser (NL intent layer in Phase 4)
├── config.py          # Constants, app aliases, safety tokens
├── commands/          # One module per command group
│   ├── system.py
│   ├── apps.py
│   ├── terminal.py
│   ├── files.py
│   └── automation.py
└── core/
    ├── executor.py    # Dispatches parsed input to handlers
    ├── registry.py    # Command registration & lookup
    └── safety.py      # Action classification & confirmation
```

## Future phases

| Phase | Feature                           |
| ----- | --------------------------------- |
| 2     | Better Windows automation         |
| 3     | Developer / project workflows     |
| 4     | Natural-language AI interpreter   |
| 5     | SQLite personal memory            |
| 6     | Local LLM / Ollama support        |
| 7     | Voice input / output              |
| 8     | Custom workflow / plugin system   |

## License

Private project.
