"""Fortnite-specific tweaks."""
import json
import os
from pathlib import Path

from .base import Tweak
from core import shell
from core.shell import ps_quote


def _find_fortnite_root() -> Path | None:
    """Locate the Fortnite install folder via Epic Games Launcher manifests,
    falling back to the default install locations."""
    manifest_dir = (
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    )
    best = None
    if manifest_dir.is_dir():
        for f in manifest_dir.glob("*.item"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = str(data.get("DisplayName", "")).strip().lower()
            loc = data.get("InstallLocation")
            if not loc or not Path(loc).is_dir():
                continue
            if name == "fortnite":
                return Path(loc)
            if "fortnite" in name and best is None:
                best = Path(loc)
    if best:
        return best

    for candidate in (r"C:\Program Files\Epic Games\Fortnite",
                      r"C:\Program Files (x86)\Epic Games\Fortnite"):
        p = Path(candidate)
        if p.is_dir():
            return p
    return None


class DefenderExclusionTweak(Tweak):
    """Excludes the Fortnite install folder from Windows Defender real-time
    scanning, which otherwise re-scans shader/asset files on every read."""

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="fortnite")

    def _path(self) -> Path | None:
        return _find_fortnite_root()

    def _excluded_paths(self):
        ps = (
            "(Get-MpPreference).ExclusionPath | ConvertTo-Json -Compress"
        )
        out = shell.powershell(ps).stdout.strip()
        if not out:
            return []
        try:
            data = json.loads(out)
        except Exception:
            return []
        if isinstance(data, str):
            data = [data]
        return [p for p in data if p]

    def apply(self, ctx):
        root = self._path()
        if not root:
            return None
        ps = (
            f"try {{ Add-MpPreference -ExclusionPath '{ps_quote(str(root))}' "
            f"-ErrorAction Stop; 'OK' }} catch {{ 'FAIL' }}"
        )
        if "OK" not in shell.powershell(ps).stdout:
            return False
        return str(root).lower() in [p.lower() for p in self._excluded_paths()]

    def revert(self, ctx):
        root = self._path()
        if not root:
            return False
        ps = (
            f"Remove-MpPreference -ExclusionPath '{ps_quote(str(root))}' "
            f"-ErrorAction SilentlyContinue"
        )
        shell.powershell(ps)
        return str(root).lower() not in [p.lower() for p in self._excluded_paths()]

    def snapshot(self, ctx):
        root = self._path()
        if not root:
            return {}
        already = str(root).lower() in [p.lower() for p in self._excluded_paths()]
        return {"path": str(root), "already_excluded": already}

    def restore(self, ctx, snap):
        path = snap.get("path")
        if not path:
            return False
        if snap.get("already_excluded"):
            return True
        ps = f"Remove-MpPreference -ExclusionPath '{ps_quote(path)}' -ErrorAction SilentlyContinue"
        shell.powershell(ps)
        return True


def build_fortnite_tweaks():
    return [
        DefenderExclusionTweak(
            1, "Add Fortnite to Defender Exclusions",
            "Exclude the auto-detected Fortnite install folder from Windows "
            "Defender real-time scanning (falls back to the default Epic "
            "Games install path if the launcher manifest isn't found)"),
    ]
