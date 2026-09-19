"""Per-section snapshot save/load. One JSON file per section."""
import json
from datetime import datetime
from pathlib import Path

from . import backup

SECTION_DIR = backup.BACKUP_DIR / "sections"
SECTION_DIR.mkdir(exist_ok=True)


def path_for(section: str) -> Path:
    return SECTION_DIR / f"{section}.json"


def has_save(section: str) -> bool:
    return path_for(section).exists()


def save(section: str, tweaks, adapter=None) -> bool:
    from tweaks.base import TweakContext
    ctx = TweakContext(adapter=adapter)

    data = {
        "section": section,
        "saved_at": datetime.now().isoformat(),
        "adapter": adapter.name if adapter else None,
        "adapter_guid": adapter.if_guid if adapter else None,
        "tweaks": {},
    }
    for t in tweaks:
        key = f"{t.id}.{t.name}"
        try:
            data["tweaks"][key] = {
                "id": t.id,
                "name": t.name,
                "snapshot": t.snapshot(ctx),
            }
        except Exception as e:
            data["tweaks"][key] = {"id": t.id, "name": t.name,
                                   "snapshot": {}, "error": str(e)}
    path_for(section).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def restore(section: str, tweaks, adapter=None) -> bool:
    if not has_save(section):
        return False
    from tweaks.base import TweakContext
    data = json.loads(path_for(section).read_text(encoding="utf-8"))
    ctx = TweakContext(adapter=adapter)
    for t in tweaks:
        key = f"{t.id}.{t.name}"
        entry = data.get("tweaks", {}).get(key)
        if not entry:
            continue
        t.restore(ctx, entry.get("snapshot", {}))
    return True


def saved_at(section: str) -> str | None:
    if not has_save(section):
        return None
    try:
        return json.loads(path_for(section).read_text(encoding="utf-8")).get("saved_at")
    except Exception:
        return None