"""Scout web research and browser automation package."""

from __future__ import annotations

from scout.web.browser import get_browser_session
from scout.web.config import WebConfig, get_web_config
from scout.web.fetcher import ExtractedWebpage, fetch_webpage
from scout.web.search import SearchResult, search_web
from scout.web.security import SecurityError, is_ip_restricted, validate_url

__all__ = [
    "WebConfig",
    "get_web_config",
    "SearchResult",
    "search_web",
    "ExtractedWebpage",
    "fetch_webpage",
    "get_browser_session",
    "validate_url",
    "is_ip_restricted",
    "SecurityError",
]
