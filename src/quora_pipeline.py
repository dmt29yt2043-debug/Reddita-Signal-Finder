"""Quora Signal Finder — search Quora for relevant parent posts via Firecrawl.

Usage:
    python src/quora_pipeline.py
    python src/quora_pipeline.py --max-results-per-query 5 --max-total-posts 10
"""

import argparse
import csv
import json
import os
import re
import time
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from firecrawl_client import get_api_key, _headers, API_BASE
from extractor import extract_signals
from scorer import calculate_relevance_score, determine_intent, build_why_relevant
from utils import clean_text, make_snippet

import requests as http_requests

# --- Config ---
QUERIES_FILE = os.path.join(os.path.dirname(__file__), "..", "queries.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
PRIORITY_SCORE_THRESHOLD = 70

CSV_COLUMNS = [
    "query", "url", "source", "title", "body", "text_snippet",
    "is_question", "mentions_parent_context", "mentions_child",
    "child_age_signal", "location_signal", "activity_type_signal",
    "pain_signal", "intent_signal", "relevance_score", "why_relevant",
]

QUORA_URL_PATTERN = re.compile(r'https?://(?:www\.)?quora\.com/[^?\s]+')


def is_quora_url(url: str) -> bool:
    """Check if URL is a Quora question/answer page."""
    parsed = urlparse(url)
    return "quora.com" in parsed.netloc and len(parsed.path) > 1


def search_quora(query: str, limit: int = 10) -> list[dict]:
    """Search for Quora results via Firecrawl."""
    url = f"{API_BASE}/search"
    payload = {"query": query, "limit": limit}

    try:
        resp = http_requests.post(url, json=payload, headers=_headers(), timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except http_requests.RequestException as e:
        print(f"  [!] Search failed for '{query}': {e}")
        return []

    if not data.get("success"):
        print(f"  [!] Search not successful for '{query}': {data}")
        return []

    results = []
    for item in data.get("data", []):
        item_url = item.get("url", "")
        if is_quora_url(item_url):
            results.append({
                "url": item_url.split("?")[0],  # strip tracking params
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "markdown": item.get("markdown", ""),
            })

    return results


def process_quora_post(url: str, query: str, title: str, description: str, markdown: str) -> dict:
    """Process a single Quora result: extract signals, score."""
    # Use markdown if available (richer), otherwise description
    body = clean_text(markdown) if markdown else clean_text(description)

    row = {
        "query": query,
        "url": url,
        "source": "quora",
        "title": clean_text(title),
        "body": body,
        "text_snippet": make_snippet(body),
    }

    # Extract signals
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


def deduplicate_by_url(posts: list[dict]) -> list[dict]:
    """Remove duplicate posts by URL."""
    seen = set()
    unique = []
    for post in posts:
        url = post.get("url", "").split("?")[0]
        if url not in seen:
            seen.add(url)
            unique.append(post)
    return unique


def save_csv(rows: list[dict], filepath: str):
    """Save rows to CSV."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Quora Signal Finder")
    parser.add_argument("--max-results-per-query", type=int, default=5)
    parser.add_argument("--max-total-posts", type=int, default=10)
    parser.add_argument("--no-sheets", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  Quora Signal Finder")
    print("=" * 60)

    # Load same queries but replace "reddit" with "quora"
    with open(QUERIES_FILE, "r") as f:
        queries = json.load(f)

    quora_queries = [q.replace(" reddit", " quora") + " 2025" for q in queries]
    print(f"\nLoaded {len(quora_queries)} search queries")

    # Phase 1: Search
    print("\n--- Phase 1: Searching Quora posts (Firecrawl) ---\n")
    all_results = []

    for i, query in enumerate(quora_queries, 1):
        print(f"[{i}/{len(quora_queries)}] Searching: '{query}'")
        results = search_quora(query, limit=args.max_results_per_query)
        print(f"  Found {len(results)} Quora URLs")

        for r in results:
            all_results.append({**r, "query": query})

        if i < len(quora_queries):
            time.sleep(1)

        # Stop early if we have enough
        if len(all_results) >= args.max_total_posts * 2:
            print(f"\n  Enough results found, stopping search early")
            break

    print(f"\nTotal URLs found: {len(all_results)}")

    unique_results = deduplicate_by_url(all_results)
    print(f"Unique URLs after dedup: {len(unique_results)}")

    if len(unique_results) > args.max_total_posts:
        unique_results = unique_results[:args.max_total_posts]
        print(f"Limiting to {args.max_total_posts} posts")

    # Phase 2: Extract signals & score
    print(f"\n--- Phase 2: Extracting signals ({len(unique_results)} posts) ---\n")
    all_rows = []

    for i, item in enumerate(unique_results, 1):
        print(f"[{i}/{len(unique_results)}] {item['url'][:80]}")
        row = process_quora_post(
            url=item["url"],
            query=item["query"],
            title=item.get("title", ""),
            description=item.get("description", ""),
            markdown=item.get("markdown", ""),
        )
        all_rows.append(row)

    # Phase 3: Save
    print(f"\n--- Phase 3: Saving results ---\n")

    all_csv = os.path.join(OUTPUT_DIR, "quora_signals.csv")
    save_csv(all_rows, all_csv)
    print(f"Saved all results: {all_csv}")

    priority_rows = [
        r for r in all_rows
        if r.get("intent_signal") == "high" or r.get("relevance_score", 0) >= PRIORITY_SCORE_THRESHOLD
    ]
    priority_csv = os.path.join(OUTPUT_DIR, "quora_signals_priority.csv")
    save_csv(priority_rows, priority_csv)
    print(f"Saved priority results: {priority_csv}")

    # Summary
    high_count = sum(1 for r in all_rows if r.get("intent_signal") == "high")
    medium_count = sum(1 for r in all_rows if r.get("intent_signal") == "medium")

    print("\n" + "=" * 60)
    print("  QUORA SUMMARY")
    print("=" * 60)
    print(f"  Unique posts:    {len(unique_results)}")
    print(f"  High intent:     {high_count}")
    print(f"  Medium intent:   {medium_count}")
    print(f"  Priority posts:  {len(priority_rows)}")
    print("=" * 60)

    # Upload to Google Sheets — separate tabs
    if not args.no_sheets:
        try:
            from sheets_uploader import get_credentials, upload_to_sheet, csv_to_sheet_data
            from googleapiclient.discovery import build

            creds = get_credentials()
            sheets_service = build("sheets", "v4", credentials=creds)
            spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "")

            if spreadsheet_id:
                print("\n--- Uploading to Google Sheets ---\n")
                if os.path.exists(all_csv):
                    data = csv_to_sheet_data(all_csv)
                    upload_to_sheet(sheets_service, spreadsheet_id, "Quora — All", data)

                if os.path.exists(priority_csv) and priority_rows:
                    data = csv_to_sheet_data(priority_csv)
                    upload_to_sheet(sheets_service, spreadsheet_id, "Quora — Priority", data)

                url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
                print(f"\n  Google Sheets: {url}")
        except Exception as e:
            print(f"\n  [!] Sheets upload failed: {e}")


if __name__ == "__main__":
    main()
