"""Natural Task Acknowledgment for Scout.

Generates concise, natural, and context-aware task acknowledgments at the
task-submission boundary before planning and execution begins.
Filters out greetings, casual chat, slash commands, and general informational queries.
"""

from __future__ import annotations

import re
import threading
from typing import Optional

# Thread-safe variation tracker for natural responses
_LOCK = threading.Lock()
_VARIATION_COUNTER = 0


def _get_variation(options: list[str]) -> str:
    """Select the next variation from a list in a round-robin thread-safe manner."""
    global _VARIATION_COUNTER
    if not options:
        return ""
    with _LOCK:
        idx = _VARIATION_COUNTER % len(options)
        _VARIATION_COUNTER += 1
        return options[idx]


# ── Non-Actionable Patterns ──────────────────────────────────────────

# Greetings
_RE_GREETINGS = re.compile(
    r"^(\b(hi|hello|hey|hey there|howdy|sup|yo|greetings|good morning|good afternoon|good evening|good day)\b)"
    r"([\s,]+(scout|there|sir|bot|friend|buddy))?[!.,?]*$",
    re.IGNORECASE,
)

# Pleasantries / Acknowledgments from user
_RE_PLEASANTRIES = re.compile(
    r"^(\b(thanks|thank you|thank you so much|thx|appreciate it|awesome|cool|great|nice|perfect|"
    r"sounds good|understood|got it|ok|okay|k|alright|fine|good job|nice job|well done|no problem)\b)[!.,?]*$",
    re.IGNORECASE,
)

# Social / Wellbeing Chit-Chat
_RE_WELLBEING = re.compile(
    r"^(\b(how are you|how are you doing|how is it going|how's it going|what's up|how's your day|how do you feel|how's life)\b)[!.,?]*$",
    re.IGNORECASE,
)

# Identity / Meta / Capability Questions
_RE_IDENTITY = re.compile(
    r"^(\b(who are you|what is your name|who made you|are you an? ai|are you human|what are you|"
    r"tell me about yourself|introduce yourself)\b)[!.,?]*$",
    re.IGNORECASE,
)

_RE_CAPABILITIES = re.compile(
    r"^(\b(what can you do|what are your capabilities|what are your tools|what tools do you have|"
    r"what are you capable of|help me understand what you can do)\b)[!.,?]*$",
    re.IGNORECASE,
)

# Conversational / Creative / Direct talk requests
_RE_CONVERSATIONAL = re.compile(
    r"\b("
    r"(just\s+)?talk(\s+about)?\s+(anything|something|whatever|to me)|"
    r"(can we|let's|lets)\s+(talk|chat)|"
    r"chat with me|speak to me|say something|"
    r"tell\s+(me\s+)?a\s+joke|make\s+me\s+laugh|crack\s+a\s+joke|"
    r"tell\s+(me\s+)?a\s+story|write\s+(me\s+)?a\s+(poem|song|story)|compose\s+a\s+(poem|song)|"
    r"what do you think\s+(about|of)"
    r")\b",
    re.IGNORECASE,
)

# General Knowledge / Explanatory Questions (not requesting computer actions or web lookups)
_RE_GENERAL_KNOWLEDGE = re.compile(
    r"^(why\s+(is|are|do|does|did)|"
    r"what\s+is\s+(the\s+capital|a\s+|an\s+|the\s+meaning|the\s+difference)|"
    r"who\s+(was|is\s+[A-Z])|"
    r"how\s+(does|do)\s+.*work|"
    r"explain\s+|define\s+)",
    re.IGNORECASE,
)

# Computer / Tool triggers that turn a question into an actionable query
_RE_TOOL_TRIGGERS = re.compile(
    r"\b(screen|screenshot|ocr|file|files|folder|download|downloads|desktop|documents|"
    r"browser|search|google|look up|speed|battery|git|window|app|application|program|code|script|terminal|"
    r"email|emails|gmail|inbox|mailbox|phone|android|mobile|adb)\b",
    re.IGNORECASE,
)

# Courtesy prefixes to strip before analyzing action intent
_RE_COURTESY_PREFIXES = re.compile(
    r"^(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+|scout[,\s]+|hey\s+scout[,\s]+|"
    r"i\s+want\s+you\s+to\s+|i\s+need\s+you\s+to\s+|help\s+me\s+|go\s+ahead\s+and\s+|kindly\s+)+",
    re.IGNORECASE,
)


