"""Backup directory helpers."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "Backups"
LOGS_DIR = ROOT / "Logs"
BACKUP_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

_STATE_FILE = BACKUP_DIR / "state.json"


def _load() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def record(key: str, value) -> None:
    state = _load()
    if key not in state:
        state[key] = {"original": value, "ts": time.time()}
        _save(state)


def get_original(key: str):
    return _load().get(key, {}).get("original")