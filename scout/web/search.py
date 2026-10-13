"""Web search provider integration for Scout.

Supports multiple configurable providers:
- duckduckgo: Zero-config, free, no API key required.
- tavily: AI-optimized search API (requires TAVILY_API_KEY).
- google: Google Custom Search JSON API (requires GOOGLE_API_KEY and GOOGLE_CSE_ID).
- brave: Brave Search API (requires BRAVE_API_KEY).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import unquote, urlencode

import httpx
from bs4 import BeautifulSoup

from scout.web.config import WebConfig, get_web_config
from scout.web.ui import log_web_event


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    published_date: str = ""
    query: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class SearchProviderError(Exception):
    """Raised when a search provider fails or is misconfigured."""


def _extract_date_from_snippet(text: str) -> tuple[str, str]:
    """Extract common date prefixes from snippets (e.g., 'May 15, 2024 ...')."""
    date_patterns = [
        r"^([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4})\s*[-—·•]\s*(.*)$",
        r"^(\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})\s*[-—·•]\s*(.*)$",
        r"^(\d{4}-\d{2}-\d{2})\s*[-—·•]\s*(.*)$",
        r"^(\d+\s+(?:days?|hours?|weeks?|months?|years?)\s+ago)\s*[-—·•]\s*(.*)$",
    ]
    for pattern in date_patterns:
        match = re.match(pattern, text.strip())
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return "", text


class DuckDuckGoProvider:
    """DuckDuckGo search provider requiring no API key."""

    LITE_URL = "https://lite.duckduckgo.com/lite/"
    HTML_URL = "https://html.duckduckgo.com/html/"

    def search(self, query: str, max_results: int = 6, timeout: float = 12.0) -> list[SearchResult]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://lite.duckduckgo.com/",
        }
        data = {"q": query, "kl": ""}

        results: list[SearchResult] = []
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.post(self.LITE_URL, data=data, headers=headers)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            tables = soup.select("table")
            if not tables:
                return results

            # Parse lite table rows
            current_link = None
            current_title = ""
            for tr in soup.select("table tr"):
                link_tag = tr.select_one("a.result-link")
                if link_tag:
                    raw_href = link_tag.get("href", "")
                    if "uddg=" in raw_href:
                        m = re.search(r"uddg=([^&]+)", raw_href)
                        href = unquote(m.group(1)) if m else raw_href
                    else:
                        href = raw_href
                    current_link = href
                    current_title = link_tag.get_text(strip=True)

                snippet_td = tr.select_one("td.result-snippet")
                if snippet_td and current_link:

                    raw_snippet = snippet_td.get_text(strip=True)
                    pub_date, clean_snippet = _extract_date_from_snippet(raw_snippet)
                    # Filter out sponsored ads or tracking redirects
                    is_ad = "duckduckgo.com/y.js" in current_link or "ad_provider=" in current_link or "ad_domain=" in current_link
                    if current_link.startswith("http") and not is_ad:
                        results.append(
                            SearchResult(
                                title=current_title,
                                url=current_link,
                                snippet=clean_snippet,
                                published_date=pub_date,
                                query=query,
                            )
                        )
                    current_link = None
                    current_title = ""
                    if len(results) >= max_results:
                        break


            return results
        except Exception as exc:
            raise SearchProviderError(f"DuckDuckGo search failed: {exc}") from exc


class TavilyProvider:
    """Tavily search provider."""

    API_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str):
        if not api_key:
            raise SearchProviderError(
                "Tavily search provider requires an API key.\n"
                "Configuration options:\n"
                "1. Set the TAVILY_API_KEY environment variable.\n"
                "2. Add 'tavily_api_key' under the 'web' section in ~/.scout/config.json.\n"
                "3. Or switch to the default 'duckduckgo' provider (zero config required)."
            )
        self.api_key = api_key

    def search(self, query: str, max_results: int = 6, timeout: float = 12.0) -> list[SearchResult]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(self.API_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()

            results: list[SearchResult] = []
            for item in data.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("content", ""),
                        published_date=item.get("published_date", ""),
                        query=query,
                    )
                )
            return results
        except httpx.HTTPStatusError as exc:
            raise SearchProviderError(f"Tavily API returned HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except Exception as exc:
            raise SearchProviderError(f"Tavily search failed: {exc}") from exc


class GoogleCSEProvider:
    """Google Custom Search JSON API provider."""

    API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cse_id: str):
        if not api_key or not cse_id:
            raise SearchProviderError(
                "Google Custom Search requires both GOOGLE_API_KEY and GOOGLE_CSE_ID.\n"
                "Configuration options:\n"
                "1. Set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables.\n"
                "2. Configure 'google_api_key' and 'google_cse_id' in ~/.scout/config.json under 'web'.\n"
                "3. Or switch to 'duckduckgo' provider."
            )
        self.api_key = api_key
        self.cse_id = cse_id

    def search(self, query: str, max_results: int = 6, timeout: float = 12.0) -> list[SearchResult]:
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(max_results, 10),
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(self.API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            results: list[SearchResult] = []
            for item in data.get("items", []):
                snippet = item.get("snippet", "")
                pub_date, clean_snippet = _extract_date_from_snippet(snippet)
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=clean_snippet,
                        published_date=pub_date,
                        query=query,
                    )
                )
            return results
        except Exception as exc:
            raise SearchProviderError(f"Google CSE search failed: {exc}") from exc


class BraveProvider:
    """Brave Search API provider."""

    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        if not api_key:
            raise SearchProviderError(
                "Brave search requires BRAVE_API_KEY.\n"
                "Set BRAVE_API_KEY env var or configure in ~/.scout/config.json."
            )
        self.api_key = api_key

    def search(self, query: str, max_results: int = 6, timeout: float = 12.0) -> list[SearchResult]:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {"q": query, "count": max_results}
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(self.API_URL, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            results: list[SearchResult] = []
            for item in data.get("web", {}).get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", ""),
                        published_date=item.get("page_age", ""),
                        query=query,
                    )
                )
            return results
        except Exception as exc:
            raise SearchProviderError(f"Brave search failed: {exc}") from exc


def get_search_provider(config: WebConfig | None = None) -> Any:
    """Instantiate the configured search provider."""
    cfg = config or get_web_config()
    provider_name = cfg.search_provider.lower()

    if provider_name == "tavily":
        return TavilyProvider(cfg.tavily_api_key)
    if provider_name == "google":
        return GoogleCSEProvider(cfg.google_api_key, cfg.google_cse_id)
    if provider_name == "brave":
        return BraveProvider(cfg.brave_api_key)
    return DuckDuckGoProvider()


def search_web(
    queries: list[str] | str,
    max_results: int = 6,
    config: WebConfig | None = None,
) -> list[SearchResult]:
    """Execute a web search across one or more queries and return unified, deduplicated results.

    Args:
        queries: Single query string or list of query strings.
        max_results: Maximum results to return per query or in total.
        config: Optional WebConfig instance.

    Returns:
        List of SearchResult objects with title, url, snippet, published_date.
    """
    cfg = config or get_web_config()
    provider = get_search_provider(cfg)

    query_list = [queries] if isinstance(queries, str) else list(queries)
    query_list = [q.strip() for q in query_list if q and q.strip()]

    if not query_list:
        return []

    log_web_event(f"Searching web with {len(query_list)} quer{'y' if len(query_list) == 1 else 'ies'}...", "search")

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for q in query_list:
        try:
            results = provider.search(q, max_results=max_results, timeout=cfg.request_timeout)
            for res in results:
                # Normalize URL for deduplication
                norm_url = res.url.rstrip("/")
                if norm_url not in seen_urls:
                    seen_urls.add(norm_url)
                    all_results.append(res)
        except SearchProviderError:
            raise
        except Exception as exc:
            raise SearchProviderError(f"Search failed for query '{q}': {exc}") from exc

    log_web_event(f"Found {len(all_results)} relevant sources across queries.", "success")
    return all_results
