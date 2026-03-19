"""Fetch created_utc dates for Reddit posts and update Google Sheets.

Reads URLs from the existing CSV, extracts post IDs, fetches dates
from PullPush API, updates CSV and re-uploads to Sheets sorted by date.
"""

import csv
import os
import sys
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from pullpush_client import fetch_post_by_id
from utils import extract_post_id


def update_csv_with_dates(csv_path: str) -> list[list[str]]:
    """Read CSV, fetch dates for each post, write back sorted by date."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Add created_date column if not present
    if "created_date" not in fieldnames:
        fieldnames = list(fieldnames) + ["created_date"]

    total = len(rows)
    print(f"  Processing {total} posts...")

    for i, row in enumerate(rows):
        url = row.get("url", "")
        post_id = extract_post_id(url)

        if not post_id:
            row["created_date"] = ""
            continue

        print(f"  [{i+1}/{total}] Fetching date for {post_id}...", end="", flush=True)

        try:
            post_data = fetch_post_by_id(post_id)
            if post_data and post_data.get("created_utc"):
                ts = int(post_data["created_utc"])
                dt = datetime.utcfromtimestamp(ts)
                row["created_date"] = dt.strftime("%Y-%m-%d")
                print(f" {row['created_date']}")
            else:
                row["created_date"] = ""
                print(" no date")
        except Exception as e:
            row["created_date"] = ""
            print(f" error: {e}")

    # Sort by date descending (newest first), empty dates at bottom
    rows.sort(key=lambda r: r.get("created_date", "") or "0000-00-00", reverse=True)

    # Write back
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved sorted CSV: {csv_path}")

    # Return as sheet data (list of lists)
    sheet_data = [fieldnames]
    for row in rows:
        sheet_data.append([row.get(col, "") for col in fieldnames])
    return sheet_data


def main():
    from sheets_uploader import get_credentials, upload_to_sheet
    from googleapiclient.discovery import build

    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")

    all_csv = os.path.join(output_dir, "reddit_signals.csv")
    priority_csv = os.path.join(output_dir, "reddit_signals_priority.csv")

    print("=== Fetching dates for All Results ===\n")
    all_data = update_csv_with_dates(all_csv)

    print("\n=== Fetching dates for Priority ===\n")
    priority_data = update_csv_with_dates(priority_csv)

    # Upload to Sheets
    sid = os.getenv("GOOGLE_SPREADSHEET_ID", "")
    if sid:
        print("\n=== Uploading to Google Sheets ===\n")
        creds = get_credentials()
        sheets = build("sheets", "v4", credentials=creds)

        upload_to_sheet(sheets, sid, "All Results", all_data)
        upload_to_sheet(sheets, sid, "Priority", priority_data)
        print("\nDone! Sheets updated and sorted by date (newest first).")
    else:
        print("\nNo GOOGLE_SPREADSHEET_ID set, skipping Sheets upload.")


if __name__ == "__main__":
    main()
