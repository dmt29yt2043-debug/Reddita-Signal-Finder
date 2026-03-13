"""Upload CSV results to Google Sheets via Service Account."""

import os
import csv
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "..", "service_account.json")
SPREADSHEET_NAME = "Reddit Signal Finder — Results"
# If set in .env, use this existing spreadsheet instead of creating new
SPREADSHEET_ID_ENV = os.getenv("GOOGLE_SPREADSHEET_ID", "")


def get_credentials():
    """Load service account credentials."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Service account JSON not found: {SERVICE_ACCOUNT_FILE}\n"
            "Download it from Google Cloud Console and place in project root."
        )
    return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)


def find_or_create_spreadsheet(drive_service, sheets_service, name: str) -> str:
    """Find existing spreadsheet by name or create a new one. Returns spreadsheet ID."""
    # Search for existing
    query = f"name='{name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        sheet_id = files[0]["id"]
        print(f"  Found existing spreadsheet: {name} ({sheet_id})")
        return sheet_id

    # Create new via Drive API (more reliable for service accounts)
    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    file = drive_service.files().create(body=file_metadata, fields="id").execute()
    sheet_id = file["id"]
    print(f"  Created new spreadsheet: {name} ({sheet_id})")
    return sheet_id


def share_spreadsheet(drive_service, spreadsheet_id: str, email: str):
    """Share spreadsheet with a user email for viewing/editing."""
    try:
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={"type": "user", "role": "writer", "emailAddress": email},
            sendNotificationEmail=False,
        ).execute()
        print(f"  Shared with: {email}")
    except Exception as e:
        print(f"  [!] Could not share with {email}: {e}")


def make_public_link(drive_service, spreadsheet_id: str):
    """Make spreadsheet viewable by anyone with the link."""
    try:
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        print(f"  Made public (anyone with link can view)")
    except Exception as e:
        print(f"  [!] Could not make public: {e}")


def csv_to_sheet_data(csv_path: str) -> list[list[str]]:
    """Read a CSV file and return as list of rows (including header)."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows


def upload_to_sheet(sheets_service, spreadsheet_id: str, sheet_name: str, data: list[list[str]]):
    """Write data to a named sheet tab. Creates the tab if needed, clears existing data."""
    # Get existing sheet names
    meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_sheets = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if sheet_name not in existing_sheets:
        # Add new sheet tab
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()

    # Clear existing data
    range_name = f"'{sheet_name}'!A:Z"
    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=range_name,
    ).execute()

    # Write new data
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": data},
    ).execute()

    print(f"  Uploaded {len(data)-1} rows to tab '{sheet_name}'")


def upload_results(all_csv: str, priority_csv: str, share_email: str = None):
    """Main function: upload both CSVs to Google Sheets.

    Args:
        all_csv: path to reddit_signals.csv
        priority_csv: path to reddit_signals_priority.csv
        share_email: optional email to share the spreadsheet with
    """
    print("\n--- Uploading to Google Sheets ---\n")

    creds = get_credentials()
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Use existing spreadsheet from .env or find/create
    if SPREADSHEET_ID_ENV:
        spreadsheet_id = SPREADSHEET_ID_ENV
        print(f"  Using spreadsheet from .env: {spreadsheet_id}")
    else:
        spreadsheet_id = find_or_create_spreadsheet(drive_service, sheets_service, SPREADSHEET_NAME)

    # Upload all results
    if os.path.exists(all_csv):
        all_data = csv_to_sheet_data(all_csv)
        upload_to_sheet(sheets_service, spreadsheet_id, "All Results", all_data)

    # Upload priority results
    if os.path.exists(priority_csv):
        priority_data = csv_to_sheet_data(priority_csv)
        upload_to_sheet(sheets_service, spreadsheet_id, "Priority", priority_data)

    # Remove default Sheet1 if it exists and we have other tabs
    try:
        meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets_list = meta.get("sheets", [])
        if len(sheets_list) > 2:
            for s in sheets_list:
                if s["properties"]["title"] == "Sheet1":
                    sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body={"requests": [{"deleteSheet": {"sheetId": s["properties"]["sheetId"]}}]},
                    ).execute()
                    break
    except Exception:
        pass

    # Share if email provided
    if share_email:
        share_spreadsheet(drive_service, spreadsheet_id, share_email)

    # Make viewable with link
    make_public_link(drive_service, spreadsheet_id)

    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    print(f"\n  Google Sheets URL: {url}")
    return url
