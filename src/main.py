"""Reddit Signal Finder — main pipeline.

Usage:
    python src/main.py
    python src/main.py --max-results-per-query 5 --max-total-posts 50

Pipeline:
    1. Firecrawl search → find Reddit post URLs
    2. PullPush.io → fetch full post content + top comments
    3. Extract signals (keywords, regex)
    4. Score relevance (0-100)
    5. Save to CSV
    6. Upload to Google Sheets
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from firecrawl_client import search_reddit
from pullpush_client import fetch_post_by_id, fetch_comments, extract_post_fields
from extractor import extract_signals
from scorer import calculate_relevance_score, determine_intent, build_why_relevant
from utils import (
    extract_subreddit,
    extract_post_id,
    clean_text,
    make_snippet,
    deduplicate_by_url,
)


# --- Config ---
DEFAULT_MAX_RESULTS_PER_QUERY = 10
DEFAULT_MAX_TOTAL_POSTS = 100
TOP_COMMENTS_COUNT = 10
PRIORITY_SCORE_THRESHOLD = 70
QUERIES_FILE = os.path.join(os.path.dirname(__file__), "..", "queries.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

CSV_COLUMNS = [
    "query", "url", "subreddit", "title", "body", "text_snippet",
    "created_at_raw", "author_raw", "scraped_success", "scrape_error",
    "is_question", "mentions_parent_context", "mentions_child",
    "child_age_signal", "location_signal", "activity_type_signal",
    "pain_signal", "intent_signal", "relevance_score", "why_relevant",
]


def load_queries() -> list[str]:
    """Load search queries from queries.json."""
    with open(QUERIES_FILE, "r") as f:
        queries = json.load(f)
    return queries


def format_utc_timestamp(ts) -> str:
    """Convert a Unix timestamp to readable date string."""
    if not ts:
        return ""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError, OSError):
        return str(ts)


def process_post(url: str, query: str, search_title: str, search_description: str) -> dict:
    """Process a single Reddit post: fetch full content via PullPush, extract signals, score.

    Falls back to Firecrawl search snippet if PullPush has no data.
    """
    post_id = extract_post_id(url)

    row = {
        "query": query,
        "url": url,
        "subreddit": extract_subreddit(url),
        "title": "",
        "body": "",
        "text_snippet": "",
        "created_at_raw": "",
        "author_raw": "",
        "scraped_success": True,
        "scrape_error": "",
    }

    title = ""
    body_parts = []

    # Try PullPush for full content
    if post_id:
        post_data = fetch_post_by_id(post_id)

        if post_data:
            fields = extract_post_fields(post_data)
            title = fields["title"]
            selftext = fields["selftext"]

            # Skip deleted/removed content markers
            if selftext and selftext not in ("[deleted]", "[removed]"):
                body_parts.append(selftext)

            row["author_raw"] = fields["author"]
            row["created_at_raw"] = format_utc_timestamp(fields["created_utc"])
            row["subreddit"] = fields["subreddit"] or row["subreddit"]

            # Fetch top comments for richer signal extraction
            comments = fetch_comments(post_id, size=TOP_COMMENTS_COUNT)
            for comment in comments:
                comment_body = comment.get("body", "")
                if comment_body and comment_body not in ("[deleted]", "[removed]"):
                    body_parts.append(comment_body)

            print(f"    PullPush: title + {len(body_parts)} text blocks")
        else:
            print(f"    PullPush: no data, using search snippet")

    # Fallback to Firecrawl search data if PullPush returned nothing
    if not title:
        title = search_title
    if not body_parts and search_description:
        body_parts.append(search_description)

    if not title and not body_parts:
        row["scraped_success"] = False
        row["scrape_error"] = "no content from PullPush or search"

    # Build full body text
    body = clean_text("\n\n".join(body_parts))
    row["title"] = clean_text(title)
    row["body"] = body
    row["text_snippet"] = make_snippet(body)

    # Extract signals from title + full body (post text + comments)
    signals = extract_signals(row["title"], body)
    row.update({
        "is_question": signals["is_question"],
        "mentions_parent_context": signals["mentions_parent_context"],
        "mentions_child": signals["mentions_child"],
        "child_age_signal": signals["child_age_signal"],
        "location_signal": signals["location_signal"],
        "activity_type_signal": signals["activity_type_signal"],
        "pain_signal": signals["pain_signal"],
    })

    # Score
    score = calculate_relevance_score(signals, has_body=bool(body))
    intent = determine_intent(score)
    why = build_why_relevant(signals, score)

    row["relevance_score"] = score
    row["intent_signal"] = intent
    row["why_relevant"] = why

    return row


def save_csv(rows: list[dict], filepath: str):
    """Save rows to a CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Reddit Signal Finder")
    parser.add_argument("--max-results-per-query", type=int,
                        default=DEFAULT_MAX_RESULTS_PER_QUERY)
    parser.add_argument("--max-total-posts", type=int,
                        default=DEFAULT_MAX_TOTAL_POSTS)
    parser.add_argument("--no-sheets", action="store_true",
                        help="Skip Google Sheets upload")
    parser.add_argument("--share-email", type=str, default=None,
                        help="Email to share Google Sheet with")
    args = parser.parse_args()

    print("=" * 60)
    print("  Reddit Signal Finder")
    print("=" * 60)

    # Load queries
    queries = load_queries()
    print(f"\nLoaded {len(queries)} search queries from queries.json")

    # Phase 1: Search for Reddit URLs via Firecrawl
    print("\n--- Phase 1: Searching for Reddit posts (Firecrawl) ---\n")
    all_results = []

    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] Searching: '{query}'")
        results = search_reddit(query, limit=args.max_results_per_query)
        print(f"  Found {len(results)} Reddit post URLs")

        for r in results:
            all_results.append({
                "url": r["url"],
                "query": query,
                "title": r.get("title", ""),
                "description": r.get("description", ""),
            })

        # Small delay between searches
        if i < len(queries):
            time.sleep(1)

    print(f"\nTotal URLs found (before dedup): {len(all_results)}")

    # Deduplicate
    unique_results = deduplicate_by_url(all_results)
    print(f"Unique URLs after dedup: {len(unique_results)}")

    # Limit total posts
    if len(unique_results) > args.max_total_posts:
        print(f"Limiting to {args.max_total_posts} posts")
        unique_results = unique_results[:args.max_total_posts]

    # Phase 2: Fetch full content via PullPush + extract signals
    print(f"\n--- Phase 2: Fetching content & scoring ({len(unique_results)} posts via PullPush) ---\n")
    all_rows = []

    for i, item in enumerate(unique_results, 1):
        print(f"[{i}/{len(unique_results)}] {item['url']}")
        try:
            row = process_post(
                url=item["url"],
                query=item["query"],
                search_title=item.get("title", ""),
                search_description=item.get("description", ""),
            )
            all_rows.append(row)
        except Exception as e:
            print(f"  [!] Error: {e}")
            all_rows.append({
                "query": item["query"],
                "url": item["url"],
                "scraped_success": False,
                "scrape_error": str(e),
                **{k: "" for k in CSV_COLUMNS if k not in ["query", "url", "scraped_success", "scrape_error"]},
            })

    # Phase 3: Save results
    print(f"\n--- Phase 3: Saving results ---\n")

    all_csv = os.path.join(OUTPUT_DIR, "reddit_signals.csv")
    save_csv(all_rows, all_csv)
    print(f"Saved all results: {all_csv}")

    # Priority: high intent or score >= threshold
    priority_rows = [
        r for r in all_rows
        if r.get("intent_signal") == "high" or r.get("relevance_score", 0) >= PRIORITY_SCORE_THRESHOLD
    ]
    priority_csv = os.path.join(OUTPUT_DIR, "reddit_signals_priority.csv")
    save_csv(priority_rows, priority_csv)
    print(f"Saved priority results: {priority_csv}")

    # Summary
    high_count = sum(1 for r in all_rows if r.get("intent_signal") == "high")
    medium_count = sum(1 for r in all_rows if r.get("intent_signal") == "medium")
    success_count = sum(1 for r in all_rows if r.get("scraped_success"))

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Queries processed:     {len(queries)}")
    print(f"  URLs found (raw):      {len(all_results)}")
    print(f"  Unique posts:          {len(unique_results)}")
    print(f"  With full content:     {success_count}")
    print(f"  High intent:           {high_count}")
    print(f"  Medium intent:         {medium_count}")
    print(f"  Priority posts:        {len(priority_rows)}")
    print(f"\n  All results:      {all_csv}")
    print(f"  Priority results: {priority_csv}")
    print("=" * 60)

    # Phase 4: Upload to Google Sheets
    if not args.no_sheets:
        try:
            from sheets_uploader import upload_results
            sheet_url = upload_results(all_csv, priority_csv, share_email=args.share_email)
            print(f"\n  Google Sheets: {sheet_url}")
        except FileNotFoundError as e:
            print(f"\n  [!] Sheets upload skipped: {e}")
        except Exception as e:
            print(f"\n  [!] Sheets upload failed: {e}")
            print("  CSV files are still saved locally.")


if __name__ == "__main__":
    main()
