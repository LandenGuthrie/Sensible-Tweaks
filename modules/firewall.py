"""Firewall helpers. Rules are prefixed so they can be bulk-removed."""
import json
import os
from pathlib import Path

from core import ui, shell
from core.shell import ps_quote

PREFIX = "SensibleTweaks - "


def add_path_menu() -> None:
    while True:
        ui.clear()
        ui.header("ADD PATH TO FIREWALL")
        print("     [1]  Custom Path")
        print("     [2]  Fortnite Preset")
        print("     [0]  Back")
        print()
        c = ui.prompt().lower()
        if c == "1":
            _add_custom_path()
        elif c == "2":
            _add_fortnite_preset()
        elif c == "0":
            return


def _scan_and_add(p: Path) -> int:
    """Add rules for a single file, or every .exe found recursively under a folder."""
    targets = list(p.rglob("*.exe")) if p.is_dir() else [p]
    for exe in targets:
        _add_rule(exe)
    return len(targets)


def _add_custom_path() -> None:
    ui.clear()
    ui.header("ADD CUSTOM PATH")
    print("   Paste a file or folder path.")
    print("   Folders are scanned recursively for .exe files,")
    print("   and each gets inbound + outbound allow rules.")
    print()
    raw = ui.prompt("Path: ").strip().strip('"')
    if not raw:
        return
    p = Path(raw)
    if not p.exists():
        ui.err("Path not found.")
        ui.pause()
        return

    if p.is_dir():
        ui.info("Scanning for executables...")
    count = _scan_and_add(p)
    ui.ok(f"Added rules for {count} file(s).")
    ui.pause()


def _find_fortnite_root() -> Path | None:
    """Look up the Fortnite install folder via Epic Games Launcher manifests,
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


def _add_fortnite_preset() -> None:
    ui.clear()
    ui.header("FORTNITE FIREWALL PRESET")
    root = _find_fortnite_root()
    if not root:
        ui.err("Couldn't auto-detect a Fortnite install.")
        ui.info("Paste the Fortnite install folder manually")
        ui.info("(the one containing 'FortniteGame').")
        raw = ui.prompt("Path: ").strip().strip('"')
        if not raw:
            ui.info("Cancelled.")
            ui.pause()
            return
        root = Path(raw)
        if not root.is_dir():
            ui.err("Path not found.")
            ui.pause()
            return
    else:
        ui.info(f"Found Fortnite at: {root}")

    ui.info("Scanning for executables (this may take a moment)...")
    count = _scan_and_add(root)
    ui.ok(f"Added rules for {count} Fortnite file(s).")
    ui.pause()


def _add_rule(path: Path) -> None:
    nm = ps_quote(f"{PREFIX}{path.name}")
    p = ps_quote(str(path))
    ps = (
        f"New-NetFirewallRule -DisplayName '{nm} (in)'  "
        f"-Direction Inbound  -Action Allow "
        f"-Program '{p}' -Enabled True | Out-Null; "
        f"New-NetFirewallRule -DisplayName '{nm} (out)' "
        f"-Direction Outbound -Action Allow "
        f"-Program '{p}' -Enabled True | Out-Null"
    )
    shell.powershell(ps)
    ui.info(f"+ {path}")


def remove_all() -> None:
    ui.clear()
    ui.header("REMOVE FIREWALL RULES")
    shell.powershell(
        f"Get-NetFirewallRule -DisplayName '{ps_quote(PREFIX)}*' "
        f"| Remove-NetFirewallRule -ErrorAction SilentlyContinue"
    )
    ui.ok("Removed all SensibleTweaks firewall rules.")
    ui.pause()