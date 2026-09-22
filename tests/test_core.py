"""Tests for Scout core modules."""

from __future__ import annotations

import pytest

from scout.core.registry import Registry
from scout.core.safety import is_blocked, is_destructive
from scout.parser import parse


# ── Parser tests ───────────────────────────────────────────────────────

class TestParser:
    def test_empty_input(self):
        assert parse("") == ("", [])

    def test_whitespace_only(self):
        assert parse("   ") == ("", [])

    def test_single_command(self):
        assert parse("help") == ("help", [])

    def test_command_with_args(self):
        assert parse("open chrome") == ("open", ["chrome"])

    def test_command_with_multiple_args(self):
        assert parse("run npm run dev") == ("run", ["npm", "run", "dev"])

    def test_case_insensitive(self):
        cmd, args = parse("OPEN Chrome")
        assert cmd == "open"

    def test_leading_trailing_whitespace(self):
        assert parse("  system  ") == ("system", [])


# ── Registry tests ─────────────────────────────────────────────────────

class TestRegistry:
    def test_register_and_get(self):
        reg = Registry()
        handler = lambda args: None  # noqa: E731
        reg.register("test", handler, description="test cmd")
        cmd = reg.get("test")
        assert cmd is not None
        assert cmd.name == "test"
        assert cmd.handler is handler

    def test_alias_lookup(self):
        reg = Registry()
        handler = lambda args: None  # noqa: E731
        reg.register("test", handler, aliases=["t", "tst"])
        assert reg.get("t") is not None
        assert reg.get("tst") is not None
        assert reg.get("t").name == "test"

    def test_unknown_command(self):
        reg = Registry()
        assert reg.get("nonexistent") is None

    def test_all_unique_no_duplicates(self):
        reg = Registry()
        reg.register("alpha", lambda a: None, aliases=["a"])
        reg.register("beta", lambda a: None, aliases=["b"])
        unique = reg.all_unique()
        names = [c.name for c in unique]
        assert names == ["alpha", "beta"]


# ── Safety tests ───────────────────────────────────────────────────────

class TestSafety:
    def test_safe_commands(self):
        assert not is_destructive("echo hello")
        assert not is_destructive("dir")
        assert not is_destructive("python --version")

    def test_destructive_commands(self):
        assert is_destructive("rm -rf /")
        assert is_destructive("del file.txt")
        assert is_destructive("shutdown /s")
        assert is_destructive("taskkill /f /im explorer.exe")

    def test_blocked_commands(self):
        assert is_blocked("format c:")
        assert is_blocked("FORMAT C:")

    def test_non_blocked_commands(self):
        assert not is_blocked("echo hello")
        assert not is_blocked("npm run dev")
