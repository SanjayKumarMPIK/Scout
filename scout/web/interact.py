"""Browser interaction module: safe clicking, typing, scrolling, option selection, and state observation."""

from __future__ import annotations

from typing import Any

from scout.web.security import SecurityError, validate_url
from scout.web.ui import log_web_event


def perform_browser_action(
    page: Any,
    action: str,
    selector: str = "",
    text: str = "",
    value: str = "",
    direction: str = "down",
    amount: int = 500,
    timeout_ms: int = 10000,
) -> dict[str, Any]:
    """Execute a concrete, accessible DOM interaction on the browser page.

    Args:
        page: Playwright Page instance.
        action: "click", "type", "select_option", "scroll", "navigate", or "wait".
        selector: CSS selector, text selector, or role specification.
        text: Text to type into fields.
        value: Option value or label to select.
        direction: Scroll direction ("down", "up", "top", "bottom").
        amount: Scroll pixel distance.
        timeout_ms: Timeout in milliseconds for locator readiness.

    Returns:
        Dictionary with status, updated URL, title, and current visible observation.
    """
    action_clean = action.strip().lower()
    log_web_event(f"Browser interaction: {action_clean} on '{selector or direction}'", "browser")

    try:
        if action_clean == "click":
            if not selector:
                raise ValueError("Selector or text is required for click action.")
            # Resolve locator: supports text=, role=, or standard CSS
            loc = _resolve_locator(page, selector)
            loc.first.wait_for(state="visible", timeout=timeout_ms)
            loc.first.click(timeout=timeout_ms)

        elif action_clean == "type":
            if not selector:
                raise ValueError("Selector is required for type action.")
            loc = _resolve_locator(page, selector)
            loc.first.wait_for(state="visible", timeout=timeout_ms)
            loc.first.fill(text, timeout=timeout_ms)

        elif action_clean == "select_option":
            if not selector:
                raise ValueError("Selector is required for select_option action.")
            loc = _resolve_locator(page, selector)
            loc.first.wait_for(state="visible", timeout=timeout_ms)
            # Try value or label
            try:
                loc.first.select_option(value=value, timeout=timeout_ms)
            except Exception:
                loc.first.select_option(label=value, timeout=timeout_ms)

        elif action_clean == "scroll":
            if selector:
                # Scroll element into view
                loc = _resolve_locator(page, selector)
                loc.first.scroll_into_view_if_needed(timeout=timeout_ms)
            else:
                if direction == "down":
                    page.mouse.wheel(0, amount)
                elif direction == "up":
                    page.mouse.wheel(0, -amount)
                elif direction == "bottom":
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                elif direction == "top":
                    page.evaluate("window.scrollTo(0, 0)")
                else:
                    page.mouse.wheel(0, amount)

        elif action_clean == "navigate":
            target_url = text or selector
            if not target_url:
                raise ValueError("Target URL is required for navigate action.")
            # Security: SSRF validation
            safe_url = validate_url(target_url)
            page.goto(safe_url, wait_until="domcontentloaded", timeout=timeout_ms)

        elif action_clean == "wait":
            if selector:
                loc = _resolve_locator(page, selector)
                loc.first.wait_for(state="visible", timeout=timeout_ms)
            else:
                page.wait_for_timeout(min(amount, 5000))

        else:
            raise ValueError(
                f"Unsupported browser action '{action}'. "
                f"Allowed actions: click, type, select_option, scroll, navigate, wait."
            )

        # Allow DOM and microtasks to settle
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass

        # Read updated state
        updated_url = page.url
        updated_title = page.title()
        visible_snippet = ""
        for tag in ["main", "article", '[role="main"]', "body"]:
            try:
                node = page.locator(tag)
                if node.count() > 0:
                    visible_snippet = node.first.inner_text(timeout=500)[:500].strip()
                    if visible_snippet:
                        break
            except Exception:
                continue

        return {
            "success": True,
            "action": action_clean,
            "url": updated_url,
            "title": updated_title,
            "observation": f"Action '{action_clean}' completed on '{updated_title}'. Current URL: {updated_url}\nVisible content preview:\n{visible_snippet}",
        }

    except Exception as exc:
        return {
            "success": False,
            "action": action_clean,
            "error": str(exc),
            "url": getattr(page, "url", ""),
            "title": getattr(page, "title", lambda: "")(),
        }


def _resolve_locator(page: Any, selector: str) -> Any:
    """Resolve accessible locator syntax or standard CSS/XPath."""
    selector_str = selector.strip()
    if selector_str.startswith("text="):
        return page.get_by_text(selector_str[5:])
    if selector_str.startswith("role="):
        parts = selector_str[5:].split(",", 1)
        role = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else None
        return page.get_by_role(role, name=name) if name else page.get_by_role(role)
    if selector_str.startswith("label="):
        return page.get_by_label(selector_str[6:])
    if selector_str.startswith("placeholder="):
        return page.get_by_placeholder(selector_str[12:])

    return page.locator(selector_str)
