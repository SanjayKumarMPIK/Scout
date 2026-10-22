"""The Planner agent, responsible for high-level reasoning and generating an execution plan."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from scout.ai.provider import AIProvider

console = Console()

# Tools the executor uses internally; never assigned by the planner.
_INTERNAL_TOOLS = {"complete_task", "step_done", "step_failed"}


@dataclass
class PlanStep:
    description: str
    tools: list[str] = field(default_factory=list)


@dataclass
class Plan:
    mode: str  # "execute" | "respond"
    steps: list[PlanStep] = field(default_factory=list)
    response: str = ""


PLANNER_PROMPT = """You are Scout Planner, the reasoning engine of a Windows computer-automation agent.
Decide HOW each user request is handled and write the exact plan the executor will follow.
The executor runs your steps literally, ONE AT A TIME, in order, using ONLY tools assigned to each step.

Reply by calling `submit_plan` exactly once:
- mode="respond": direct answer (greetings, general Q&A, capabilities). Put full text in `response`, leave `steps` empty.
- mode="execute": action requests. Provide ordered `steps`, leave `response` empty.

# TONE & PERSONALITY (STRICT):
1. PERSONALITY: You are a VERY friendly, chill agent with a fun vibe and cool slang. Address the user respectfully as "sir" naturally within your responses.
2. NO OPENING GREETING PREFIXES: NEVER start responses with opening greetings like "Yo", "Yo sir", "Hey", "Hello", or filler greeting prefixes unless the user greeted you first.
3. GREET ONLY WHEN GREETED: If the user explicitly greets you (e.g. "hi", "hello", "hey", "good morning"), greet them back warmly and naturally, addressing them as "sir".
4. DIRECT ANSWERS: For all questions, compliments, or commands, dive STRAIGHT into the answer or action without opening greetings or throat-clearing. Keep your fun vibe, slang, and address the user as "sir" naturally within the body of your answer.
YOU HAVE A VOICE COMMAND TOOL, IF A USER ASKS ABOUT IT, YOU MUST REPLY POSITIVELY ABOUT THE VOICE COMMANDS. THE COMMAND TO ENABLE VOICE IS "/voice".

# Multi-Turn Rules
1. Never repeat or re-plan completed tasks from chat history unless explicitly requested ("run again", "retry").
2. Answer capability questions directly with mode="respond".

# System Paths
{system_paths}

# Executor Tools
{tool_reference}

# Web Research Policy
1. Tool hierarchy: `web_search` for queries -> `fetch_webpage` for reading pages -> `browser_navigate` only when JavaScript/interactions required. Close browser with `browser_close` when done.
2. For specific figures/stipends/tables: `web_search` first, then `fetch_webpage` on top candidate URLs. Include source titles and URLs.

# Mobile ADB Policy (Zero Refusal)
- If user mentions "phone", "Android", or mobile: NEVER refuse or claim lack of access. Formulate an `execute` plan using `adb_command`.
- Examples: Battery: `shell dumpsys battery` | Launch app: `shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1` | URL: `shell am start -a android.intent.action.VIEW -d '<url>'` | Keys: `shell input keyevent <code: 26=power, 3=home, 4=back>` | Tap: `shell input tap <x> <y>` | Text: `shell input text '<str>'` | Screen: `shell screencap -p /sdcard/s.png`

