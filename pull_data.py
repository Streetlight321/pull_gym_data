"""Pull gym data from a Google Sheet into output.csv and a Supabase Postgres table."""

import csv
import json
import os
import time
import uuid
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

RETRY_DELAYS = (10, 30, 60)
RETRYABLE_STATUS_CODES = {429, 500, 503}
CHUNK_SIZE = 500

# Sheet header -> Postgres column. Order here defines the CSV column order too.
COLUMN_MAP = [
    ("Date", "workout_date"),
    ("Day", "day"),
    ("Exercises", "exercise"),
    ("Set #", "set_num"),
    ("Weight", "weight"),
    ("# of Reps", "reps"),
    ("Volume", "volume"),
    ("Notes", "notes"),
]

DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y")


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

def fetch_all_values(ws):
    for attempt, delay in enumerate(RETRY_DELAYS, start=1):
        try:
            return ws.get_all_values()
        except gspread.exceptions.APIError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status not in RETRYABLE_STATUS_CODES:
                raise
            print(f"gspread APIError {status} on attempt {attempt}; retrying in {delay}s")
            time.sleep(delay)
    return ws.get_all_values()


def read_sheet():
    creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    return fetch_all_values(spreadsheet.sheet1)


# ---------------------------------------------------------------------------
# Parsing: the sheet gives us strings; Postgres wants real types
# ---------------------------------------------------------------------------

def parse_date(value):
    v = (value or "").strip()
    if not v:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {value!r}")


def parse_number(value):
    v = (value or "").replace(",", "").replace("$", "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        print(f"  warning: could not parse number {value!r}, storing NULL")
        return None


def parse_int(value):
    n = parse_number(value)
    return None if n is None else int(round(n))


def parse_text(value):
    return (value or "").strip() or None


def to_records(rows):
    """Turn raw sheet values into typed dicts ready for Postgres."""
    if not rows:
        return []

    header = [h.strip() for h in rows[0]]
    index = {}
    for sheet_name, column in COLUMN_MAP:
        if sheet_name not in header:
            raise KeyError(
                f"Column {sheet_name!r} missing from sheet. Found: {header}"
            )
        index[column] = header.index(sheet_name)

    records = []
    skipped = 0
    # start=2 because row 1 is the header, so this is the true sheet row number
    for sheet_row, row in enumerate(rows[1:], start=2):
        if not any((cell or "").strip() for cell in row):
            continue

        def cell(column):
            i = index[column]
            return row[i] if i < len(row) else ""

        workout_date = parse_date(cell("workout_date"))
        exercise = parse_text(cell("exercise"))
        if workout_date is None or exercise is None:
            skipped += 1
            continue

        records.append({
            "sheet_row": sheet_row,
            "workout_date": workout_date,
            "day": parse_text(cell("day")),
            "exercise": exercise,
            "set_num": parse_int(cell("set_num")),
            "weight": parse_number(cell("weight")),
            "reps": parse_int(cell("reps")),
            "volume": parse_number(cell("volume")),
            "notes": parse_text(cell("notes")),
        })

    if skipped:
        print(f"Skipped {skipped} row(s) missing a date or exercise")
    return records


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def push_to_supabase(records):
    """Replace the table contents with this run's snapshot.

    Insert every row tagged with a fresh sync_id, then delete everything that
    doesn't carry it. If the insert phase fails partway through, the partial
    batch is removed and the previous snapshot is left untouched.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    table = os.environ.get("SUPABASE_TABLE", "gym_sets")

    if not url or not key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set - skipping Supabase export")
        return
    if not records:
        print("No records parsed - refusing to wipe the Supabase table")
        return

    from supabase import create_client

    client = create_client(url, key)
    sync_id = str(uuid.uuid4())
    payload = [dict(r, sync_id=sync_id) for r in records]

    try:
        for i in range(0, len(payload), CHUNK_SIZE):
            chunk = payload[i:i + CHUNK_SIZE]
            client.table(table).insert(chunk, returning="minimal").execute()
            print(f"  inserted rows {i + 1}-{i + len(chunk)}")
    except Exception:
        print("Insert failed - rolling back this run's partial batch")
        client.table(table).delete(returning="minimal").eq("sync_id", sync_id).execute()
        raise

    client.table(table).delete(returning="minimal").neq("sync_id", sync_id).execute()
    print(f"Supabase export complete -> {table} ({len(payload)} rows, sync {sync_id})")


# ---------------------------------------------------------------------------

def write_csv(rows, path="new_output.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"Export complete -> {path}")


def main():
    load_dotenv()
    rows = read_sheet()
    write_csv(rows)
    push_to_supabase(to_records(rows))


if __name__ == "__main__":
    main()
