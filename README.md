# Scout

**Personal Windows Automation Assistant** — a lightweight, terminal-first automation system.

## Install (Windows)

1. Download `ScoutSetup-<version>.exe` and run it (no admin rights needed).
2. Open a new terminal and type `scout` (or use the Start Menu shortcut).
3. On first launch, pick your AI provider and enter **your own** API key.

Everything personal stays on your machine and is never bundled in the installer:

| Data | Location |
| --- | --- |
| API keys | Windows Credential Manager |
| Memories | `%USERPROFILE%\.scout\data\scout.db` |
| Settings | `%USERPROFILE%\.scout\config.json` |

Uninstalling asks whether to also delete your memories/settings.

## Run from source

```bash
pip install -r requirements.txt
python -m scout.cli
```

## Build the installer

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

Output: `dist\installer\ScoutSetup-<version>.exe`. The script installs PyInstaller and
(via winget) Inno Setup if missing. Bump `__version__` in `scout/__init__.py` per release.

## Available commands

| Command                    | Aliases      | Description                                    |
| -------------------------- | ------------ | ---------------------------------------------- |
| `help`                     | `?`, `h`     | Show available commands                        |
| `system`                   | `sys`        | Display CPU, memory, battery and OS info       |
| `open <app>`               | —            | Open an application (chrome, vscode, notepad…) |
| `run <command>`            | —            | Run a shell command (with safety checks)       |
| `type <text>`              | —            | Type text via the keyboard                     |
| `press <key\|combo>`       | —            | Press a key or combo (enter, ctrl+c, alt+tab)  |
| `screenshot`               | `ss`         | Take a screenshot                              |
| `files [dir]`              | `ls`, `dir`  | List files in a directory                      |
| `workflow list`            | `wf list`    | List available workflows                       |
| `workflow show <name>`     | `wf show`    | Display workflow steps                         |
| `workflow run <name>`      | `wf run`     | Execute a workflow                             |
| `clear`                    | `cls`        | Clear the terminal                             |
| `exit`                     | `quit`, `q`  | Exit Scout                                     |

## Workflows

Workflows are reusable sequences of Scout actions defined as JSON files.

Place `.json` files in:
- `workflows/` (project-local, next to the `scout/` package)
- `~/.scout/workflows/` (global)

### Workflow format

```json
{
  "name": "start-web",
  "description": "Start my web development environment",
  "steps": [
    { "action": "open_app", "app": "vscode" },
    { "action": "change_directory", "path": "${projects.web}" },
    { "action": "run_command", "command": "npm run dev" },
    { "action": "wait", "seconds": 3 },
    { "action": "open_url", "url": "http://localhost:3000" }
  ]
}
```

### Supported actions

| Action             | Parameters                  |
| ------------------ | --------------------------- |
| `open_app`         | `app`                       |
| `run_command`      | `command`, optional `cwd`   |
| `type`             | `text`                      |
| `press`            | `key` (e.g. `ctrl+c`)      |
| `wait`             | `seconds` (0–300)           |
| `open_url`         | `url`                       |
| `change_directory` | `path`                      |

### Variable substitution

Use `${section.key}` to reference values from `~/.scout/config.json`:

```json
{
  "projects": {
    "native": "C:\\PROJECTS\\Native\\android",
    "web": "C:\\PROJECTS\\Web"
  }
}
```

Then in workflows: `"path": "${projects.native}"`

## Safety

- **Blocked patterns**: `format c:`, etc. — always rejected.
- **Destructive tokens**: `rm`, `del`, `shutdown`, `taskkill`, etc. — require explicit confirmation.
- **Workflow safety**: every workflow step goes through the same safety layer as interactive commands.

## Architecture

```
scout/
├── cli.py               # Interactive shell / REPL
├── parser.py            # Input parser (NL intent layer in Phase 4)
├── config.py            # Constants, app aliases, safety tokens
├── user_config.py       # User config.json + variable substitution
├── commands/
│   ├── system.py        # system info
│   ├── apps.py          # open applications
│   ├── terminal.py      # run shell commands
│   ├── files.py         # directory listing
│   ├── automation.py    # type, press, screenshot
│   └── workflow_cmd.py  # workflow CLI front-end
├── core/
│   ├── executor.py      # Dispatches parsed input to handlers
│   ├── registry.py      # Command registration & lookup
│   └── safety.py        # Action classification & confirmation
└── workflow/
    ├── parser.py        # Workflow JSON parser + validation
    ├── actions.py       # Translates steps into existing commands
    └── manager.py       # Discovery, listing, execution
```

## Web Research & Browser Interaction

Scout includes an intelligent, secure web research and browser automation layer:

### Web Tools

| Tool | Type | Description |
| --- | --- | --- |
| `web_search` | Search | Search web with single or multiple queries across DuckDuckGo, Tavily, Google, or Brave. |
| `fetch_webpage` | Static HTTP | Fast direct HTTP page fetcher. Strips boilerplate and detects if JavaScript rendering is needed. |
| `browser_navigate` | Browser | Opens URLs in an isolated Playwright Chromium instance. Waits for page readiness. |
| `browser_extract` | Browser | Extracts text, headings, links, tables, lists, specific CSS elements, or structured fields. |
| `browser_interact` | Browser | Interacts with web pages (click, type, select option, scroll, navigate). Consequential actions require user confirmation. |
| `browser_close` | Browser | Shuts down the active browser session and frees resources. |

### Configuration (`~/.scout/config.json`)

```json
{
  "web": {
    "search_provider": "duckduckgo",
    "tavily_api_key": "tvly-...",
    "google_api_key": "AIza...",
    "google_cse_id": "0123...",
    "brave_api_key": "BSA...",
    "request_timeout": 15.0,
    "max_content_length": 8000,
    "headless": true,
    "respect_robots_txt": true
  }
}
```

*Search provider credentials can also be set via environment variables: `SCOUT_SEARCH_PROVIDER`, `TAVILY_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, `BRAVE_API_KEY`.*

### Security & Safety

- **SSRF Defense**: Automatically blocks loopback, private RFC-1918 networks, link-local, cloud metadata (`169.254.169.254`), and local domains. Redirect targets are checked on each hop.
- **Untrusted Content Separation**: All extracted web data is wrapped in security boundaries with prompt injection warnings.
- **Permission System**: Form submissions, typing, and clicks during `browser_interact` require explicit user authorization.


## License

Private project.
