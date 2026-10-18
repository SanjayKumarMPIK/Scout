"""Native Windows OCR integration using Windows.Media.Ocr.

Provides fast, zero-latency, completely offline text and UI element detection
using Windows 10/11 built-in WinRT OCR capabilities.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scout.vision.capture import take_screenshot

logger = logging.getLogger(__name__)

_OCR_PS1_PATH = Path(__file__).parent / "windows_ocr.ps1"


@dataclass
class OcrWord:
    text: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OcrLine:
    text: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    words: list[OcrWord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OcrResult:
    success: bool
    text: str = ""
    lines: list[OcrLine] = field(default_factory=list)
    error: str = ""
    image_path: str = ""
    duration_ms: float = 0.0

    def find_element(self, query: str, case_sensitive: bool = False) -> dict[str, Any] | None:
        """Find the best matching UI text element and return its click coordinates.

        Searches lines first, then individual words.

        Returns:
            Dict with center_x, center_y, text, rect, or None if not found.
        """
        if not self.success or not query.strip():
            return None

        q = query.strip() if case_sensitive else query.strip().lower()

        # 1. Exact line match
        for line in self.lines:
            lt = line.text if case_sensitive else line.text.lower()
            if lt == q:
                return {
                    "text": line.text,
                    "center_x": line.center_x,
                    "center_y": line.center_y,
                    "rect": {"x": line.x, "y": line.y, "width": line.width, "height": line.height},
                    "type": "exact_line",
                }

        # 2. Exact word match
        for line in self.lines:
            for word in line.words:
                wt = word.text if case_sensitive else word.text.lower()
                if wt == q:
                    return {
                        "text": word.text,
                        "center_x": word.center_x,
                        "center_y": word.center_y,
                        "rect": {"x": word.x, "y": word.y, "width": word.width, "height": word.height},
                        "type": "exact_word",
                    }

        # 3. Substring in line
        for line in self.lines:
            lt = line.text if case_sensitive else line.text.lower()
            if q in lt:
                # Find the specific matching word if possible for tighter center coordinate
                for word in line.words:
                    wt = word.text if case_sensitive else word.text.lower()
                    if q in wt:
                        return {
                            "text": word.text,
                            "center_x": word.center_x,
                            "center_y": word.center_y,
                            "rect": {"x": word.x, "y": word.y, "width": word.width, "height": word.height},
                            "type": "word_match_in_line",
                        }
                return {
                    "text": line.text,
                    "center_x": line.center_x,
                    "center_y": line.center_y,
                    "rect": {"x": line.x, "y": line.y, "width": line.width, "height": line.height},
                    "type": "substring_line",
                }

        return None

    def find_all(self, query: str, case_sensitive: bool = False) -> list[dict[str, Any]]:
        """Find all matching UI text elements."""
        matches: list[dict[str, Any]] = []
        if not self.success or not query.strip():
            return matches

        q = query.strip() if case_sensitive else query.strip().lower()

        for line in self.lines:
            lt = line.text if case_sensitive else line.text.lower()
            if q in lt:
                matches.append({
                    "text": line.text,
                    "center_x": line.center_x,
                    "center_y": line.center_y,
                    "rect": {"x": line.x, "y": line.y, "width": line.width, "height": line.height},
                })
        return matches

    def to_formatted_text(self, max_lines: int = 50) -> str:
        """Format recognized text and coordinates into clean structured output."""
        if not self.success:
            return f"OCR Failed: {self.error}"
        if not self.lines:
            return "OCR succeeded, but no text was detected on the image/screen."

        parts = [
            f"=== Windows OCR Results ({len(self.lines)} lines detected in {self.duration_ms:.1f}ms) ===",
            "Full Text:",
            self.text,
            "\nDetected Elements with Click Coordinates [X, Y]:",
        ]
        for line in self.lines[:max_lines]:
            parts.append(f"- [{line.center_x}, {line.center_y}] \"{line.text}\" (size: {line.width}x{line.height})")

        if len(self.lines) > max_lines:
            parts.append(f"\n[... and {len(self.lines) - max_lines} more detected lines ...]")

        return "\n".join(parts)


def ocr_image(image_path: str | Path, timeout: float = 12.0) -> OcrResult:
    """Run native Windows.Media.Ocr on an image file.

    Args:
        image_path: Path to the image file (PNG, JPG, BMP).
        timeout: Maximum execution timeout in seconds.

    Returns:
        OcrResult with recognized text, lines, words, and coordinates.
    """
    resolved_path = Path(image_path).resolve()
    if not resolved_path.exists():
        return OcrResult(success=False, error=f"Image file not found: {image_path}", image_path=str(image_path))

    if not _OCR_PS1_PATH.exists():
        return OcrResult(
            success=False,
            error=f"Windows OCR PowerShell script not found at {_OCR_PS1_PATH}",
            image_path=str(resolved_path),
        )

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(_OCR_PS1_PATH),
        "-ImagePath",
        str(resolved_path),
    ]

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
        duration_ms = (time.time() - t0) * 1000.0

        if proc.returncode != 0 and not proc.stdout.strip():
            return OcrResult(
                success=False,
                error=f"PowerShell OCR exited with code {proc.returncode}: {proc.stderr.strip()}",
                image_path=str(resolved_path),
                duration_ms=duration_ms,
            )

        raw_output = proc.stdout.strip()
        if not raw_output:
            return OcrResult(
                success=False,
                error=f"No output returned from OCR script. Stderr: {proc.stderr.strip()}",
                image_path=str(resolved_path),
                duration_ms=duration_ms,
            )

        if "OCR_BASE64:" in raw_output:
            try:
                b64_part = raw_output.split("OCR_BASE64:")[1].strip()
                b64_token = b64_part.split()[0]
                json_bytes = base64.b64decode(b64_token)
                raw_output = json_bytes.decode("utf-8", errors="replace")
            except Exception as dec_err:
                logger.warning(f"Failed to decode base64 OCR payload: {dec_err}")

        try:
            data = json.loads(raw_output, strict=False)
        except json.JSONDecodeError:
            # Clean control characters (except newline, tab) that can break JSON parser
            cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", raw_output)
            data = json.loads(cleaned, strict=False)

        if not data.get("success", False):
            return OcrResult(
                success=False,
                error=data.get("error", "Unknown OCR failure"),
                image_path=str(resolved_path),
                duration_ms=duration_ms,
            )

        lines: list[OcrLine] = []
        for l_data in data.get("lines", []):
            words: list[OcrWord] = []
            for w_data in l_data.get("words", []):
                words.append(
                    OcrWord(
                        text=w_data.get("text") or "",
                        x=int(w_data.get("x") or 0),
                        y=int(w_data.get("y") or 0),
                        width=int(w_data.get("width") or 0),
                        height=int(w_data.get("height") or 0),
                        center_x=int(w_data.get("center_x") or 0),
                        center_y=int(w_data.get("center_y") or 0),
                    )
                )

            lines.append(
                OcrLine(
                    text=l_data.get("text") or "",
                    x=int(l_data.get("x") or 0),
                    y=int(l_data.get("y") or 0),
                    width=int(l_data.get("width") or 0),
                    height=int(l_data.get("height") or 0),
                    center_x=int(l_data.get("center_x") or 0),
                    center_y=int(l_data.get("center_y") or 0),
                    words=words,
                )
            )

        return OcrResult(
            success=True,
            text=data.get("text", "").strip(),
            lines=lines,
            image_path=str(resolved_path),
            duration_ms=duration_ms,
        )

    except subprocess.TimeoutExpired:
        return OcrResult(
            success=False,
            error=f"Windows OCR timed out after {timeout}s",
            image_path=str(resolved_path),
        )
    except json.JSONDecodeError as exc:
        return OcrResult(
            success=False,
            error=f"Failed to parse OCR JSON output: {exc}. Raw: {proc.stdout[:300]}",
            image_path=str(resolved_path),
        )
    except Exception as exc:
        return OcrResult(
            success=False,
            error=f"Unexpected error running Windows OCR: {exc}",
            image_path=str(resolved_path),
        )


def ocr_screen(timeout: float = 12.0) -> OcrResult:
    """Capture the current screen and run native Windows OCR.

    Returns:
        OcrResult with full detected text, bounding boxes, and click coordinates.
    """
    cap = take_screenshot()
    if not cap.get("success"):
        return OcrResult(success=False, error=f"Screen capture failed: {cap.get('error')}")

    img_path = cap["path"]
    return ocr_image(img_path, timeout=timeout)
