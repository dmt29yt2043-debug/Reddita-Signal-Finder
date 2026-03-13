"""Utility functions: URL normalization, text cleaning, deduplication."""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


# Reddit post URL pattern
REDDIT_POST_PATTERN = re.compile(
    r'https?://(?:www\.|old\.)?reddit\.com/r/\w+/comments/\w+'
)


def is_reddit_post_url(url: str) -> bool:
    """Check if URL is a Reddit post (not subreddit, profile, search, etc.)."""
    return bool(REDDIT_POST_PATTERN.match(url))


def normalize_reddit_url(url: str) -> str:
    """Normalize a Reddit URL: strip tracking params, use www.reddit.com."""
    parsed = urlparse(url)

    # Normalize host to www.reddit.com
    host = "www.reddit.com"

    # Clean path: remove trailing slashes, strip after the post slug
    path = parsed.path.rstrip("/")

    # Keep only the core post path: /r/{sub}/comments/{id}/{slug}
    match = re.match(r'(/r/\w+/comments/\w+(?:/[^/]*)?)', path)
    if match:
        path = match.group(1)

    # Remove all query params (tracking, utm, etc.)
    clean_url = urlunparse(("https", host, path, "", "", ""))
    return clean_url


def extract_reddit_urls(text: str) -> list[str]:
    """Find all Reddit post URLs in a block of text."""
    urls = REDDIT_POST_PATTERN.findall(text)
    return urls


def extract_subreddit(url: str) -> str:
    """Extract subreddit name from a Reddit URL."""
    match = re.search(r'/r/(\w+)/', url)
    return match.group(1) if match else ""


def extract_post_id(url: str) -> str:
    """Extract the Reddit post ID from a URL.

    Example: /r/nycparents/comments/1ebd0g7/... -> 1ebd0g7
    """
    match = re.search(r'/comments/(\w+)', url)
    return match.group(1) if match else ""


def clean_text(text: str) -> str:
    """Clean scraped text: normalize whitespace, remove junk."""
    if not text:
        return ""
    # Collapse multiple newlines into two
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def make_snippet(text: str, max_length: int = 500) -> str:
    """Create a text snippet of the first ~max_length characters."""
    cleaned = clean_text(text)
    if len(cleaned) <= max_length:
        return cleaned
    # Cut at last space before limit
    cut = cleaned[:max_length].rsplit(' ', 1)[0]
    return cut + "..."


def deduplicate_by_url(posts: list[dict]) -> list[dict]:
    """Remove duplicate posts by normalized URL. Keep first occurrence."""
    seen = set()
    unique = []
    for post in posts:
        norm = normalize_reddit_url(post.get("url", ""))
        if norm not in seen:
            seen.add(norm)
            unique.append(post)
    return unique
