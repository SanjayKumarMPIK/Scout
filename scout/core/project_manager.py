"""Project manager – persistent registry, type detection, and package-manager detection.

Projects are stored in ``~/.scout/projects.json`` as a simple dict keyed by name.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from scout.config import APP_DIR

PROJECTS_FILE = APP_DIR / "projects.json"


# ── Data structures ────────────────────────────────────────────────────

@dataclass
class ProjectInfo:
    """Rich information about a registered project."""
    name: str
    path: str
    project_type: str = "Unknown"
    frameworks: list[str] = field(default_factory=list)
    has_git: bool = False
    package_manager: str = ""
    detected_tools: dict[str, str] = field(default_factory=dict)


# ── Persistence ────────────────────────────────────────────────────────

def _load_projects() -> dict[str, str]:
    """Load {name: path} from projects.json."""
    if not PROJECTS_FILE.exists():
        return {}
    try:
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_projects(projects: dict[str, str]) -> None:
    """Persist {name: path} to projects.json."""
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2), encoding="utf-8")


# ── CRUD ───────────────────────────────────────────────────────────────

def add_project(name: str, path: str) -> tuple[bool, str]:
    """Register a project. Returns (success, message)."""
    p = Path(path)
    if not p.is_dir():
        return False, f"Directory does not exist: {path}"

    name = name.lower().strip()
    if not name:
        return False, "Project name cannot be empty"

    projects = _load_projects()
    if name in projects:
        return False, f"Project '{name}' already exists (use 'project remove' first)"

    projects[name] = str(p.resolve())
    _save_projects(projects)
    return True, f"Project '{name}' registered at {p.resolve()}"


def remove_project(name: str) -> tuple[bool, str]:
    """Unregister a project. Returns (success, message)."""
    name = name.lower().strip()
    projects = _load_projects()
    if name not in projects:
        return False, f"Project '{name}' not found"

    del projects[name]
    _save_projects(projects)
    return True, f"Project '{name}' removed"


def get_project(name: str) -> tuple[str, str] | None:
    """Return (name, path) or None."""
    name = name.lower().strip()
    projects = _load_projects()
    path = projects.get(name)
    if path is None:
        return None
    return name, path


def list_projects() -> dict[str, str]:
    """Return all registered projects as {name: path}."""
    return _load_projects()


# ── Project type detection ─────────────────────────────────────────────

_TYPE_MARKERS: list[tuple[str, str, list[str]]] = [
    # (filename_or_glob, project_type, frameworks_hint)
    ("manage.py",            "Python",       ["Django"]),
    ("next.config.js",       "Node.js",      ["Next.js"]),
    ("next.config.mjs",      "Node.js",      ["Next.js"]),
    ("next.config.ts",       "Node.js",      ["Next.js"]),
    ("nuxt.config.ts",       "Node.js",      ["Nuxt"]),
    ("vite.config.js",       "Node.js",      ["Vite"]),
    ("vite.config.ts",       "Node.js",      ["Vite"]),
    ("angular.json",         "Node.js",      ["Angular"]),
    ("app.json",             "Node.js",      ["React Native"]),
    ("expo.json",            "Node.js",      ["Expo / React Native"]),
    ("Cargo.toml",           "Rust",         []),
    ("pom.xml",              "Java",         ["Maven"]),
    ("build.gradle",         "Java",         ["Gradle"]),
    ("build.gradle.kts",     "Kotlin",       ["Gradle"]),
    ("go.mod",               "Go",           []),
    ("pyproject.toml",       "Python",       []),
    ("requirements.txt",     "Python",       []),
    ("setup.py",             "Python",       []),
    ("package.json",         "Node.js",      []),
]


def detect_project_type(path: str) -> tuple[str, list[str]]:
    """Detect project type and framework hints from marker files.

    Returns (project_type, [framework_hints]).
    """
    p = Path(path)
    if not p.is_dir():
        return "Unknown", []

    for filename, ptype, frameworks in _TYPE_MARKERS:
        if (p / filename).exists():
            return ptype, list(frameworks)

    return "Unknown", []


# ── Package-manager detection ──────────────────────────────────────────

def detect_package_manager(path: str) -> str:
    """Detect the package manager for a project directory.

    Returns a string like 'npm', 'pnpm', 'yarn', 'pip', 'uv', or ''.
    """
    p = Path(path)
    if not p.is_dir():
        return ""

    # Node.js lock files (most specific first)
    if (p / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (p / "yarn.lock").exists():
        return "yarn"
    if (p / "bun.lockb").exists():
        return "bun"
    if (p / "package-lock.json").exists():
        return "npm"
    if (p / "package.json").exists():
        return "npm"  # default for Node when no lock file

    # Python
    if (p / "uv.lock").exists() or (p / ".python-version").exists():
        if shutil.which("uv"):
            return "uv"
    if (p / "Pipfile").exists():
        return "pipenv"
    if (p / "requirements.txt").exists() or (p / "pyproject.toml").exists() or (p / "setup.py").exists():
        return "pip"

    # Rust
    if (p / "Cargo.toml").exists():
        return "cargo"

    # Go
    if (p / "go.mod").exists():
        return "go"

    # Java/Kotlin
    if (p / "pom.xml").exists():
        return "maven"
    if (p / "build.gradle").exists() or (p / "build.gradle.kts").exists():
        return "gradle"

    return ""


# ── Rich project info ─────────────────────────────────────────────────

def get_project_info(name: str) -> ProjectInfo | None:
    """Build a ProjectInfo with detected metadata."""
    entry = get_project(name)
    if entry is None:
        return None

    name, path = entry
    ptype, frameworks = detect_project_type(path)
    pm = detect_package_manager(path)
    has_git = (Path(path) / ".git").is_dir()

    return ProjectInfo(
        name=name,
        path=path,
        project_type=ptype,
        frameworks=frameworks,
        has_git=has_git,
        package_manager=pm,
    )


# ── Package-manager command mapping ───────────────────────────────────

_PM_COMMANDS: dict[str, dict[str, str]] = {
    "npm":    {"install": "npm install",   "start": "npm start",      "build": "npm run build",  "test": "npm test"},
    "pnpm":   {"install": "pnpm install",  "start": "pnpm start",     "build": "pnpm build",     "test": "pnpm test"},
    "yarn":   {"install": "yarn install",  "start": "yarn start",     "build": "yarn build",     "test": "yarn test"},
    "bun":    {"install": "bun install",   "start": "bun start",      "build": "bun build",      "test": "bun test"},
    "pip":    {"install": "pip install -r requirements.txt", "start": "", "build": "", "test": "python -m pytest"},
    "uv":     {"install": "uv pip install -r requirements.txt", "start": "", "build": "", "test": "python -m pytest"},
    "pipenv": {"install": "pipenv install", "start": "", "build": "", "test": "pipenv run pytest"},
    "cargo":  {"install": "cargo build",    "start": "cargo run",      "build": "cargo build --release", "test": "cargo test"},
    "go":     {"install": "go mod download","start": "go run .",       "build": "go build",       "test": "go test ./..."},
    "maven":  {"install": "mvn install",    "start": "",               "build": "mvn package",    "test": "mvn test"},
    "gradle": {"install": "gradle build",   "start": "",               "build": "gradle build",   "test": "gradle test"},
}


def get_pm_command(pm: str, action: str) -> str | None:
    """Return the shell command for a package-manager action, or None."""
    cmds = _PM_COMMANDS.get(pm, {})
    cmd = cmds.get(action, None)
    return cmd if cmd else None
