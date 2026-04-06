# Pull Gym Data

Pulls data from a Google Sheet and exports it to `output.csv`. Runs daily via GitHub Actions.

## Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_CREDENTIALS_JSON` | Full JSON content of your Google service account credentials file (single-line string) |
| `GOOGLE_SHEET_ID` | The Google Sheet ID from the spreadsheet URL |

## Local Setup

1. Copy `.env.example` to `.env` and fill in the values:
   ```
   cp .env.example .env
   ```
2. Paste your full `credentials.json` content into `GOOGLE_CREDENTIALS_JSON` as a single line.
3. Set `GOOGLE_SHEET_ID` to your sheet ID.
4. Install dependencies and run:
   ```
   pip install -r requirements.txt
   python pull_data.py
   ```

## Scheduled Workflow

The GitHub Actions workflow (`.github/workflows/pull_data.yml`) runs daily at **12:00 AM EST (05:00 UTC)**. It can also be triggered manually from the Actions tab.

The workflow commits updated `output.csv` back to the repo automatically.

## GitHub Secrets

Add these in **Settings → Secrets and variables → Actions**:

- `GOOGLE_CREDENTIALS_JSON` — the full JSON content of your service account credentials file
- `GOOGLE_SHEET_ID` — your Google Sheet ID
