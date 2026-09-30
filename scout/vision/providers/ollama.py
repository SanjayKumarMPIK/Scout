"""Ollama-based vision provider."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from scout.vision.provider import VisionProvider


class OllamaVisionProvider(VisionProvider):
    """Vision provider using a local Ollama multimodal model."""

    def __init__(self, model: str = "qwen2.5-vl:3b"):
        super().__init__("ollama_vision", model)
        self.endpoint = "http://localhost:11434/api/generate"

    def analyze(self, image_path: str, instruction: str) -> dict:
        """Send an image + instruction to the Ollama vision model."""
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return {"success": False, "observation": f"Failed to read image: {e}", "raw": ""}

        payload = {
            "model": self.model,
            "prompt": instruction,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 300,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
                text = body.get("response", "").strip()
                return {
                    "success": True,
                    "observation": text,
                    "raw": text,
                }
        except urllib.error.URLError as e:
            return {"success": False, "observation": f"Ollama not reachable: {e.reason}", "raw": ""}
        except Exception as e:
            return {"success": False, "observation": f"Vision analysis failed: {e}", "raw": ""}

    def test_connection(self) -> tuple[bool, str]:
        """Test if the Ollama vision model is available."""
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in body.get("models", [])]
                
                # Check if the configured vision model is installed
                model_base = self.model.split(":")[0]
                found = any(model_base in m for m in models)
                
                if found:
                    return True, f"Ollama vision model '{self.model}' is available"
                else:
                    available = ", ".join(models[:5]) if models else "none"
                    return False, (
                        f"Vision model '{self.model}' not found. "
                        f"Available models: {available}. "
                        f"Install it with: ollama pull {self.model}"
                    )
        except urllib.error.URLError:
            return False, "Ollama is not running. Start it with: ollama serve"
        except Exception as e:
            return False, f"Error checking Ollama: {e}"
