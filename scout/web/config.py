"""Web capability configuration for Scout."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scout.config import APP_DIR
from scout.user_config import load_config


@dataclass
class WebConfig:
    # ── Search Configuration ──────────────────────────────────────────
    # Provider: "duckduckgo", "tavily", "google", "brave"
    search_provider: str = "duckduckgo"
    tavily_api_key: str = ""
    google_api_key: str = ""
    google_cse_id: str = ""
    brave_api_key: str = ""
    max_search_results: int = 6

    # ── HTTP Fetcher Configuration ────────────────────────────────────
    request_timeout: float = 15.0
    max_redirects: int = 5
    max_content_length: int = 8000
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 (Scout Web Assistant)"
    )
    respect_robots_txt: bool = True
    max_download_size_bytes: int = 5 * 1024 * 1024  # 5 MB max response

    # ── Browser Automation Configuration ──────────────────────────────
    browser_type: str = "chromium"  # "chromium", "firefox", "webkit"
    headless: bool = True
    browser_timeout_ms: int = 25000
    viewport_width: int = 1280
    viewport_height: int = 800
    browser_data_dir: Path = field(default_factory=lambda: APP_DIR / "browser_data")

    # ── Security & Safety ─────────────────────────────────────────────
    block_private_ips: bool = True
    allowed_schemes: tuple[str, ...] = ("http", "https")


def get_web_config() -> WebConfig:
    """Load web configuration from environment variables and config.json."""
    cfg = WebConfig()
    user_cfg = load_config().get("web", {})

    # Provider
    cfg.search_provider = os.getenv(
        "SCOUT_SEARCH_PROVIDER",
        user_cfg.get("search_provider", cfg.search_provider),
    ).lower()

    # API Keys (env vars take precedence)
    cfg.tavily_api_key = os.getenv("TAVILY_API_KEY", user_cfg.get("tavily_api_key", ""))
    cfg.google_api_key = os.getenv("GOOGLE_API_KEY", user_cfg.get("google_api_key", ""))
    cfg.google_cse_id = os.getenv("GOOGLE_CSE_ID", user_cfg.get("google_cse_id", ""))
    cfg.brave_api_key = os.getenv("BRAVE_API_KEY", user_cfg.get("brave_api_key", ""))

    # Limits & Timeouts
    if "request_timeout" in user_cfg:
        cfg.request_timeout = float(user_cfg["request_timeout"])
    if "max_content_length" in user_cfg:
        cfg.max_content_length = int(user_cfg["max_content_length"])
    if "respect_robots_txt" in user_cfg:
        cfg.respect_robots_txt = bool(user_cfg["respect_robots_txt"])

    # Browser
    if "headless" in user_cfg:
        cfg.headless = bool(user_cfg["headless"])
    if os.getenv("SCOUT_BROWSER_HEADLESS") is not None:
        cfg.headless = os.getenv("SCOUT_BROWSER_HEADLESS", "").lower() in ("1", "true", "yes")

    if "browser_timeout_ms" in user_cfg:
        cfg.browser_timeout_ms = int(user_cfg["browser_timeout_ms"])

    return cfg
