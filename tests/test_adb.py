"""Tests for Android ADB mobile device automation."""

from unittest.mock import MagicMock, patch
import pytest

from scout.ai.tools import execute_tool, tool_adb_command
from scout.ai.acknowledgment import is_actionable_task, generate_acknowledgment


class TestAdbTool:
    """Test the adb_command tool execution and argument handling."""

    @patch("subprocess.run")
    @patch("shutil.which", return_value="C:\\platform-tools\\adb.exe")
    def test_adb_command_strips_prefix_and_executes(self, mock_which, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "List of devices attached\n192.168.0.104:45475 device"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        # Call with "adb devices"
        result = execute_tool("adb_command", {"command": "adb devices"})
        assert result.success is True
        assert "192.168.0.104:45475" in result.message
        # Verify it stripped "adb " and didn't duplicate it
        called_args = mock_run.call_args[0][0]
        assert called_args == ["C:\\platform-tools\\adb.exe", "devices"]

    @patch("subprocess.run")
    @patch("shutil.which", return_value="C:\\platform-tools\\adb.exe")
    def test_adb_command_with_device_id(self, mock_which, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "level: 85"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        result = execute_tool("adb_command", {
            "command": "shell dumpsys battery",
            "device_id": "emulator-5554"
        })
        assert result.success is True
        assert "level: 85" in result.message

        called_args = mock_run.call_args[0][0]
        assert called_args == ["C:\\platform-tools\\adb.exe", "-s", "emulator-5554", "shell", "dumpsys", "battery"]

    @patch("subprocess.run")
    @patch("shutil.which", return_value="C:\\platform-tools\\adb.exe")
    def test_adb_command_failure_reporting(self, mock_which, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "error: device unauthorized."
        mock_run.return_value = mock_proc

        result = execute_tool("adb_command", {"command": "shell input tap 100 200"})
        assert result.success is False
        assert "device unauthorized" in result.message


class TestPhoneTaskAcknowledgment:
    """Test that phone requests are recognized and acknowledged appropriately."""

    @pytest.mark.parametrize("query", [
        "Open WhatsApp from my phone",
        "Check battery level using my phone",
        "Take a photo from my phone",
        "Unlock my phone",
        "Lock my phone",
        "Turn on flashlight on my phone",
        "Open YouTube using my phone",
    ])
    def test_phone_phrasing_is_actionable(self, query: str):
        assert is_actionable_task(query) is True

    @pytest.mark.parametrize("query", [
        "Open WhatsApp from my phone",
        "Check battery level using my phone",
    ])
    def test_phone_acknowledgment_generated(self, query: str):
        ack = generate_acknowledgment(query)
        assert ack is not None
        assert any(word in ack.lower() for word in ("phone", "adb"))
