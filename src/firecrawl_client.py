"""Firecrawl API client: search for Reddit posts via web search.

Note: Firecrawl does not support scraping reddit.com directly.
We rely on search results which return title + description (search snippets).
This gives us enough text for signal extraction.
"""

import os
import requests
from utils import is_reddit_post_url, normalize_reddit_url, extract_reddit_urls


API_BASE = "https://api.firecrawl.dev/v1"
TIMEOUT = 60


def get_api_key() -> str:
    key = os.getenv("FIRECRAWL_API_KEY", "")
    if not key:
        raise ValueError("FIRECRAWL_API_KEY not set in .env")
    return key


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }


def search_reddit(query: str, limit: int = 10) -> list[dict]:
    """Search the web for a query and return Reddit post results.

    Uses Firecrawl /search endpoint. Reddit blocks full-page scraping,
    so we use title + description from search results as our text content.
    """
    url = f"{API_BASE}/search"
    payload = {
        "query": query,
        "limit": limit,
    }

    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  [!] Search failed for '{query}': {e}")
        return []

    if not data.get("success"):
        print(f"  [!] Search not successful for '{query}': {data}")
        return []

    results = []
    for item in data.get("data", []):
        item_url = item.get("url", "")

        if is_reddit_post_url(item_url):
            # Combine title and description as our content
            title = item.get("title", "")
            description = item.get("description", "")

            results.append({
                "url": normalize_reddit_url(item_url),
                "title": title,
                "description": description,
                "markdown": item.get("markdown", ""),
            })
            continue

        # Also check if description/markdown contains Reddit post links
        text = item.get("description", "") + " " + item.get("markdown", "")
        found_urls = extract_reddit_urls(text)
        for found in found_urls:
            results.append({
                "url": normalize_reddit_url(found),
                "title": "",
                "description": "",
                "markdown": "",
            })

    return results
