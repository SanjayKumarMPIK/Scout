"""DOM extraction utilities for browser pages (headings, tables, lists, structured fields, pagination)."""

from __future__ import annotations

import json
import re
from typing import Any

from scout.web.security import wrap_untrusted_content
from scout.web.ui import log_web_event


def extract_headings_and_text(page: Any, max_chars: int = 8000) -> dict[str, Any]:
    """Extract headings, main text, and document title from a browser page."""
    title = page.title()
    url = page.url

    headings = []
    for h in page.locator("h1, h2, h3").all():
        try:
            txt = h.text_content(timeout=500)
            if txt and txt.strip():
                headings.append(txt.strip())
        except Exception:
            continue

    # Extract text from main semantic nodes or body
    text_content = ""
    for sel in ["main", "article", '[role="main"]', "body"]:
        locator = page.locator(sel)
        if locator.count() > 0:
            try:
                raw = locator.first.inner_text(timeout=1000)
                if raw and len(raw.strip()) > 50:
                    text_content = raw.strip()
                    break
            except Exception:
                continue

    truncated = False
    if len(text_content) > max_chars:
        text_content = text_content[:max_chars]
        truncated = True

    return {
        "url": url,
        "title": title,
        "headings": headings[:10],
        "content": text_content,
        "truncated": truncated,
    }


def extract_links(page: Any, max_links: int = 25) -> list[dict[str, str]]:
    """Extract visible links with text and destinations from the page."""
    results: list[dict[str, str]] = []
    seen = set()

    for a in page.locator("a[href]").all():
        if len(results) >= max_links:
            break
        try:
            href = a.get_attribute("href", timeout=300)
            text = a.text_content(timeout=300)
            if not href or not text or not text.strip():
                continue
            text = text.strip()
            if href.startswith(("#", "javascript:", "mailto:")):
                continue
            if href not in seen:
                seen.add(href)
                results.append({"text": text[:60], "url": href})
        except Exception:
            continue

    return results


def extract_tables(page: Any, max_tables: int = 5) -> list[dict[str, Any]]:
    """Extract tables from the page into structured headers and rows."""
    tables_data: list[dict[str, Any]] = []

    for idx, table in enumerate(page.locator("table").all()[:max_tables]):
        try:
            # Headers
            headers = []
            for th in table.locator("th").all():
                txt = th.text_content(timeout=300)
                if txt:
                    headers.append(txt.strip())

            # Rows
            rows = []
            for tr in table.locator("tr").all()[:50]:
                tds = [td.text_content(timeout=300).strip() for td in tr.locator("td").all()]
                if tds:
                    if headers and len(headers) == len(tds):
                        rows.append(dict(zip(headers, tds)))
                    else:
                        rows.append(tds)

            if rows or headers:
                tables_data.append({
                    "table_index": idx + 1,
                    "headers": headers,
                    "row_count": len(rows),
                    "rows": rows[:30],
                })
        except Exception:
            continue

    return tables_data


def extract_lists(page: Any, max_lists: int = 5) -> list[dict[str, Any]]:
    """Extract ordered and unordered lists from the page."""
    lists_data: list[dict[str, Any]] = []

    for idx, list_elem in enumerate(page.locator("ul, ol").all()[:max_lists]):
        try:
            items = []
            for li in list_elem.locator("li").all()[:25]:
                txt = li.text_content(timeout=300)
                if txt and txt.strip():
                    items.append(txt.strip())
            if items:
                lists_data.append({
                    "list_index": idx + 1,
                    "item_count": len(items),
                    "items": items,
                })
        except Exception:
            continue

    return lists_data


def extract_elements_by_selector(page: Any, selector: str, max_items: int = 25) -> list[dict[str, Any]]:
    """Extract elements matching a specific CSS or XPath selector."""
    items: list[dict[str, Any]] = []
    try:
        locators = page.locator(selector).all()
        for loc in locators[:max_items]:
            try:
                txt = loc.inner_text(timeout=500).strip()
                tag = loc.evaluate("el => el.tagName.toLowerCase()")
                attrs = loc.evaluate("""el => {
                    const res = {};
                    for (const attr of el.attributes) {
                        if (['id', 'class', 'href', 'src', 'name', 'value', 'data-id', 'aria-label'].includes(attr.name)) {
                            res[attr.name] = attr.value;
                        }
                    }
                    return res;
                }""")
                items.append({
                    "tag": tag,
                    "text": txt[:200],
                    "attributes": attrs,
                })
            except Exception:
                continue
    except Exception as exc:
        items.append({"error": f"Failed to query selector '{selector}': {exc}"})

    return items


