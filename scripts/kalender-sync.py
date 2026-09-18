#!/usr/bin/env python3
"""Kalender sync scaffold.

This intentionally does not contain OAuth credentials. It provides the stable
normalized cache contract consumed by the QML plugin and is ready for the
Google Calendar OAuth/API implementation in the next phase.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def cache_path() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "kalender" / "events.json"


def write_cache(events: list[dict], path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }
    fd, tmp = tempfile.mkstemp(prefix="events.", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, help="write a fixture JSON array")
    parser.add_argument("--cache", type=Path, default=cache_path())
    args = parser.parse_args()

    events = []
    if args.fixture:
        with args.fixture.open(encoding="utf-8") as handle:
            events = json.load(handle)
        if not isinstance(events, list):
            raise SystemExit("fixture must contain a JSON array")

    write_cache(events, args.cache)
    print(args.cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
