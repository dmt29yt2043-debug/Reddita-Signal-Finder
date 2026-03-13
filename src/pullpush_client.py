"""PullPush.io client: fetch full Reddit post content and comments.

PullPush is a free Pushshift-compatible API that provides full text
of Reddit posts and comments without authentication.
Rate limits: ~30 req/min hard limit.
"""

import time
import requests


API_BASE = "https://api.pullpush.io/reddit"
TIMEOUT = 30

# Simple rate limiter: track last request time
_last_request_time = 0
MIN_REQUEST_INTERVAL = 2.5  # seconds between requests (~24 req/min, under 30 limit)


def _rate_limit():
    """Wait if needed to stay under rate limits."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def fetch_post_by_id(post_id: str):
    """Fetch a single Reddit post by its ID via PullPush.

    Returns dict with post data or None if not found.
    """
    _rate_limit()
    url = f"{API_BASE}/search/submission/"
    params = {"ids": post_id}

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"    [!] PullPush fetch failed for post {post_id}: {e}")
        return None

    posts = data.get("data", [])
    if not posts:
        return None

    return posts[0]


def search_posts(query: str, subreddit: str = None, size: int = 25) -> list[dict]:
    """Search for Reddit posts via PullPush.

    Args:
        query: search keywords
        subreddit: optional subreddit to limit search
        size: max results (up to 100)
    """
    _rate_limit()
    url = f"{API_BASE}/search/submission/"
    params = {
        "q": query,
        "size": min(size, 100),
    }
    if subreddit:
        params["subreddit"] = subreddit

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"    [!] PullPush search failed for '{query}': {e}")
        return []

    return data.get("data", [])


def fetch_comments(post_id: str, size: int = 50) -> list[dict]:
    """Fetch comments for a Reddit post via PullPush.

    Returns list of comment dicts with 'body', 'author', 'score', etc.
    """
    _rate_limit()
    url = f"{API_BASE}/search/comment/"
    params = {
        "link_id": post_id,
        "size": min(size, 100),
        "sort": "score",
        "order": "desc",
    }

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"    [!] PullPush comments failed for post {post_id}: {e}")
        return []

    return data.get("data", [])


def extract_post_fields(post: dict) -> dict:
    """Extract useful fields from a PullPush post response."""
    return {
        "title": post.get("title", ""),
        "selftext": post.get("selftext", ""),
        "author": post.get("author", ""),
        "created_utc": post.get("created_utc", ""),
        "subreddit": post.get("subreddit", ""),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
        "permalink": post.get("permalink", ""),
        "url": post.get("url", ""),
    }