def extract_structured_fields(page: Any, fields: list[str]) -> dict[str, Any]:
    """Extract requested fields using semantic DOM patterns.

    Identifies missing or uncertain fields clearly without hallucinating values.
    """
    result: dict[str, Any] = {}

    for field in fields:
        field_clean = field.strip().lower()
        field_result = {"value": None, "status": "missing", "confidence": "none"}

        # Search patterns
        candidates = [
            f"[itemprop='{field_clean}']",
            f"#{field_clean}",
            f".{field_clean}",
            f"[data-{field_clean}]",
            f"[aria-label*='{field_clean}' i]",
            f"[name='{field_clean}']",
            f"[id*='{field_clean}' i]",
            f"[class*='{field_clean}' i]",
        ]

        # Specific heuristics for prices
        if field_clean in ("price", "cost", "amount"):
            candidates = [
                "[class*='price' i]",
                "[id*='price' i]",
                "[itemprop='price']",
                ".price",
                ".cost",
                ".amount",
            ] + candidates

        # Specific heuristics for titles/names
        if field_clean in ("title", "name", "heading", "product_name"):
            candidates = ["h1", "[itemprop='name']", ".product-title", ".title"] + candidates

        # Specific heuristics for ratings
        if field_clean in ("rating", "stars", "score"):
            candidates = ["[class*='rating' i]", "[aria-label*='rating' i]", "[itemprop='ratingValue']"] + candidates

        for sel in candidates:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    text = loc.inner_text(timeout=400).strip()
                    if text:
                        field_result = {
                            "value": text[:150],
                            "status": "extracted",
                            "confidence": "high" if sel == candidates[0] else "medium",
                            "selector_matched": sel,
                        }
                        break
            except Exception:
                continue

        result[field] = field_result

    return result


def extract_from_browser_page(
    page: Any,
    extract_type: str = "all",
    selector: str = "",
    fields: list[str] | None = None,
    next_selector: str = "",
    max_pages: int = 1,
) -> dict[str, Any]:
    """Unified entry point for browser structured extraction.

    Supports:
    - headings & main text
    - links
    - tables & lists
    - specific selector elements
    - structured requested fields
    - pagination across multiple pages
    """
    url = page.url
    title = page.title()
    log_web_event(f"Extracting '{extract_type}' from '{title or url}'...", "extract")

    pages_extracted = []
    current_page_num = 1

    while current_page_num <= max_pages:
        page_data: dict[str, Any] = {
            "page_number": current_page_num,
            "url": page.url,
            "title": page.title(),
        }

        if extract_type in ("all", "text"):
            page_data.update(extract_headings_and_text(page))

        if extract_type in ("all", "links"):
            page_data["links"] = extract_links(page)

        if extract_type in ("all", "tables"):
            page_data["tables"] = extract_tables(page)

        if extract_type in ("all", "lists"):
            page_data["lists"] = extract_lists(page)

        if selector or extract_type == "elements":
            page_data["elements"] = extract_elements_by_selector(page, selector or "*")

        if fields:
            page_data["structured_fields"] = extract_structured_fields(page, fields)

        pages_extracted.append(page_data)

        # Pagination handling
        if next_selector and current_page_num < max_pages:
            next_btn = page.locator(next_selector).first
            try:
                if next_btn.count() > 0 and next_btn.is_visible(timeout=1000):
                    log_web_event(f"Paginating: clicking next page ({next_selector})...", "browser")
                    next_btn.click(timeout=3000)
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                    current_page_num += 1
                else:
                    break
            except Exception as exc:
                log_web_event(f"Pagination stopped: {exc}", "info")
                break
        else:
            break

    result_payload: dict[str, Any] = {
        "url": url,
        "title": title,
        "total_pages_extracted": len(pages_extracted),
        "data": pages_extracted if max_pages > 1 else pages_extracted[0],
    }

    # Format JSON string and wrap with security notice
    formatted_json = json.dumps(result_payload, indent=2, ensure_ascii=False)
    wrapped = wrap_untrusted_content(formatted_json, url)
    return {"structured": result_payload, "formatted": wrapped}
