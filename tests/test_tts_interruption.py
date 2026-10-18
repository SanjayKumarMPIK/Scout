"""Unit tests for TTS speech interruption, stream abort, and barge-in."""

from __future__ import annotations

import queue
import time
from unittest.mock import MagicMock, patch
import pytest

from scout.voice.tts import is_speaking, stop_speaking, speak
import scout.voice.tts as tts_mod


def test_stop_speaking_aborts_active_stream():
    mock_stream = MagicMock()
    tts_mod._current_stream = mock_stream
    tts_mod._is_speaking = True
    tts_mod._stop_event.clear()

    assert is_speaking() is True

    stop_speaking()

    assert is_speaking() is False
    assert tts_mod._stop_event.is_set() is True
    assert tts_mod._is_speaking is False
    mock_stream.abort.assert_called_once()


def test_stop_speaking_drains_tts_queue():
    tts_mod._tts_queue.put("Sentence 1")
    tts_mod._tts_queue.put("Sentence 2")
    tts_mod._tts_queue.put("Sentence 3")

    assert tts_mod._tts_queue.qsize() == 3

    stop_speaking()

    assert tts_mod._tts_queue.empty() is True


def test_speak_aborts_previous_speech():
    mock_stream = MagicMock()
    tts_mod._current_stream = mock_stream
    tts_mod._is_speaking = True

    with patch("scout.voice.tts.load_config", return_value={"tts": {"enabled": True}}):
        with patch("threading.Thread"):
            speak("New incoming message")

    mock_stream.abort.assert_called_once()
    assert tts_mod._tts_queue.qsize() == 1
    # Clean up
    stop_speaking()


def test_barge_in_disabled_by_default():
    with patch("scout.voice.tts.load_config", return_value={"voice": {}}):
        with patch("threading.Thread") as mock_thread:
            tts_mod._start_voice_barge_in()
            mock_thread.assert_not_called()


def test_barge_in_starts_when_enabled():
    with patch("scout.voice.tts.load_config", return_value={"voice": {"barge_in": True}}):
        with patch("threading.Thread") as mock_thread:
            tts_mod._start_voice_barge_in()
            mock_thread.assert_called_once()
