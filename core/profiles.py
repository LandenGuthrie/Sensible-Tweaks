"""Named per-section profile save/restore.

Layout:
    Backups/profiles/network/My Gaming Setup.json
    Backups/profiles/fps/Competitive.json
    Backups/profiles/fortnite/Max FPS.json
"""
import json
import re
from datetime import datetime
from pathlib import Path

from . import backup

PROFILE_ROOT = backup.BACKUP_DIR / "profiles"
PROFILE_ROOT.mkdir(exist_ok=True)

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str) -> str:
    name = _INVALID.sub("_", name).strip().rstrip(".")
    return name[:80] or "Unnamed"


def _section_dir(section: str) -> Path:
    d = PROFILE_ROOT / section
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(section: str, name: str) -> Path:
    return _section_dir(section) / f"{_sanitize(name)}.json"


def list_profiles(section: str):
    """Returns list of (name, saved_at) sorted newest first."""
    d = _section_dir(section)
    items = []
    for f in d.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items.append((f.stem, data.get("saved_at", "")))
        except Exception:
            items.append((f.stem, ""))
    items.sort(key=lambda x: x[1], reverse=True)
    return items


def has_profile(section: str, name: str) -> bool:
    return _path(section, name).exists()


def saved_at(section: str, name: str):
    p = _path(section, name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("saved_at")
    except Exception:
        return None


def save_profile(section: str, name: str, tweaks, adapter=None) -> bool:
    from tweaks.base import TweakContext
    ctx = TweakContext(adapter=adapter)

    data = {
        "section": section,
        "name": _sanitize(name),
        "saved_at": datetime.now().isoformat(),
        "adapter": adapter.name if adapter else None,
        "adapter_guid": adapter.if_guid if adapter else None,
        "tweaks": {},
    }
    for t in tweaks:
        key = f"{t.id}.{t.name}"
        try:
            snap = t.snapshot(ctx)
        except Exception as e:
            snap = {"__error__": str(e)}
        data["tweaks"][key] = {"id": t.id, "name": t.name, "snapshot": snap}

    _path(section, name).write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    return True


def restore_profile(section: str, name: str, tweaks, adapter=None):
    """Returns (restored_count, total_count)."""
    p = _path(section, name)
    if not p.exists():
        return 0, len(tweaks)

    from tweaks.base import TweakContext
    data = json.loads(p.read_text(encoding="utf-8"))
    ctx = TweakContext(adapter=adapter)

    restored = 0
    for t in tweaks:
        key = f"{t.id}.{t.name}"
        entry = data.get("tweaks", {}).get(key)
        if not entry:
            continue
        snap = entry.get("snapshot", {})
        if "__error__" in snap:
            continue
        try:
            if t.restore(ctx, snap):
                restored += 1
        except Exception:
            pass
    return restored, len(tweaks)


def delete_profile(section: str, name: str) -> bool:
    p = _path(section, name)
    if p.exists():
        p.unlink()
        return True
    return False


def profile_meta(section: str, name: str) -> dict:
    """Return the header fields of a profile without loading the tweaks."""
    p = _path(section, name)
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {
            "name": d.get("name", name),
            "saved_at": d.get("saved_at", ""),
            "adapter": d.get("adapter", ""),
        }
    except Exception:
        return {}