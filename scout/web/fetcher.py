"""HTTP webpage fetcher with SSRF defense, robots.txt compliance, and DOM readability extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
import urllib.robotparser

import httpx
from bs4 import BeautifulSoup, Comment

from scout.web.config import WebConfig, get_web_config
from scout.web.security import SecurityError, validate_url, wrap_untrusted_content
from scout.web.ui import log_web_event


@dataclass
class ExtractedWebpage:
    url: str
    title: str = ""
    description: str = ""
    published_date: str = ""
    author: str = ""
    headings: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    content: str = ""
    requires_js: bool = False
    truncated: bool = False

    def to_formatted_text(self) -> str:
        """Format the extracted page into structured text for agent reasoning."""
        parts = []
        if self.title:
            parts.append(f"# {self.title}")
        parts.append(f"Source URL: {self.url}")
        if self.published_date:
            parts.append(f"Publication Date: {self.published_date}")
        if self.author:
            parts.append(f"Author: {self.author}")
        if self.description:
            parts.append(f"Description: {self.description}")

        if self.requires_js:
            parts.append(
                "\n⚠️ [JAVASCRIPT RENDERING RECOMMENDED]\n"
                "This webpage appears to be a client-side JavaScript application (SPA shell). "
                "The server returned minimal static HTML. For full content, use 'browser_navigate'."
            )

        if self.headings:
            parts.append("\n## Key Headings")
            for h in self.headings[:8]:
                parts.append(f"- {h}")

        parts.append("\n## Main Content\n")
        parts.append(self.content or "(No text content found)")

        if self.truncated:
            parts.append("\n[... Remaining content truncated to fit context limits ...]")

        if self.links:
            parts.append("\n## Relevant Links")
            for link in self.links[:10]:
                parts.append(f"- [{link['text']}]({link['url']})")

        raw_text = "\n".join(parts)
        return wrap_untrusted_content(raw_text, self.url)


# Cache robots.txt parsers by domain
_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser] = {}


def _check_robots_txt(url: str, user_agent: str, timeout: float = 5.0) -> bool:
    """Return True if robots.txt allows fetching the URL, False otherwise."""
    parsed = urlparse(url)
    domain_key = f"{parsed.scheme}://{parsed.netloc}"

    rp = _ROBOTS_CACHE.get(domain_key)
    if rp is None:
        robots_url = f"{domain_key}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            validate_url(robots_url)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    # Disallow all if robots.txt is forbidden
                    rp.disallow_all = True
                else:
                    # Allow all if robots.txt 404s
                    rp.allow_all = True
        except Exception:
            # If robots.txt cannot be reached, default to permissive
            rp.allow_all = True
        _ROBOTS_CACHE[domain_key] = rp

    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True


def _detect_js_requirement(soup: BeautifulSoup, text_len: int) -> bool:
    """Detect if page is likely an SPA requiring client-side JavaScript rendering."""
    # Common SPA hooks
    spa_hooks = soup.select("#root, #app, #__next, div[data-reactroot], app-root")
    has_spa_hook = any(len(hook.get_text(strip=True)) < 50 for hook in spa_hooks)

    body_text = soup.body.get_text(strip=True) if soup.body else ""
    js_notice_patterns = [
        r"enable javascript",
        r"javascript is required",
        r"need to enable javascript",
        r"please turn on javascript",
    ]
    has_js_notice = any(re.search(pat, body_text, re.IGNORECASE) for pat in js_notice_patterns)

    # Minimal text but has many scripts
    script_count = len(soup.find_all("script"))
    is_sparse = (text_len < 250) and (script_count >= 3)

    return (has_spa_hook and text_len < 300) or has_js_notice or is_sparse


def _clean_html_tree(soup: BeautifulSoup) -> None:
    """Remove boilerplate, scripts, styles, navigation, and advertisement elements."""
    # Remove HTML comments
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()


    # Elements to strip
    strip_tags = [
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "embed",
        "object",
        "nav",
        "footer",
        "header",
        "aside",
    ]
    for tag in soup.find_all(strip_tags):
        tag.decompose()

    # Common ad and banner classes/roles
    ad_selectors = [
        ".ad",
        ".advertisement",
        ".ads",
        ".banner-ad",
        ".cookie-banner",
        ".cookie-notice",
        ".nav-menu",
        '[role="navigation"]',
        '[role="banner"]',
        '[role="alert"]',
    ]
    for sel in ad_selectors:
        for match in soup.select(sel):
            match.decompose()


def _extract_page_content(soup: BeautifulSoup, max_chars: int) -> tuple[str, bool]:
    """Extract readable text from main article or body and enforce character limit."""
    # Target semantic main container if available
    main_node = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )

    lines: list[str] = []
    for elem in main_node.descendants:
        if elem.name in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote"):
            txt = elem.get_text(" ", strip=True)
            if txt and len(txt) > 3:
                # Add bullet for lists
                prefix = "- " if elem.name == "li" else ""
                lines.append(f"{prefix}{txt}")

    # Fallback to general text if semantic blocks didn't capture enough
    if len(" ".join(lines)) < 150:
        lines = [line.strip() for line in main_node.get_text("\n").split("\n") if line.strip()]

    # Deduplicate consecutive identical lines
    deduped: list[str] = []
    for l in lines:
        if not deduped or deduped[-1] != l:
            deduped.append(l)

    full_text = "\n\n".join(deduped)
    if len(full_text) > max_chars:
        return full_text[:max_chars], True
    return full_text, False


def fetch_webpage(url: str, config: WebConfig | None = None) -> ExtractedWebpage:
    """Safely fetch and extract content from a publicly accessible webpage.

    Args:
        url: URL of the webpage to fetch.
        config: Optional WebConfig settings.

    Returns:
        ExtractedWebpage containing clean content, metadata, links, and JS requirements.

    Raises:
        SecurityError: If URL is private/unsafe.
        Exception: On network errors or HTTP failures.
    """
    cfg = config or get_web_config()

    # Step 1: SSRF Validation
    safe_url = validate_url(url, allow_private=not cfg.block_private_ips)

    # Step 2: Robots.txt check
    if cfg.respect_robots_txt:
        if not _check_robots_txt(safe_url, cfg.user_agent, timeout=cfg.request_timeout):
            return ExtractedWebpage(
                url=safe_url,
                title="Access Restricted",
                content=f"Access to '{safe_url}' is disallowed by the website's robots.txt policy.",
            )

    log_web_event(f"Fetching webpage: {safe_url}", "fetch")

    # Step 3: Fetch with safe redirect validation
    headers = {
        "User-Agent": cfg.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    current_url = safe_url
    resp_text = ""
    final_url = safe_url

    with httpx.Client(timeout=cfg.request_timeout, follow_redirects=False) as client:
        redirect_count = 0
        while redirect_count <= cfg.max_redirects:
            try:
                resp = client.get(current_url, headers=headers)
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"Connection timed out while fetching '{current_url}': {exc}") from exc
            except httpx.RequestError as exc:
                raise ConnectionError(f"Network error while connecting to '{current_url}': {exc}") from exc

            # Handle redirects safely
            if resp.is_redirect:
                loc = resp.headers.get("location")
                if not loc:
                    break
                next_url = urljoin(current_url, loc)
                # MUST validate redirect target to prevent SSRF via redirection!
                safe_next = validate_url(next_url, allow_private=not cfg.block_private_ips)
                current_url = safe_next
                redirect_count += 1
                continue

            resp.raise_for_status()

            # Content type check
            ctype = resp.headers.get("content-type", "").lower()
            if not any(t in ctype for t in ("text/html", "text/plain", "application/xhtml")):
                raise ValueError(
                    f"Unsupported content type '{ctype}'. Scout only fetches HTML or text documents."
                )

            # Check download size limit
            content_bytes = resp.content
            if len(content_bytes) > cfg.max_download_size_bytes:
                raise ValueError(
                    f"Response size ({len(content_bytes)} bytes) exceeded limit of {cfg.max_download_size_bytes} bytes."
                )

            resp_text = resp.text
            final_url = current_url
            break
        else:
            raise RecursionError(f"Exceeded maximum redirect limit ({cfg.max_redirects}).")

    # Step 4: DOM Parsing & Extraction
    soup = BeautifulSoup(resp_text, "html.parser")

    # Metadata extraction
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()

    pub_date = ""
    date_meta = (
        soup.find("meta", property="article:published_time")
        or soup.find("meta", attrs={"name": "date"})
        or soup.find("meta", attrs={"name": "pubdate"})
        or soup.find("time")
    )
    if date_meta:
        pub_date = date_meta.get("content") or date_meta.get("datetime") or date_meta.get_text(strip=True)

    author = ""
    author_meta = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", property="article:author")
    if author_meta and author_meta.get("content"):
        author = author_meta["content"].strip()

    # Clean DOM (strip nav, ads, scripts, footers) before extracting links & text
    _clean_html_tree(soup)

    # Headings
    headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]

    # Links from content
    links: list[dict[str, str]] = []
    seen_hrefs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        link_text = a.get_text(strip=True)
        if href and link_text and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
            full_href = urljoin(final_url, href)
            if full_href not in seen_hrefs and full_href.startswith("http"):
                seen_hrefs.add(full_href)
                links.append({"text": link_text[:50], "url": full_href})
            if len(links) >= 15:
                break

    # Extract text
    content, truncated = _extract_page_content(soup, max_chars=cfg.max_content_length)


    # Detect JavaScript requirement
    requires_js = _detect_js_requirement(soup, len(content))

    log_web_event(
        f"Extracted {len(content)} chars from '{title or final_url}'{' (JS recommended)' if requires_js else ''}.",
        "extract",
    )

    return ExtractedWebpage(
        url=final_url,
        title=title,
        description=description,
        published_date=pub_date,
        author=author,
        headings=headings,
        links=links,
        content=content,
        requires_js=requires_js,
        truncated=truncated,
    )