def is_actionable_task(text: str) -> bool:
    """Determine whether the user input is an actionable task that warrants acknowledgment."""
    if not text:
        return False

    raw = text.strip()
    if not raw:
        return False

    # Slash commands are handled directly by command handlers
    if raw.startswith("/"):
        return False

    low = raw.lower()

    # Session exit / control
    if low in {"exit", "quit", "q", ":q", "bye", "goodbye", "cya", "clear", "cls", "stop", "cancel"}:
        return False

    # Filter out greetings, pleasantries, wellbeing, identity, capabilities
    if _RE_GREETINGS.match(raw) or _RE_PLEASANTRIES.match(raw) or _RE_WELLBEING.match(raw):
        return False
    if _RE_IDENTITY.match(raw) or _RE_CAPABILITIES.match(raw):
        return False

    # Filter out pure conversational banter or creative chatting
    if _RE_CONVERSATIONAL.search(raw):
        return False

    # Filter out general knowledge / trivia questions unless they mention computer/tool triggers
    if _RE_GENERAL_KNOWLEDGE.match(raw) and not _RE_TOOL_TRIGGERS.search(raw):
        return False

    # Strip courtesy prefix to find core intent
    core = _RE_COURTESY_PREFIXES.sub("", raw).strip()
    core_low = core.lower()

    # 1. Action verbs at the start of core command
    action_start_prefixes = (
        "open ", "launch ", "start ", "close ", "quit ", "kill ", "minimize ", "maximize ",
        "switch to ", "focus ", "search ", "google ", "look up ", "browse ", "fetch ",
        "find ", "locate ", "list ", "read ", "write ", "create ", "make ", "delete ",
        "remove ", "copy ", "move ", "rename ", "save ", "type ", "press ", "click ",
        "scroll ", "take a screenshot", "capture screen", "check ", "inspect ", "examine ",
        "test ", "verify ", "run ", "execute ", "commit ", "push ", "pull ", "clone ",
        "install ", "download ", "lock ", "unlock ", "turn on ", "turn off ",
    )
    if any(core_low.startswith(p) for p in action_start_prefixes):
        return True

    # 2. Key actionable tool keywords anywhere in the command
    action_keywords = (
        "open notepad", "open chrome", "open browser", "open calculator",
        "search for", "search the web", "look that up", "look up",
        "internet speed", "speedtest", "battery level", "battery status",
        "read the screen", "read screen", "on my screen", "what's on my screen", "what is on my screen",
        "git status", "git commit", "git push", "git pull", "git diff", "git log", "git branch",
        "run command", "run terminal", "run pytest", "run script",
        "files in", "folder", "downloads folder", "desktop folder", "documents folder",
        "read my emails", "read emails", "check my emails", "check emails", "check my inbox", "check inbox", "search emails", "latest emails",
        "from my phone", "from phone", "using my phone", "using phone", "on my phone", "on phone", "with my phone", "with phone", "check my phone",
    )
    if any(kw in low for kw in action_keywords):
        return True

    # 3. If it contains a tool trigger and an imperative verb
    if _RE_TOOL_TRIGGERS.search(low) and any(verb in low for verb in ("get ", "show ", "tell me ", "check ", "find ")):
        return True

    return False


