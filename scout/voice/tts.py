"""Text-to-Speech integration using Kokoro ONNX."""

import os
import re
import threading
import queue
import urllib.request
import time
from pathlib import Path

from scout.config import APP_DIR
from scout.user_config import load_config
from rich.console import Console

console = Console()

KOKORO_DIR = APP_DIR / "models" / "kokoro"
MODEL_PATH = KOKORO_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = KOKORO_DIR / "voices-v1.0.bin"

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

_kokoro = None
_tts_queue = queue.Queue()
_speak_thread = None
_stop_event = threading.Event()
_is_initialized = False
_init_lock = threading.Lock()


def _download_file(url: str, path: Path, desc: str, expected_size: int = None) -> bool:
    if path.exists() and path.stat().st_size > 0:
        if expected_size is None or path.stat().st_size == expected_size:
            return True
        else:
            # Partial or corrupted download from a previous interrupted run
            console.print(f"[yellow]Found partial/corrupted file for {desc}. Redownloading...[/yellow]")
            try:
                path.unlink()
            except Exception:
                pass
    
    KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Downloading {desc}... (this only happens once)[/dim]")
    
    try:
        import requests
        from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        with requests.get(url, stream=True, headers=headers, timeout=10) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with Progress(
                TextColumn("[cyan]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(desc, total=total_size)
                
                with open(path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if _stop_event.is_set():
                            raise Exception("Download cancelled by user.")
                        if chunk:
                            file.write(chunk)
                            progress.update(task, advance=len(chunk))
                            
        return True
    except Exception as e:
        console.print(f"[yellow]Failed to download {desc}: {e}[/yellow]")
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        return False


def _init_kokoro():
    global _kokoro, _is_initialized
    with _init_lock:
        if _is_initialized:
            return True
            
        if not _download_file(MODEL_URL, MODEL_PATH, "Kokoro TTS model", expected_size=325532387):
            return False
        if not _download_file(VOICES_URL, VOICES_PATH, "Kokoro TTS voices", expected_size=28214398):
            return False

        try:
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
            _is_initialized = True
            return True
        except Exception as e:
            console.print(f"[yellow]Failed to initialize Kokoro TTS: {e}[/yellow]")
            return False


def _tts_worker():
    import sounddevice as sd
    
    while True:
        text = _tts_queue.get()
        if text is None:
            break
            
        if _stop_event.is_set():
            _tts_queue.task_done()
            continue
            
        config = load_config()
        tts_config = config.get("tts", {})
        if not tts_config.get("enabled", True):
            _tts_queue.task_done()
            continue
            
        voice = tts_config.get("voice", "af_bella")
        speed = float(tts_config.get("speed", 1.0))
        
        if not _init_kokoro():
            _tts_queue.task_done()
            continue
            
        try:
            # Clean up text (remove markdown, code blocks, etc)
            clean_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
            clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)
            clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)
            
            # Remove emojis so the TTS doesn't read out "smiling face with sunglasses"
            try:
                import emoji
                clean_text = emoji.replace_emoji(clean_text, replace='')
            except ImportError:
                pass
            
            # Split into manageable sentences
            sentences = re.split(r'(?<=[.!?\n])\s+', clean_text.strip())
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence or _stop_event.is_set():
                    continue
                    
                # Generate audio
                samples, sample_rate = _kokoro.create(sentence, voice=voice, speed=speed)
                
                if _stop_event.is_set():
                    break
                    
                # Play audio
                sd.play(samples, samplerate=sample_rate)
                
                # Wait for playback to finish or be interrupted
                try:
                    stream = sd.get_stream()
                    while stream and stream.active:
                        if _stop_event.is_set():
                            sd.stop()
                            break
                        time.sleep(0.05)
                except Exception:
                    pass
        except Exception as e:
            console.print(f"\n[yellow]TTS playback error: {e}[/yellow]")
            
        _tts_queue.task_done()


import logging

# Suppress harmless phonemizer warnings (e.g. "words count mismatch")
logging.getLogger("phonemizer").setLevel(logging.ERROR)

def speak(text: str):
    global _speak_thread, _stop_event
    
    config = load_config()
    if not config.get("tts", {}).get("enabled", True):
        return

    # Clear previous queue
    while not _tts_queue.empty():
        try:
            _tts_queue.get_nowait()
            _tts_queue.task_done()
        except queue.Empty:
            break
            
    # Stop current playback
    _stop_event.set()
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
    
    if _speak_thread is None or not _speak_thread.is_alive():
        _stop_event.clear()
        _speak_thread = threading.Thread(target=_tts_worker, daemon=True)
        _speak_thread.start()
        
    _stop_event.clear()
    _tts_queue.put(text)


def stop_speaking():
    _stop_event.set()
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
