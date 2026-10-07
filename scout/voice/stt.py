"""Speech-to-Text module using Groq Whisper API."""

import os
import queue
import tempfile
import threading
from typing import Optional

import requests
import sounddevice as sd
import soundfile as sf
from rich.console import Console

from scout.core.auth import get_api_key

console = Console()

_COMMON_PROMPT = "Scout, Python, PowerShell, Windows, VS Code, GitHub, Groq, Ollama, Qwen, OpenClaw, Chrome, Notepad, terminal, Git, npm"


def record_until_enter() -> Optional[str]:
    """Record audio from the default microphone until the user presses Enter.
    Returns the path to the temporary WAV file, or None if failed.
    """
    q = queue.Queue()

    def callback(indata, frames, time, status):
        if status:
            console.print(f"[yellow]Microphone warning:[/] {status}")
        q.put(indata.copy())

    try:
        sd.check_input_settings()
    except Exception as e:
        console.print(f"\n[red]Microphone error:[/] {e}")
        console.print("[dim]Make sure your microphone is connected and permissions are granted.[/dim]")
        return None

    samplerate = 16000
    channels = 1
    
    # Create temp file
    fd, filename = tempfile.mkstemp(suffix=".wav")
    os.close(fd)  # Close the low-level handle so sf.SoundFile can open it

    console.print("🎙️ [bold red]Listening...[/bold red] [dim](Press Enter to stop)[/dim]", end="")

    try:
        with sf.SoundFile(filename, mode='w', samplerate=samplerate, channels=channels) as file:
            with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
                # Wait for user to press Enter to stop recording
                try:
                    input()
                except (KeyboardInterrupt, EOFError):
                    pass
                
            # Flush remaining audio
            while not q.empty():
                file.write(q.get())
                
        return filename
    except Exception as e:
        console.print(f"\n[red]Recording error:[/] {e}")
        if os.path.exists(filename):
            os.remove(filename)
        return None


def transcribe_audio() -> Optional[str]:
    """Record audio and transcribe it using Groq API or local model.
    Returns the transcribed text, or None if failed.
    """
    from scout.user_config import load_config
    config = load_config()
    provider = config.get("voice", {}).get("provider", "groq")

    if provider == "groq":
        api_key = get_api_key("groq")
        if not api_key:
            console.print("\n[red]Error: Groq API key not found.[/red]")
            console.print("[dim]Voice mode uses Groq's Whisper API. Set your key with: /provider key groq[/dim]")
            return None

    # 1. Record audio
    filename = record_until_enter()
    if not filename:
        return None

    # Check if file is empty
    if os.path.getsize(filename) < 100:
        console.print("\n[yellow]Recording was empty or too short.[/yellow]")
        os.remove(filename)
        return None

    # 2. Transcribe
    if provider == "local":
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            console.print("\n[red]faster-whisper is not installed.[/red]")
            console.print("[dim]Please run: pip install faster-whisper[/dim]")
            os.remove(filename)
            return None
            
        with console.status("🎙️ [cyan]Transcribing locally...[/cyan]"):
            try:
                global _local_model
                if '_local_model' not in globals():
                    console.print("\n[dim]Loading local Whisper model (this takes a moment)...[/dim]")
                    _local_model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
                    
                segments, info = _local_model.transcribe(filename, beam_size=5)
                text = " ".join([segment.text for segment in segments]).strip()
                
                if not text:
                    console.print("\n[yellow]Could not hear anything clearly.[/yellow]")
                    return None
                return text
            except Exception as e:
                console.print(f"\n[red]Local transcription error:[/] {e}")
                return None
            finally:
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except Exception:
                        pass
    else:
        # Groq
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "whisper-large-v3-turbo",
            "response_format": "json",
            "prompt": _COMMON_PROMPT
        }
    
        try:
            with console.status("🎙️ [cyan]Transcribing (Groq)...[/cyan]"):
                with open(filename, "rb") as f:
                    files = {"file": (os.path.basename(filename), f, "audio/wav")}
                    response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                    
                response.raise_for_status()
                text = response.json().get("text", "").strip()
                
                if not text:
                    console.print("\n[yellow]Could not hear anything clearly.[/yellow]")
                    return None
                    
                return text
                
        except requests.exceptions.RequestException as e:
            console.print(f"\n[red]Groq STT API Error:[/] {e}")
            try:
                if e.response is not None:
                    console.print(f"[dim]{e.response.json()}[/dim]")
            except Exception:
                pass
            return None
        except Exception as e:
            console.print(f"\n[red]Transcription error:[/] {e}")
            return None
        finally:
            # Cleanup temp file
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except Exception:
                    pass
