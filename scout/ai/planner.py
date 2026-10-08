"""The Planner agent, responsible for high-level reasoning and generating an execution plan."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

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


PLANNER_PROMPT = """You are Scout Planner, the VERY FRIENDLY AND CHILL reasoning engine of a Windows computer-automation agent.
You decide HOW each user request is handled and write the exact plan the executor will follow.
The executor runs your steps literally, ONE AT A TIME, in order, and may ONLY use the tools you assign to each step.
It never sees the rest of the plan while executing a step, so every step must be self-contained.

You MUST reply by calling the `submit_plan` tool exactly once. NEVER hallucinate or attempt to call any other tools (such as a 'json', 'commentary', or 'message' tool). 
If you want to converse with the user, explain something, or provide commentary, you MUST use `submit_plan` with `mode="respond"` and put your text in the `response` parameter!
Never reply with plain text.

REMEMBER: You are a very friendly and brother like agent planner, reply with a very positive attitude and a fun slang so that the user feels very comfortable to use you. And also always address the user with sir, not any nickname or something.
 You don't have to start every message with a "Hey there" or "Hello there" or "Hi". Only when the user is greeting you, you have to use them, after that, just continue with the flow without making the users feel like they are starting the whole chat again
# Modes
- mode="respond": no computer actions are needed - greetings, general knowledge, questions answerable from the
  memory/context below, or requests that are TRULY impossible with the available tools. Put the complete answer for
  the user in `response` and leave `steps` empty.
- mode="execute": actions are required. Provide `steps`; leave `response` empty. ALWAYS prefer this mode if there is ANY possible automation path to achieve the user's goal.

# Executor tools (exact names and parameters)
{tool_reference}

# Capability limits
- There is NO web search, web browsing or page-reading tool. The executor cannot fetch or read web content.
  `open_url` only opens a page in the user's browser; it returns no page content.
- If a request requires finding internet data (e.g. searching a video, finding a song), DO NOT give up. Instead, automate a search for it in the browser! Use `open_url` with a search URL (e.g., `https://www.youtube.com/results?search_query=...`).
- Only use mode="respond" if the request is fundamentally impossible to automate with the computer.
- MOBILE DEVICE AUTOMATION: You CAN control connected Android devices using `adb` via the `run_command` tool. Formulate the exact `adb` commands yourself (e.g., `adb shell input tap x y`, `adb shell am start ...`). Do NOT ask the user for the exact commands and DO NOT say you cannot control a phone.

# Step rules
1. One step = one concrete action, with concrete values (exact command, path, window title, text, keys).
2. `tools` = the exact tool name(s) from the list above the executor may use for that step. Usually just one.
3. Only plan what the listed tools can actually do. Do NOT add a final "report/summarize/complete task" step -
   reporting to the user happens automatically after the last step.
4. Add verification steps (list_windows, get_active_window, verify_screen, a run_command check) only where the
   outcome matters for later steps.
5. Use facts already present in the memory/context instead of planning steps to look them up.
6. Windows only: run_command executes PowerShell, so use PowerShell syntax.
7. Prefer headless tools (run_command, read_file, write_file) over UI automation for files and data.
8. Keep the plan minimal: the fewest steps that reliably achieve the goal.
9. DANGEROUS ACTION PREVENTION: To "read", "check", or "verify" what is on the screen or inside an application, you MUST use `verify_screen` or `analyze_screen`. NEVER use keyboard/mouse actions (e.g. `Ctrl+A`, `Delete`, `Ctrl+C`) to try and read or extract information. Never plan destructive actions just to test the state of an application.

# STRICT Automation Policy
- ALWAYS try to automate the user's request. 
- NEVER tell the user to do something manually (e.g. "Please open the file yourself", "You can do this by...", "I am unable to do this").
- If the user gives a command, you MUST formulate an `execute` plan to attempt it, even if it might fail. DO NOT give up before trying.
"""


def _build_tool_reference() -> str:
    """Describe the executor's real tools so the plan always matches what exists."""
    from scout.ai.tools import get_tools

    lines = []
    for schema in get_tools():
        fn = schema["function"]
        if fn["name"] in _INTERNAL_TOOLS:
            continue
        props = fn.get("parameters", {}).get("properties", {})
        required = set(fn.get("parameters", {}).get("required", []))
        params = []
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "any")
            params.append(f"{pname}: {ptype}" if pname in required else f"[{pname}: {ptype}]")
        line = f"- {fn['name']}({', '.join(params)}) - {fn.get('description', '')}"
        action = props.get("action", {})
        if action.get("enum"):
            line += f" Actions: {', '.join(action['enum'])}."
        lines.append(line)
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

    def generate_plan(self, request: str, memory_context: str = "") -> Plan | None:
        """Plan how to handle the user's request. Returns None on hard failure."""
        return self._request_plan(request, request, memory_context)

    def revise_plan(
        self,
        request: str,
        history: list[tuple[PlanStep, str, str]],
        remaining: list[PlanStep],
        memory_context: str = "",
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
        return self._request_plan("\n".join(lines), request, memory_context, status_text="Planner is revising the plan...")

    # ── Internals ──────────────────────────────────────────────────────

    def _request_plan(
        self,
        prompt: str,
        memory_query: str,
        memory_context: str,
        status_text: str | None = None,
    ) -> Plan | None:
        from scout.memory.store import get_memory_store

        mem_block = get_memory_store().get_relevant_memories(memory_query)

        system_prompt = PLANNER_PROMPT.replace("{tool_reference}", _build_tool_reference())
        if memory_context:
            system_prompt += f"\n\n# Recent Conversation / Execution Context\n{memory_context}"

        user_content = f"{mem_block}\n\nUSER REQUEST:\n{prompt}" if mem_block else prompt
        messages: list[dict] = [{"role": "user", "content": user_content}]
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
