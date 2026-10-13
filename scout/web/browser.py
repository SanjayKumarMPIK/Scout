"""Dedicated Scout browser session manager using Playwright.

Features:
- Isolated Scout browser context (no leakage of user's personal browser cookies or logins).
- Crash and disconnect detection with auto-recovery.
- Meaningful page readiness waits (domcontentloaded + network settling).
- Resource cleanup and lifecycle management.
"""

from __future__ import annotations

import atexit
from typing import Any

from scout.web.config import WebConfig, get_web_config
from scout.web.extract import extract_from_browser_page, extract_headings_and_text
from scout.web.interact import perform_browser_action
from scout.web.security import SecurityError, validate_url, wrap_untrusted_content
from scout.web.ui import log_web_event


class BrowserSessionError(Exception):
    """Raised when the browser automation engine encounters an unrecoverable failure."""


class ScoutBrowserSession:
    """Manages an isolated Playwright browser session for Scout."""

    def __init__(self, config: WebConfig | None = None):
        self.config = config or get_web_config()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def _ensure_active(self) -> Any:
        """Ensure Playwright, Browser, Context, and Page are initialized and responsive."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserSessionError(
                "Playwright is not installed. Please install it using 'pip install playwright' "
                "followed by 'python -m playwright install chromium'."
            ) from exc

        # Check if active page is still responsive
        if self._page is not None and self._browser is not None:
            try:
                if not self._page.is_closed() and self._browser.is_connected():
                    return self._page
            except Exception:
                pass  # Broken session; recreate

        self.close()

        log_web_event("Initializing isolated Scout browser instance...", "browser")
        try:
            self._playwright = sync_playwright().start()
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
            ]
            self._browser = self._playwright.chromium.launch(
                headless=self.config.headless,
                args=launch_args,
            )
            self._context = self._browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                user_agent=self.config.user_agent,
                ignore_https_errors=False,
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.config.browser_timeout_ms)
            return self._page
        except Exception as exc:
            self.close()
            raise BrowserSessionError(f"Failed to launch browser engine: {exc}") from exc

    def navigate(self, url: str, timeout_ms: int | None = None) -> dict[str, Any]:
        """Navigate to a URL in the browser with SSRF protection and page readiness verification."""
        cfg = self.config
        safe_url = validate_url(url, allow_private=not cfg.block_private_ips)
        effective_timeout = timeout_ms or cfg.browser_timeout_ms

        page = self._ensure_active()
        log_web_event(f"Navigating browser to: {safe_url}", "browser")

        try:
            response = page.goto(safe_url, wait_until="domcontentloaded", timeout=effective_timeout)
            status_code = response.status if response else 200

            # Wait for network idle or reasonable DOM settlement without indefinite sleep
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass  # Network idle is a bonus; page is already domcontentloaded

            page_info = extract_headings_and_text(page, max_chars=cfg.max_content_length)
            url_after = page.url
            title_after = page.title()

            summary = (
                f"Page Title: {title_after}\n"
                f"Current URL: {url_after}\n"
                f"HTTP Status: {status_code}\n"
                f"Headings: {', '.join(page_info['headings']) if page_info['headings'] else 'None'}\n\n"
                f"Content Preview:\n{page_info['content'][:1500]}"
            )
            wrapped = wrap_untrusted_content(summary, url_after)

            log_web_event(f"Loaded '{title_after}' ({status_code})", "success")
            return {
                "success": True,
                "url": url_after,
                "title": title_after,
                "status_code": status_code,
                "headings": page_info["headings"],
                "content_preview": page_info["content"][:1500],
                "formatted": wrapped,
            }

        except Exception as exc:
            log_web_event(f"Browser navigation failed: {exc}", "error")
            return {
                "success": False,
                "error": str(exc),
                "url": safe_url,
            }

    def extract(
        self,
        extract_type: str = "all",
        selector: str = "",
        fields: list[str] | None = None,
        next_selector: str = "",
        max_pages: int = 1,
    ) -> dict[str, Any]:
        """Extract structured data from the currently loaded browser page."""
        if self._page is None or self._page.is_closed():
            raise BrowserSessionError("No browser page is currently open. Navigate to a URL first.")

        return extract_from_browser_page(
            self._page,
            extract_type=extract_type,
            selector=selector,
            fields=fields,
            next_selector=next_selector,
            max_pages=max_pages,
        )

    def interact(
        self,
        action: str,
        selector: str = "",
        text: str = "",
        value: str = "",
        direction: str = "down",
        amount: int = 500,
        timeout_ms: int = 10000,
    ) -> dict[str, Any]:
        """Perform an interaction on the active page."""
        if self._page is None or self._page.is_closed():
            raise BrowserSessionError("No browser page is currently open. Navigate to a URL first.")

        return perform_browser_action(
            self._page,
            action=action,
            selector=selector,
            text=text,
            value=value,
            direction=direction,
            amount=amount,
            timeout_ms=timeout_ms,
        )

    def close(self) -> None:
        """Close browser resources and clean up processes."""
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None


# Singleton instance
_BROWSER_SESSION: ScoutBrowserSession | None = None


def get_browser_session() -> ScoutBrowserSession:
    """Get or initialize the singleton Scout browser session."""
    global _BROWSER_SESSION
    if _BROWSER_SESSION is None:
        _BROWSER_SESSION = ScoutBrowserSession()
    return _BROWSER_SESSION


@atexit.register
def _cleanup_browser() -> None:
    global _BROWSER_SESSION
    if _BROWSER_SESSION is not None:
        _BROWSER_SESSION.close()
        _BROWSER_SESSION = None
