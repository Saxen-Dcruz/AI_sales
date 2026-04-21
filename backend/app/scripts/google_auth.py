"""
One-time OAuth2 handshake script.
Generates gmail_token.json and calendar_token.json from client_secrets.json.

Run locally (NOT inside Docker):
    cd backend
    python app/scripts/google_auth.py

For remote/headless servers (no browser):
    python app/scripts/google_auth.py --no-browser
"""

import argparse
import os
import pickle
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/

CLIENT_SECRETS = BASE_DIR / "client_secrets.json"
GMAIL_TOKEN = BASE_DIR / "gmail_token.json"
CALENDAR_TOKEN = BASE_DIR / "calendar_token.json"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def generate_token(scopes: list[str], token_path: Path, no_browser: bool, port: int = 8080) -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), scopes)

    if no_browser:
        creds = flow.run_console()
    else:
        creds = flow.run_local_server(port=port)

    with open(token_path, "wb") as f:
        pickle.dump(creds, f)

    print(f"Token saved: {token_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Use console-based auth (for remote/headless servers)",
    )
    args = parser.parse_args()

    if not CLIENT_SECRETS.exists():
        raise FileNotFoundError(f"client_secrets.json not found at {CLIENT_SECRETS}")

    print("--- Authorizing Gmail ---")
    generate_token(GMAIL_SCOPES, GMAIL_TOKEN, args.no_browser, port=8080)

    print("--- Authorizing Google Calendar ---")
    generate_token(CALENDAR_SCOPES, CALENDAR_TOKEN, args.no_browser, port=8081)

    print("Done. Both token files created.")


if __name__ == "__main__":
    main()
