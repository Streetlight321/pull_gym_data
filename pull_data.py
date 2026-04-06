import json
import os
import gspread
import csv
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

# Load Google service account credentials from env var (JSON string)
creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
creds_info = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
client = gspread.authorize(creds)

sheet_id = os.environ["GOOGLE_SHEET_ID"]

# Open the spreadsheet
spreadsheet = client.open_by_key(sheet_id)

# Select the first worksheet
worksheet = spreadsheet.sheet1

# Get all values (including header row)
data = worksheet.get_all_values()

# Write to CSV
with open("output.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(data)

print("Export complete -> output.csv")
