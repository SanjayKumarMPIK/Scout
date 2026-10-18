"""Tests for Native Windows OCR and UI text detection."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw
import pytest

from scout.vision.ocr import (
    OcrLine,
    OcrResult,
    OcrWord,
    ocr_image,
)


def test_ocr_data_structures():
    word1 = OcrWord(text="Submit", x=100, y=200, width=50, height=20, center_x=125, center_y=210)
    word2 = OcrWord(text="Now", x=155, y=200, width=30, height=20, center_x=170, center_y=210)
    line1 = OcrLine(
        text="Submit Now",
        x=100,
        y=200,
        width=85,
        height=20,
        center_x=142,
        center_y=210,
        words=[word1, word2],
    )

    line2 = OcrLine(
        text="Cancel",
        x=200,
        y=200,
        width=40,
        height=20,
        center_x=220,
        center_y=210,
        words=[OcrWord(text="Cancel", x=200, y=200, width=40, height=20, center_x=220, center_y=210)],
    )

    res = OcrResult(success=True, text="Submit Now\nCancel", lines=[line1, line2], duration_ms=45.0)

    # Exact line match
    elem_exact = res.find_element("Submit Now")
    assert elem_exact is not None
    assert elem_exact["center_x"] == 142
    assert elem_exact["center_y"] == 210

    # Word match
    elem_word = res.find_element("Submit")
    assert elem_word is not None
    assert elem_word["center_x"] == 125
    assert elem_word["center_y"] == 210

    # Case insensitive
    elem_case = res.find_element("cancel")
    assert elem_case is not None
    assert elem_case["center_x"] == 220

    # Nonexistent
    assert res.find_element("Missing Button") is None

    # Formatted text
    formatted = res.to_formatted_text()
    assert "Submit Now" in formatted
    assert "[142, 210]" in formatted


def test_ocr_image_missing_file():
    res = ocr_image("nonexistent_path_test_9876.png")
    assert res.success is False
    assert "not found" in res.error.lower()


def test_ocr_image_real_rendering(tmp_path: Path):
    test_img = tmp_path / "test_ui.png"
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 30), "Save Project", fill=(0, 0, 0))
    draw.text((30, 110), "Submit", fill=(0, 0, 0))
    draw.text((30, 190), "Status: Online", fill=(0, 0, 0))
    img.save(str(test_img))

    res = ocr_image(test_img)
    assert res.success is True
    assert len(res.lines) >= 1

    # Should locate "Submit"
    submit_elem = res.find_element("Submit")
    assert submit_elem is not None
    assert submit_elem["center_x"] > 0
    assert submit_elem["center_y"] > 0

    # Should locate "Project"
    project_elem = res.find_element("Project")
    assert project_elem is not None
    assert project_elem["center_x"] > 0
    assert project_elem["center_y"] > 0


def test_tool_ocr_find_element(tmp_path: Path):
    from scout.ai.tools import execute_tool

    test_img = tmp_path / "button_ui.png"
    img = Image.new("RGB", (500, 250), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 50), "Confirm Order", fill=(0, 0, 0))
    img.save(str(test_img))

    # Existing element
    res = execute_tool("ocr_find_element", {"text": "Confirm", "image_path": str(test_img)})
    assert res.success is True
    assert "center coordinates" in res.message
    assert "computer(action='click'" in res.message

    # Missing element
    res_missing = execute_tool("ocr_find_element", {"text": "Cancel Order", "image_path": str(test_img)})
    assert res_missing.success is False
    assert "not found" in res_missing.message


def test_tool_ocr_read_screen(tmp_path: Path):
    from scout.ai.tools import execute_tool

    test_img = tmp_path / "dialog_ui.png"
    img = Image.new("RGB", (500, 250), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 50), "Dialog Message", fill=(0, 0, 0))
    img.save(str(test_img))

    res = execute_tool("ocr_read_screen", {"image_path": str(test_img)})
    assert res.success is True
    assert "Windows OCR Results" in res.message


def test_ocr_tools_safety_classification():
    from scout.ai.interpreter import _get_risk_level

    assert _get_risk_level("ocr_read_screen") == "SAFE"
    assert _get_risk_level("ocr_find_element") == "SAFE"


def test_ocr_handles_control_characters_in_json(monkeypatch, tmp_path: Path):
    from unittest.mock import MagicMock
    import scout.vision.ocr as ocr_mod

    test_img = tmp_path / "dummy.png"
    test_img.write_bytes(b"\x89PNG\r\n\x1a\n")

    # Mock raw output containing unescaped newlines/tabs inside a JSON string
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    # Raw JSON with literal unescaped control characters
    mock_proc.stdout = (
        '{"success": true, "text": "Line1\nLine2\tTabbed", "lines": [{"text": "Line1\nLine2", "words": []}]}'
    )

    monkeypatch.setattr(ocr_mod.subprocess, "run", lambda *args, **kwargs: mock_proc)

    res = ocr_mod.ocr_image(test_img)
    assert res.success is True
    assert "Line1" in res.text
    assert len(res.lines) == 1
