"""Tests for Natural Task Acknowledgment."""

from unittest.mock import patch, MagicMock
import pytest

from scout.ai.acknowledgment import (
    is_actionable_task,
    generate_acknowledgment,
    acknowledge_task,
)


class TestIsActionableTask:
    """Test task classification: distinguishing actionable tasks from greetings and chatter."""

    @pytest.mark.parametrize("task", [
        "Open Notepad and type hello.",
        "open chrome",
        "launch Spotify",
        "close notepad",
        "minimize the active window",
        "Can you search and list top internships that i can apply to. Location should be remote, stipend details should be mentioned and the domain is, software. AI Engineer, full stack developer, frontend developer, backend developer, etc",
        "In the downloads folder, there is a html file called exam format. Search for 'Natural Resource Management' in that file and retrieve all details",
        "check my internet speed",
        "what is on my screen",
        "read the screen",
        "take a screenshot",
        "run git status",
        "git commit -m 'update feature'",
        "type 'hello world' into the text box",
        "click the submit button",
        "find files in downloads",
        "list all files on desktop",
        "create a directory called projects",
        "delete temp.txt",
        "check battery percentage",
        "Please open calculator and calculate 50 * 20",
        "Could you search the web for latest AI news?",
        "Help me find the document report.pdf",
    ])
    def test_actionable_tasks_identified(self, task: str):
        assert is_actionable_task(task) is True

    @pytest.mark.parametrize("non_task", [
        # Pure greetings
        "hi",
        "hello",
        "hello scout",
        "hey",
        "hey there",
        "hey scout",
        "good morning",
        "good evening",
        "howdy",
        "yo scout",
        # Wellbeing / social questions
        "how are you?",
        "how are you doing",
        "how's it going",
        "what's up",
        "how do you feel today?",
        # Identity / meta
        "who are you",
        "what is your name?",
        "who made you",
        "are you an ai?",
        "tell me about yourself",
        # Capabilities
        "what can you do?",
        "what are your capabilities",
        "what tools do you have",
        "what are you capable of?",
        # Conversational banter & direct talk requests
        "just talk anything",
        "talk to me",
        "chat with me",
        "say something interesting",
        "can we talk?",
        "tell me a joke",
        "make me laugh",
        "tell me a story about space",
        "write a poem about flowers",
        "what do you think about music?",
        # General knowledge / trivia without tool requests
        "why is the sky blue?",
        "what is the capital of France?",
        "what is 2 + 2?",
        "explain quantum computing",
        "who was Albert Einstein?",
        "how does an airplane fly?",
        # Pleasantries / Gratitude
        "thanks!",
        "thank you so much",
        "awesome",
        "cool",
        "great job",
        "good job Scout",
        "ok",
        "understood",
        # Slash & exit commands
        "/voice on",
        "/help",
        "/memory",
        "exit",
        "quit",
        "bye",
        "",
        "   ",
    ])
    def test_non_actionable_inputs_filtered(self, non_task: str):
        assert is_actionable_task(non_task) is False


class TestGenerateAcknowledgment:
    """Test concise, natural phrasing generation."""

    def test_open_notepad_and_type_hello(self):
        ack = generate_acknowledgment("Open Notepad and type hello.")
        assert ack is not None
        assert "open Notepad and type hello" in ack or "open" in ack.lower()
        # Verify it expresses future/in-progress intent rather than claiming false completion
        assert "for you" in ack or "opening" in ack.lower() or "handle" in ack.lower()

    def test_concise_on_long_research_request(self):
        long_request = (
            "Can you search and list top internships that i can apply to. "
            "Location should be remote, stipend details should be mentioned and "
            "the domain is, software. AI Engineer, full stack developer, frontend developer, backend developer, etc"
        )
        ack = generate_acknowledgment(long_request)
        assert ack is not None
        # Must be concise and relevant, NOT repeating the entire multi-line prompt
        assert len(ack.split()) <= 12
        assert any(term in ack.lower() for term in ("search", "look", "handle", "take care"))

    def test_system_check_acknowledgment(self):
        ack = generate_acknowledgment("check my internet speed")
        assert ack is not None
        assert any(term in ack.lower() for term in ("check", "handle", "take care"))

    def test_screen_acknowledgment(self):
        ack = generate_acknowledgment("what is on my screen")
        assert ack is not None
        assert any(term in ack.lower() for term in ("screen", "take a look", "check", "inspect"))

    def test_git_acknowledgment(self):
        ack = generate_acknowledgment("run git status")
        assert ack is not None
        assert any(term in ack.lower() for term in ("run", "execute", "take care", "handle"))

    def test_file_acknowledgment(self):
        ack = generate_acknowledgment("find files in downloads folder")
        assert ack is not None
        assert any(term in ack.lower() for term in ("file", "find", "check", "handle"))

    def test_no_acknowledgment_for_greetings(self):
        assert generate_acknowledgment("hi") is None
        assert generate_acknowledgment("hello scout") is None
        assert generate_acknowledgment("how are you?") is None
        assert generate_acknowledgment("just talk anything") is None
        assert generate_acknowledgment("tell me a joke") is None
        assert generate_acknowledgment("/voice") is None


class TestAcknowledgeTaskWorkflow:
    """Test acknowledgment execution across Voice and Keyboard modes."""

    @patch("scout.ui.chat.print_scout_acknowledgment")
    @patch("scout.voice.tts.speak")
    def test_keyboard_mode_acknowledges_visually_only(self, mock_speak, mock_print):
        ack = acknowledge_task("Open Notepad and type hello.", voice_mode=False)
        assert ack is not None
        mock_print.assert_called_once_with(ack)
        mock_speak.assert_not_called()

    @patch("scout.ui.chat.print_scout_acknowledgment")
    @patch("scout.voice.tts.speak")
    def test_voice_mode_acknowledges_both_visually_and_audibly(self, mock_speak, mock_print):
        ack = acknowledge_task("Open Notepad and type hello.", voice_mode=True)
        assert ack is not None
        mock_print.assert_called_once_with(ack)
        mock_speak.assert_called_once_with(ack)

    @patch("scout.ui.chat.print_scout_acknowledgment")
    @patch("scout.voice.tts.speak")
    def test_greeting_suppresses_acknowledgment_in_both_modes(self, mock_speak, mock_print):
        # Keyboard mode
        ack_kb = acknowledge_task("hello scout", voice_mode=False)
        assert ack_kb is None
        mock_print.assert_not_called()
        mock_speak.assert_not_called()

        # Voice mode
        ack_voice = acknowledge_task("just talk anything", voice_mode=True)
        assert ack_voice is None
        mock_print.assert_not_called()
        mock_speak.assert_not_called()
