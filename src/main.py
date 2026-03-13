"""Reddit Signal Finder — main pipeline.

Usage:
    python src/main.py
    python src/main.py --max-results-per-query 5 --max-total-posts 50
"""

import argparse
import csv
import json
import os
import sys
import time

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from firecrawl_client import search_reddit
from extractor import extract_signals
from scorer import calculate_relevance_score, determine_intent, build_why_relevant
from utils import (
    extract_subreddit,
    clean_text,
    make_snippet,
    deduplicate_by_url,
)


# --- Config ---
DEFAULT_MAX_RESULTS_PER_QUERY = 10
DEFAULT_MAX_TOTAL_POSTS = 100
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


def process_post(url: str, query: str, search_title: str, description: str, markdown: str) -> dict:
    """Process a single Reddit post from search results, extract signals, score.

    Note: Firecrawl cannot scrape reddit.com directly.
    We use title + description from search results as our text content.
    If markdown is available (rare for Reddit), we use that too.
    """
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

    # Build body from available content
    title = clean_text(search_title)
    # Use markdown if available, otherwise description from search
    body_text = markdown if markdown else description
    body = clean_text(body_text)

    if not title and not body:
        row["scraped_success"] = False
        row["scrape_error"] = "no content returned from search"

    row["title"] = title
    row["body"] = body
    row["text_snippet"] = make_snippet(body)

    # Extract signals from title + body
    signals = extract_signals(title, body)
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
    args = parser.parse_args()

    print("=" * 60)
    print("  Reddit Signal Finder")
    print("=" * 60)

    # Load queries
    queries = load_queries()
    print(f"\nLoaded {len(queries)} search queries from queries.json")

    # Phase 1: Search for Reddit URLs
    print("\n--- Phase 1: Searching for Reddit posts ---\n")
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
                "markdown": r.get("markdown", ""),
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

    # Phase 2: Process each post
    print(f"\n--- Phase 2: Processing {len(unique_results)} posts ---\n")
    all_rows = []

    for i, item in enumerate(unique_results, 1):
        print(f"[{i}/{len(unique_results)}] Processing: {item['url']}")
        try:
            row = process_post(
                url=item["url"],
                query=item["query"],
                search_title=item.get("title", ""),
                description=item.get("description", ""),
                markdown=item.get("markdown", ""),
            )
            all_rows.append(row)
        except Exception as e:
            print(f"  [!] Error processing {item['url']}: {e}")
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
    print(f"  With content:          {success_count}")
    print(f"  High intent:           {high_count}")
    print(f"  Medium intent:         {medium_count}")
    print(f"  Priority posts:        {len(priority_rows)}")
    print(f"\n  All results:      {all_csv}")
    print(f"  Priority results: {priority_csv}")
    print("=" * 60)


if __name__ == "__main__":
    main()
