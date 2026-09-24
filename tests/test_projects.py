"""Tests for Phase 3: project management, type detection, package-manager detection,
git commands, dev commands, and workflow/project integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.core.project_manager import (
    PROJECTS_FILE,
    ProjectInfo,
    _load_projects,
    _save_projects,
    add_project,
    detect_package_manager,
    detect_project_type,
    get_pm_command,
    get_project,
    get_project_info,
    list_projects,
    remove_project,
)
from scout.workflow.actions import StepResult, execute_step
from scout.workflow.parser import WorkflowStep


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_projects(tmp_path: Path, monkeypatch):
    """Redirect projects.json to a temp file for every test."""
    fake_file = tmp_path / "projects.json"
    monkeypatch.setattr("scout.core.project_manager.PROJECTS_FILE", fake_file)
    yield fake_file


@pytest.fixture
def sample_node_project(tmp_path: Path):
    """Create a minimal Node.js project directory."""
    proj = tmp_path / "mynode"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"mynode"}', encoding="utf-8")
    (proj / "package-lock.json").write_text("{}", encoding="utf-8")
    (proj / ".git").mkdir()
    return proj


@pytest.fixture
def sample_python_project(tmp_path: Path):
    """Create a minimal Python project directory."""
    proj = tmp_path / "mypython"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[project]\nname='x'", encoding="utf-8")
    (proj / "requirements.txt").write_text("rich\n", encoding="utf-8")
    return proj


@pytest.fixture
def sample_vite_project(tmp_path: Path):
    """Create a project with Vite config."""
    proj = tmp_path / "myvite"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"v"}', encoding="utf-8")
    (proj / "vite.config.ts").write_text("export default {}", encoding="utf-8")
    (proj / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    return proj


# ── Project registration tests ────────────────────────────────────────

class TestProjectRegistration:
    def test_add_project(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        ok, msg = add_project("test", str(proj))
        assert ok
        assert "registered" in msg.lower()

    def test_add_duplicate(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        add_project("dup", str(proj))
        ok, msg = add_project("dup", str(proj))
        assert not ok
        assert "already exists" in msg.lower()

    def test_add_nonexistent_path(self):
        ok, msg = add_project("bad", r"C:\DOES_NOT_EXIST_12345")
        assert not ok

    def test_add_empty_name(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        ok, msg = add_project("", str(proj))
        assert not ok

    def test_remove_project(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        add_project("removeme", str(proj))
        ok, msg = remove_project("removeme")
        assert ok
        assert get_project("removeme") is None

    def test_remove_nonexistent(self):
        ok, msg = remove_project("ghost")
        assert not ok

    def test_list_projects(self, tmp_path: Path):
        p1 = tmp_path / "a"
        p2 = tmp_path / "b"
        p1.mkdir()
        p2.mkdir()
        add_project("alpha", str(p1))
        add_project("beta", str(p2))
        projects = list_projects()
        assert "alpha" in projects
        assert "beta" in projects

    def test_get_project(self, tmp_path: Path):
        proj = tmp_path / "proj"
        proj.mkdir()
        add_project("found", str(proj))
        result = get_project("found")
        assert result is not None
        assert result[0] == "found"

    def test_get_project_not_found(self):
        assert get_project("nonexistent") is None


# ── Project persistence tests ─────────────────────────────────────────

class TestProjectPersistence:
    def test_persistence_roundtrip(self, tmp_path: Path, _isolated_projects):
        proj = tmp_path / "persistent"
        proj.mkdir()
        add_project("persist", str(proj))
        # Re-load from file
        loaded = _load_projects()
        assert "persist" in loaded

    def test_corrupt_file(self, _isolated_projects):
        _isolated_projects.write_text("not json!!!", encoding="utf-8")
        result = _load_projects()
        assert result == {}  # graceful fallback


# ── Project type detection tests ──────────────────────────────────────

class TestProjectTypeDetection:
    def test_detect_node(self, sample_node_project: Path):
        ptype, frameworks = detect_project_type(str(sample_node_project))
        assert ptype == "Node.js"

    def test_detect_python(self, sample_python_project: Path):
        ptype, frameworks = detect_project_type(str(sample_python_project))
        assert ptype == "Python"

    def test_detect_vite(self, sample_vite_project: Path):
        ptype, frameworks = detect_project_type(str(sample_vite_project))
        assert ptype == "Node.js"
        assert "Vite" in frameworks

    def test_detect_django(self, tmp_path: Path):
        proj = tmp_path / "django"
        proj.mkdir()
        (proj / "manage.py").write_text("", encoding="utf-8")
        ptype, frameworks = detect_project_type(str(proj))
        assert ptype == "Python"
        assert "Django" in frameworks

    def test_detect_nextjs(self, tmp_path: Path):
        proj = tmp_path / "next"
        proj.mkdir()
        (proj / "next.config.js").write_text("", encoding="utf-8")
        ptype, frameworks = detect_project_type(str(proj))
        assert "Next.js" in frameworks

    def test_detect_rust(self, tmp_path: Path):
        proj = tmp_path / "rust"
        proj.mkdir()
        (proj / "Cargo.toml").write_text("", encoding="utf-8")
        ptype, _ = detect_project_type(str(proj))
        assert ptype == "Rust"

    def test_detect_java_maven(self, tmp_path: Path):
        proj = tmp_path / "java"
        proj.mkdir()
        (proj / "pom.xml").write_text("", encoding="utf-8")
        ptype, frameworks = detect_project_type(str(proj))
        assert ptype == "Java"
        assert "Maven" in frameworks

    def test_detect_unknown(self, tmp_path: Path):
        proj = tmp_path / "empty"
        proj.mkdir()
        ptype, _ = detect_project_type(str(proj))
        assert ptype == "Unknown"

    def test_detect_nonexistent_path(self):
        ptype, _ = detect_project_type(r"C:\NOPE_12345")
        assert ptype == "Unknown"


# ── Package-manager detection tests ───────────────────────────────────

class TestPackageManagerDetection:
    def test_npm_lockfile(self, sample_node_project: Path):
        assert detect_package_manager(str(sample_node_project)) == "npm"

    def test_pnpm_lockfile(self, sample_vite_project: Path):
        assert detect_package_manager(str(sample_vite_project)) == "pnpm"

    def test_yarn_lockfile(self, tmp_path: Path):
        proj = tmp_path / "yarn_proj"
        proj.mkdir()
        (proj / "package.json").write_text("{}", encoding="utf-8")
        (proj / "yarn.lock").write_text("", encoding="utf-8")
        assert detect_package_manager(str(proj)) == "yarn"

    def test_pip_project(self, sample_python_project: Path):
        assert detect_package_manager(str(sample_python_project)) == "pip"

    def test_cargo_project(self, tmp_path: Path):
        proj = tmp_path / "rust"
        proj.mkdir()
        (proj / "Cargo.toml").write_text("", encoding="utf-8")
        assert detect_package_manager(str(proj)) == "cargo"

    def test_empty_dir(self, tmp_path: Path):
        proj = tmp_path / "empty"
        proj.mkdir()
        assert detect_package_manager(str(proj)) == ""

    def test_pm_command_npm(self):
        assert get_pm_command("npm", "install") == "npm install"
        assert get_pm_command("npm", "test") == "npm test"

    def test_pm_command_unknown(self):
        assert get_pm_command("unknown_pm", "install") is None


# ── Project info tests ────────────────────────────────────────────────

class TestProjectInfo:
    def test_full_info(self, sample_node_project: Path):
        add_project("nodeapp", str(sample_node_project))
        info = get_project_info("nodeapp")
        assert info is not None
        assert info.project_type == "Node.js"
        assert info.has_git is True
        assert info.package_manager == "npm"

    def test_info_nonexistent(self):
        assert get_project_info("ghost") is None


# ── Git command construction tests ────────────────────────────────────

class TestGitCommands:
    def test_git_status_on_project(self, sample_node_project: Path):
        """Verify _run_git can execute a harmless git command."""
        add_project("gittest", str(sample_node_project))

        # Initialize the git repo properly for testing
        import subprocess
        subprocess.run(
            ["git", "init"], cwd=str(sample_node_project),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )

        from scout.commands.git_cmd import _run_git
        # Should not raise
        _run_git(str(sample_node_project), ["status", "--short"])

    def test_resolve_nonexistent_project(self):
        from scout.commands.git_cmd import _resolve_project
        assert _resolve_project(["nonexistent"]) is None

    def test_resolve_non_git_project(self, sample_python_project: Path):
        add_project("nongit", str(sample_python_project))
        from scout.commands.git_cmd import _resolve_project
        assert _resolve_project(["nongit"]) is None


# ── Workflow/project integration tests ────────────────────────────────

class TestWorkflowProjectIntegration:
    def test_project_run_step(self, sample_node_project: Path):
        add_project("wftest", str(sample_node_project))
        step = WorkflowStep(
            1, "project_run",
            {"project": "wftest", "command": "echo hello"},
            {},
        )
        result = execute_step(step)
        assert result.success

    def test_project_run_nonexistent(self):
        step = WorkflowStep(
            1, "project_run",
            {"project": "nope", "command": "echo hi"},
            {},
        )
        result = execute_step(step)
        assert not result.success
        assert "not found" in result.message.lower()

    def test_project_run_missing_command(self, sample_node_project: Path):
        add_project("wftest2", str(sample_node_project))
        step = WorkflowStep(1, "project_run", {"project": "wftest2"}, {})
        result = execute_step(step)
        assert not result.success

    def test_project_open_nonexistent(self):
        step = WorkflowStep(1, "project_open", {"project": "ghost"}, {})
        result = execute_step(step)
        assert not result.success

    def test_project_run_blocked(self, sample_node_project: Path):
        add_project("blocked", str(sample_node_project))
        step = WorkflowStep(
            1, "project_run",
            {"project": "blocked", "command": "format c:"},
            {},
        )
        result = execute_step(step)
        assert not result.success
        assert "Blocked" in result.message


# ── Safety integration ────────────────────────────────────────────────

class TestProjectSafety:
    def test_project_run_destructive_denied(self, sample_node_project: Path):
        add_project("safetychk", str(sample_node_project))
        step = WorkflowStep(
            1, "project_run",
            {"project": "safetychk", "command": "del something.txt"},
            {},
        )
        with patch("scout.workflow.actions.confirm_destructive", return_value=False):
            result = execute_step(step)
        assert not result.success
        assert "Cancelled" in result.message


# ── Invalid project path tests ────────────────────────────────────────

class TestInvalidProjectPaths:
    def test_path_is_file(self, tmp_path: Path):
        f = tmp_path / "afile.txt"
        f.write_text("hi", encoding="utf-8")
        ok, msg = add_project("badpath", str(f))
        assert not ok

    def test_path_with_spaces(self, tmp_path: Path):
        proj = tmp_path / "my project"
        proj.mkdir()
        ok, msg = add_project("spaces", str(proj))
        assert ok
        entry = get_project("spaces")
        assert entry is not None