def generate_acknowledgment(text: str) -> Optional[str]:
    """Generate a concise, natural, task-relevant acknowledgment.
    
    Returns None if the input is not an actionable task.
    """
    if not is_actionable_task(text):
        return None

    raw = text.strip()

    # Strip courtesy prefixes while preserving original case for target extraction
    cleaned = _RE_COURTESY_PREFIXES.sub("", raw).strip()
    cleaned_low = cleaned.lower()

    # 1. Open / Launch / Start application
    m_open = re.match(r"^(open|launch|start)\s+(.+)$", cleaned, re.IGNORECASE)
    if m_open:
        action = m_open.group(1).lower()
        target = m_open.group(2).strip().rstrip(".?!")
        words = target.split()
        if len(words) <= 7:
            # Preserve target text casing (e.g., "Notepad and type hello")
            templates = [
                f"Sure, I'll {action} {target} for you.",
                f"Got it. I'll {action} {target} for you.",
                f"Understood. Opening {target} for you." if action == "open" else f"Understood. Launching {target} for you.",
            ]
            return _get_variation(templates)
        else:
            templates = [
                "Understood. I'll open the requested application.",
                "Sure, I'll take care of opening that for you.",
                "Got it. Let me handle that for you.",
            ]
            return _get_variation(templates)

    # 2. Close / Minimize / Quit application
    m_close = re.match(r"^(close|minimize|quit|kill)\s+(.+)$", cleaned, re.IGNORECASE)
    if m_close:
        action = m_close.group(1).lower()
        target = m_close.group(2).strip().rstrip(".?!")
        words = target.split()
        if len(words) <= 5:
            templates = [
                f"Understood, closing {target} for you." if action in ("close", "quit", "kill") else f"Understood, minimizing {target} for you.",
                f"Got it. I'll {action} {target} for you.",
                "Sure, handling that for you.",
            ]
            return _get_variation(templates)
        else:
            templates = [
                "Understood, closing that for you.",
                "Got it, handling that now.",
                "Sure, I'll close the requested window.",
            ]
            return _get_variation(templates)

    # 3. Email / Inbox Operations
    if re.search(r"\b(emails?|gmail|inbox|mailbox)\b", cleaned_low):
        templates = [
            "Sure, I'll check your emails for you.",
            "Got it. Looking through your emails now.",
            "Understood, checking your inbox for you.",
        ]
        return _get_variation(templates)

    # 4. Phone / Mobile / ADB Operations
    if re.search(r"\b(phone|android|mobile|adb)\b", cleaned_low) or "from my phone" in cleaned_low or "using my phone" in cleaned_low:
        templates = [
            "Sure, I'll handle that on your phone using ADB for you.",
            "Got it. Connecting to your phone via ADB now.",
            "Understood, executing that on your phone for you.",
        ]
        return _get_variation(templates)

    # 5. Web Search / Research / Look up
    if re.search(r"\b(search|look\s+up|google|research|browse|fetch|find\s+information)\b", cleaned_low):
        templates = [
            "Sure, I'll look that up for you.",
            "Got it. Let me search that for you.",
            "Understood. I'll search for that right away.",
            "Absolutely, looking that up for you now.",
        ]
        return _get_variation(templates)

    # 4. Screen / Vision / OCR
    if re.search(r"\b(screen|screenshot|ocr|what\'?s\s+on\s+(my\s+)?screen|look\s+at\s+(my\s+)?screen|read\s+(the\s+)?screen)\b", cleaned_low):
        templates = [
            "Sure, let me take a look at your screen.",
            "Got it. Checking your screen now.",
            "Understood, inspecting the screen now.",
        ]
        return _get_variation(templates)

    # 5. File & Folder Operations (find, list, read, inspect)
    if re.search(r"\b(files?|folders?|downloads|desktop|documents|directory)\b", cleaned_low) and re.search(r"\b(list|find|show|read|check|locate|search)\b", cleaned_low):
        templates = [
            "Understood. I'll check the files for you.",
            "Got it. I'll find that for you.",
            "Sure, looking for those files for you.",
        ]
        return _get_variation(templates)

    # 6. System Diagnostics (speed, battery, wifi, system info)
    if re.search(r"\b(speed|speedtest|internet\s+speed|battery|system\s+info|wifi|network|specs|cpu|ram)\b", cleaned_low):
        templates = [
            "Sure, I'll check that for you.",
            "Got it. Checking that now.",
            "Understood. Let me check that for you.",
        ]
        return _get_variation(templates)

    # 7. Git & Development / Execution
    if re.search(r"\b(git\s+(status|commit|push|pull|diff|log|branch)|run|execute|pytest|npm|python)\b", cleaned_low):
        templates = [
            "Got it, running that for you.",
            "Sure, I'll execute that for you.",
            "Understood, I'll take care of running that for you.",
        ]
        return _get_variation(templates)

    # 8. General Actionable Fallback
    templates = [
        "Got it. Let me handle that for you.",
        "Absolutely, I'll take care of that.",
        "Sure, I'll get right on that.",
        "Understood. Let me take care of that for you.",
    ]
    return _get_variation(templates)


def acknowledge_task(request: str, voice_mode: bool = False) -> Optional[str]:
    """Acknowledge an actionable user task before planning and execution begins.
    
    In keyboard mode: displays acknowledgment in the terminal immediately.
    In voice mode: displays acknowledgment AND triggers TTS speech playback asynchronously.
    Returns the acknowledgment text if acknowledged, or None if skipped.
    """
    ack = generate_acknowledgment(request)
    if not ack:
        return None

    try:
        from scout.ui.chat import print_scout_acknowledgment
        print_scout_acknowledgment(ack)
    except Exception:
        pass

    if voice_mode:
        try:
            from scout.voice.tts import speak
            speak(ack)
        except Exception:
            pass

    return ack
