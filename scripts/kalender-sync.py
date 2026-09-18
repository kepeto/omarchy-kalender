#!/usr/bin/env python3
"""Google Calendar synchronizer for Kalender.

Uses only Python's standard library so it can run without installing packages.
OAuth credentials are supplied by the user and never copied into the plugin.
The normalized cache is consumed by QML at ~/.cache/kalender/events.json.
"""
from __future__ import annotations

import argparse
import getpass
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
CALENDAR_ENDPOINT = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


def cache_path() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kalender" / "events.json"


def state_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "kalender"


def load_json(path: Path, default=None):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, value: object, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def credentials(path: Path) -> tuple[str, str]:
    data = load_json(path, {}) or {}
    installed = data.get("installed", data.get("web", data))
    client_id = installed.get("client_id")
    client_secret = installed.get("client_secret")
    if not client_id or not client_secret:
        raise SystemExit(f"Invalid Google OAuth client file: {path}")
    return client_id, client_secret


def oauth_credentials(args) -> tuple[str, str]:
    """Resolve credentials from a file or secure interactive prompts."""
    if args.client_secret_file:
        return credentials(args.client_secret_file)
    client_id = args.client_id or input("Google OAuth Client ID: ").strip()
    if not client_id:
        raise SystemExit("Client ID cannot be empty")
    client_secret = args.client_secret or getpass.getpass("Google OAuth Client secret: ").strip()
    if not client_secret:
        raise SystemExit("Client secret cannot be empty")
    return client_id, client_secret


def post_form(url: str, values: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(values).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"Google OAuth HTTP {error.code}: {detail}") from error


def oauth(args) -> dict:
    client_id, client_secret = oauth_credentials(args)
    token_file = state_path() / "token.json"
    token = load_json(token_file, {}) or {}
    if token.get("refresh_token") and not args.reauthorize:
        refreshed = post_form(TOKEN_ENDPOINT, {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        })
        refreshed.setdefault("refresh_token", token["refresh_token"])
        token.update(refreshed)
        atomic_json(token_file, token)
        return token

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    code_holder: dict[str, str] = {}
    state = secrets.token_urlsafe(24)

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_error(400, "Invalid OAuth state")
                return
            code_holder["code"] = query.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Kalender authorization complete. You can close this tab.")

        def log_message(self, *_args):
            return

    server = http.server.HTTPServer(("127.0.0.1", port), Callback)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    redirect = f"http://127.0.0.1:{port}/oauth2callback"
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    url = f"{AUTH_ENDPOINT}?{query}"
    print(f"Authorize Kalender in your browser:\n{url}", flush=True)
    if not args.no_browser:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    thread.join(timeout=300)
    server.server_close()
    if not code_holder.get("code"):
        raise SystemExit("OAuth callback timed out or was cancelled")
    token = post_form(TOKEN_ENDPOINT, {
        "code": code_holder["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    })
    atomic_json(token_file, token)
    return token


def api_get(path: str, token: str, params: dict[str, str] | None = None) -> dict:
    url = CALENDAR_ENDPOINT + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"Google Calendar HTTP {error.code}: {detail}") from error


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_event(item: dict) -> dict | None:
    start = item.get("start", {})
    end = item.get("end", {})
    if "date" in start:
        return {
            "id": item.get("id", ""),
            "calendarId": item.get("calendarId", "primary"),
            "title": item.get("summary", "(untitled)"),
            "description": item.get("description", ""),
            "location": item.get("location", ""),
            "startDate": start["date"],
            "endDate": end.get("date", start["date"]),
            "allDay": True,
            "htmlLink": item.get("htmlLink", ""),
            "status": item.get("status", "confirmed"),
        }
    raw_start = start.get("dateTime")
    raw_end = end.get("dateTime")
    if not raw_start:
        return None
    return {
        "id": item.get("id", ""),
        "calendarId": item.get("calendarId", "primary"),
        "title": item.get("summary", "(untitled)"),
        "description": item.get("description", ""),
        "location": item.get("location", ""),
        "start": raw_start,
        "end": raw_end or raw_start,
        "allDay": False,
        "htmlLink": item.get("htmlLink", ""),
        "status": item.get("status", "confirmed"),
    }


def sync(args) -> int:
    token = oauth(args)
    now = datetime.now().astimezone()
    window_end = now + timedelta(days=args.days)
    events: list[dict] = []
    calendar_ids = args.calendar_id or ["primary"]
    for calendar_id in calendar_ids:
        page_token = None
        while True:
            params = {
                "singleEvents": "true",
                "orderBy": "startTime",
                "showDeleted": "false",
                "timeMin": iso_utc(now),
                "timeMax": iso_utc(window_end),
                "maxResults": "2500",
            }
            if page_token:
                params["pageToken"] = page_token
            data = api_get(f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events", token, params)
            for item in data.get("items", []):
                event = normalize_event({**item, "calendarId": calendar_id})
                if event and event.get("status") != "cancelled":
                    events.append(event)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    events.sort(key=lambda event: (event.get("startDate") or event.get("start") or "", event.get("title", "")))
    atomic_json(args.cache, {"version": 1, "updated": datetime.now(timezone.utc).isoformat(), "events": events})
    print(f"Synced {len(events)} events to {args.cache}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Google Calendar events for Kalender")
    credentials_group = parser.add_mutually_exclusive_group()
    credentials_group.add_argument("--client-secret-file", type=Path, help="Google OAuth client JSON (file mode)")
    credentials_group.add_argument("--client-id", help="Google OAuth client ID; omit to enter interactively")
    parser.add_argument("--client-secret", help="OAuth client secret; omit to enter securely with a hidden prompt")
    parser.add_argument("--reauthorize", action="store_true", help="Ignore saved token and run OAuth again")
    parser.add_argument("--calendar-id", action="append", help="Calendar ID; repeat for multiple calendars (default: primary)")
    parser.add_argument("--days", type=int, default=30, help="Days ahead to fetch (default: 30)")
    parser.add_argument("--cache", type=Path, default=cache_path())
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    return sync(args)


if __name__ == "__main__":
    raise SystemExit(main())
