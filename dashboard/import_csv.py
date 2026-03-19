"""Import existing CSV files into SQLite database."""

import csv
import glob
import os
import re
from dashboard.config import BASE_DIR
from dashboard.database import init_db, get_db


def parse_bool(val):
    """Convert CSV string to bool."""
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


def extract_post_id_from_url(url):
    """Extract Reddit post ID from URL."""
    match = re.search(r"/comments/([a-z0-9]+)", url)
    return match.group(1) if match else None


def extract_subreddit_from_url(url):
    """Extract subreddit from URL."""
    match = re.search(r"/r/([^/]+)", url)
    return match.group(1) if match else None


def import_csv_file(csv_path, conn):
    """Import a single CSV file into signals table."""
    imported = 0
    skipped = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").strip()
            if not url:
                skipped += 1
                continue

            # Extract post_id and subreddit from URL
            post_id = extract_post_id_from_url(url)
            subreddit = row.get("subreddit", "") or extract_subreddit_from_url(url)

            try:
                conn.execute("""
                    INSERT OR IGNORE INTO signals (
                        query, url, post_id, subreddit, title, body, text_snippet,
                        created_at_raw, author_raw, scraped_success, scrape_error,
                        is_question, mentions_parent_context, mentions_child,
                        child_age_signal, location_signal, activity_type_signal,
                        pain_signal, intent_signal, relevance_score, why_relevant,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
                """, (
                    row.get("query", ""),
                    url,
                    post_id,
                    subreddit,
                    row.get("title", ""),
                    row.get("body", ""),
                    row.get("text_snippet", ""),
                    row.get("created_at_raw", ""),
                    row.get("author_raw", ""),
                    parse_bool(row.get("scraped_success", True)),
                    row.get("scrape_error", ""),
                    parse_bool(row.get("is_question", False)),
                    parse_bool(row.get("mentions_parent_context", False)),
                    parse_bool(row.get("mentions_child", False)),
                    row.get("child_age_signal", ""),
                    row.get("location_signal", ""),
                    row.get("activity_type_signal", ""),
                    row.get("pain_signal", ""),
                    row.get("intent_signal", ""),
                    int(row.get("relevance_score", 0) or 0),
                    row.get("why_relevant", ""),
                ))
                imported += 1
            except Exception as e:
                print(f"  Error importing {url}: {e}")
                skipped += 1

    return imported, skipped


def main():
    """Import all CSV files from output/ into SQLite."""
    init_db()

    output_dir = BASE_DIR / "output"
    csv_files = sorted(glob.glob(str(output_dir / "*.csv")))

    if not csv_files:
        print("No CSV files found in output/")
        return

    total_imported = 0
    total_skipped = 0

    with get_db() as conn:
        for csv_path in csv_files:
            filename = os.path.basename(csv_path)
            imported, skipped = import_csv_file(csv_path, conn)
            total_imported += imported
            total_skipped += skipped
            print(f"  {filename}: imported={imported}, skipped/dupes={skipped}")

    print(f"\nTotal: imported={total_imported}, skipped={total_skipped}")

    # Show counts
    from dashboard.database import query_one
    counts = query_one("SELECT COUNT(*) as total, SUM(CASE WHEN intent_signal='high' THEN 1 ELSE 0 END) as high FROM signals")
    print(f"Database: {counts['total']} signals, {counts['high']} high intent")


if __name__ == "__main__":
    main()