# Step Rules
1. One step = one concrete action with exact parameters. `tools` = exact tool names allowed.
2. No final "report" step (reporting is automatic). Windows only: `run_command` uses PowerShell.
3. Prefer headless tools (`read_file`, `search_file`, `write_file`, `run_command`) over UI clicks for data/files.
4. For reading screen text/buttons, prefer `ocr_read_screen` or `ocr_find_element` over heavy vision. Never use destructive keys (`Ctrl+A`, `Delete`) to inspect state.
5. NEVER instruct the user to perform tasks manually; automate them yourself.
"""


def _build_tool_reference() -> str:
    """Describe the executor's real tools compactly so the plan always matches what exists."""
    from scout.ai.tools import get_tools

    lines = []
    for schema in get_tools():
        fn = schema["function"]
        if fn["name"] in _INTERNAL_TOOLS:
            continue
        props = fn.get("parameters", {}).get("properties", {})
        required = set(fn.get("parameters", {}).get("required", []))
        params = [p if p in required else f"[{p}]" for p in props.keys()]
        desc = fn.get("description", "").split(".")[0].strip()
        lines.append(f"- `{fn['name']}({', '.join(params)})`: {desc}")
    return "\n".join(lines)


def _valid_tool_names() -> set[str]:
    from scout.ai.tools import get_tools

    return {t["function"]["name"] for t in get_tools()} - _INTERNAL_TOOLS


def get_planner_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "submit_plan",
                "description": "Submit how the request will be handled: a direct response, or a step-by-step plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["execute", "respond"],
                            "description": "'respond' to answer directly without actions, 'execute' to run steps.",
                        },
                        "response": {
                            "type": "string",
                            "description": "The full answer to the user (mode='respond' only).",
                        },
                        "steps": {
                            "type": "array",
                            "description": "Ordered steps for the executor (mode='execute' only).",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {
                                        "type": "string",
                                        "description": "One specific, self-contained action with concrete values.",
                                    },
                                    "tools": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Exact executor tool name(s) allowed for this step.",
                                    },
                                },
                                "required": ["description", "tools"],
                            },
                        },
                    },
                    "required": ["mode"],
                },
            },
        }
    ]


