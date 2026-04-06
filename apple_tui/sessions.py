"""
Persistent session storage.

Sessions are saved as JSON to ~/.config/apple-tui/sessions/<date>-<n>.json
and restored on next launch so conversation history survives restarts.
"""

import json
import os
from datetime import date
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "apple-tui"
SESSIONS_DIR = CONFIG_DIR / "sessions"


def _sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _today_path() -> Path:
    """Return path for today's session file, auto-incrementing if needed."""
    today = date.today().isoformat()
    base = _sessions_dir()
    n = 1
    while True:
        p = base / f"{today}-{n}.json"
        if not p.exists():
            return p
        n += 1


def save_transcript(transcript_data: dict, name: str | None = None) -> Path:
    """Write transcript dict to disk. Returns the path written.

    If name is given, writes to <name>.json (overwrites). Otherwise uses a
    date-based filename.
    """
    if name is not None:
        path = _sessions_dir() / f"{name}.json"
    else:
        path = _today_path()
    path.write_text(json.dumps(transcript_data, indent=2), encoding="utf-8")
    return path


def load_transcript(name: str | None = None) -> dict | None:
    """Load a session by name, or the most recently modified session if name is None."""
    base = _sessions_dir()
    if name is not None:
        path = base / f"{name}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    files = sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_transcript() -> dict | None:
    """Load the most recently modified session file, or None if none exist."""
    return load_transcript()


def list_sessions() -> list[Path]:
    """Return all session files sorted newest first."""
    base = _sessions_dir()
    return sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