class Planner:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    # ── Public API ─────────────────────────────────────────────────────

    def generate_plan(self, request: str, memory_context: str = "", chat_history: list[dict] | None = None) -> Plan | None:
        """Plan how to handle the user's request. Returns None on hard failure."""
        return self._request_plan(request, request, memory_context, chat_history=chat_history)

    def revise_plan(
        self,
        request: str,
        history: list[tuple[PlanStep, str, str]],
        remaining: list[PlanStep],
        memory_context: str = "",
        chat_history: list[dict] | None = None,
    ) -> Plan | None:
        """Re-plan after a step failed.

        ``history`` holds (step, status, result) for every step attempted so far.
        """
        lines = [f"ORIGINAL USER REQUEST:\n{request}\n", "PROGRESS SO FAR:"]
        for i, (step, status, result) in enumerate(history, 1):
            lines.append(f"{i}. [{status.upper()}] {step.description}\n   Result: {result}")
        if remaining:
            lines.append("\nSTEPS NOT YET RUN (from the previous plan):")
            lines.extend(f"- {s.description}" for s in remaining)
        lines.append(
            "\nThe last step FAILED. Submit a revised plan containing ONLY the steps still needed to finish the "
            "request (do not repeat completed steps). Use a different approach for the failed part. If the request "
            "cannot be completed with the available tools, use mode='respond' and explain why."
        )
        return self._request_plan("\n".join(lines), request, memory_context, status_text="Planner is revising the plan...", chat_history=chat_history)

    # ── Internals ──────────────────────────────────────────────────────

    def _request_plan(
        self,
        prompt: str,
        memory_query: str,
        memory_context: str,
        status_text: str | None = None,
        chat_history: list[dict] | None = None,
    ) -> Plan | None:
        from scout.memory.store import get_memory_store

        mem_block = get_memory_store().get_relevant_memories(memory_query)

        user_home = Path.home()
        system_paths = (
            f"- User Profile: {user_home}\n"
            f"- Downloads Folder: {user_home / 'Downloads'}\n"
            f"- Desktop Folder: {user_home / 'Desktop'}\n"
            f"- Documents Folder: {user_home / 'Documents'}\n"
            "ALWAYS use these exact paths when the user asks for files in Downloads, Desktop, or Documents. NEVER guess usernames."
        )
        system_prompt = PLANNER_PROMPT.replace("{tool_reference}", _build_tool_reference()).replace("{system_paths}", system_paths)
        if memory_context:
            system_prompt += f"\n\n# User Profile & Preferences\n{memory_context}"

        user_content = f"{mem_block}\n\nUSER REQUEST:\n{prompt}" if mem_block else prompt
        
        messages: list[dict] = []
        if chat_history:
            messages.extend(chat_history)
        
        messages.append({"role": "user", "content": user_content})
        
        tools = get_planner_tools()
        status_text = status_text or f"Planner ({self.provider.__class__.__name__}) is generating the plan..."

        last_text = ""
        try:
            for attempt in range(2):
                with console.status(f"[dim]{status_text}[/dim]"):
                    response = self.provider.chat_completion(system_prompt, messages, tools)
                message = response.get("choices", [{}])[0].get("message", {}) or {}

                plan = self._parse_tool_call(message)
                if plan:
                    return plan

                last_text = (message.get("content") or "").strip()
                plan = self._parse_json_text(last_text)
                if plan:
                    return plan

                if attempt == 0:
                    # One corrective retry: the model must use submit_plan.
                    messages.append({"role": "assistant", "content": last_text or "(no output)"})
                    messages.append({
                        "role": "user",
                        "content": "You did not call `submit_plan`. Call `submit_plan` now with either "
                                   "mode='respond' (and the full answer) or mode='execute' (and the steps).",
                    })
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Planner failed:[/] {escape(str(e))}")
            return None

        return self._parse_plain_text(last_text)

    def _parse_tool_call(self, message: dict) -> Plan | None:
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            if fn.get("name") != "submit_plan":
                continue
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            plan = self._plan_from_dict(args)
            if plan:
                return plan
        return None

    def _parse_json_text(self, text: str) -> Plan | None:
        """Some models write the submit_plan arguments as JSON text instead of a tool call."""
        if "{" not in text:
            return None
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict) and isinstance(data.get("arguments"), dict):
            data = data["arguments"]
        if isinstance(data, dict) and isinstance(data.get("parameters"), dict):
            data = data["parameters"]
        return self._plan_from_dict(data) if isinstance(data, dict) else None

    def _parse_plain_text(self, text: str) -> Plan | None:
        """Last resort: a numbered list becomes steps; anything else is a direct answer."""
        if not text:
            console.print("[red]Planner returned an empty response.[/]")
            return None
        numbered = re.findall(r"^\s*\d+[.)]\s+(.+)$", text, flags=re.MULTILINE)
        if len(numbered) >= 2:
            return Plan(mode="execute", steps=[PlanStep(s.strip()) for s in numbered])
        return Plan(mode="respond", response=text)

    def _plan_from_dict(self, data: dict) -> Plan | None:
        if not any(k in data for k in ("mode", "steps", "response")):
            return None

        valid = _valid_tool_names()
        steps: list[PlanStep] = []
        for raw in data.get("steps") or []:
            if isinstance(raw, str):
                desc, tools = raw, []
            elif isinstance(raw, dict):
                desc = str(raw.get("description") or raw.get("step") or "").strip()
                tools = raw.get("tools") or raw.get("tool") or []
                if isinstance(tools, str):
                    tools = [tools]
            else:
                continue
            if not desc.strip():
                continue
            # Drop unknown tool names; an empty list means "any tool" for that step.
            steps.append(PlanStep(desc.strip(), [t for t in tools if t in valid]))

        response = str(data.get("response") or "").strip()
        mode = data.get("mode")
        if mode not in ("execute", "respond"):
            mode = "execute" if steps else "respond"
        if mode == "execute" and not steps:
            mode = "respond"
        if mode == "respond" and not response:
            if steps:
                mode = "execute"
            else:
                return None
        return Plan(mode=mode, steps=steps if mode == "execute" else [], response=response)
