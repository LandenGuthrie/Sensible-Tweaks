from core import ui, adapter as adp, profiles
from tweaks.network import build_network_tweaks
from tweaks.base import TweakContext
from modules import auto_apply, firewall, stats

SECTION = "network"


def _report(name: str, action: str, result) -> None:
    if result is True:
        ui.ok(f"{action}: {name}")
    elif result is None:
        ui.info(f"Chip doesn't support: {name}")
    else:
        ui.err(f"Failed (could not verify): {name}")


# ---------------------------------------------------------------------------
# profile helpers
# ---------------------------------------------------------------------------

def _pick_profile(prompt_msg: str = "Profile name: ") -> str | None:
    """Show existing profiles, ask for a name. Returns name or None."""
    items = profiles.list_profiles(SECTION)
    if items:
        print("   Saved profiles:")
        for i, (nm, ts) in enumerate(items, 1):
            when = ts[:19].replace("T", " ") if ts else "unknown"
            print(f"     [{i}]  {nm}   ({when})")
        print()
    else:
        print("   (no saved profiles yet)")
        print()

    c = ui.prompt(prompt_msg).strip()
    if not c:
        return None

    # If they picked a number from the list, resolve to the name
    if c.isdigit() and items:
        idx = int(c) - 1
        if 0 <= idx < len(items):
            return items[idx][0]
        ui.err("Number out of range.")
        return None

    return c


def _save_profile() -> None:
    ui.clear()
    ui.header("SAVE NETWORK PROFILE")
    name = _pick_profile("New profile name: ")
    if not name:
        ui.info("Cancelled.")
        ui.pause()
        return

    if profiles.has_profile(SECTION, name):
        ui.info(f"A profile named '{name}' already exists.")
        if ui.prompt("Overwrite? (y/n): ").lower() != "y":
            ui.info("Cancelled.")
            ui.pause()
            return

    a = adp.pick_adapter("eth") or adp.pick_adapter("wifi")
    tweaks = build_network_tweaks()
    profiles.save_profile(SECTION, name, tweaks, adapter=a)
    ui.ok(f"Saved '{name}'  ({profiles.saved_at(SECTION, name)})")
    ui.pause()


def _restore_profile() -> None:
    ui.clear()
    ui.header("RESTORE NETWORK PROFILE")
    if not profiles.list_profiles(SECTION):
        ui.err("No saved profiles. Use 'Save Network Profile' first.")
        ui.pause()
        return

    name = _pick_profile("Restore which profile: ")
    if not name:
        ui.info("Cancelled.")
        ui.pause()
        return

    if not profiles.has_profile(SECTION, name):
        ui.err(f"No profile named '{name}'.")
        ui.pause()
        return

    a = adp.pick_adapter("eth") or adp.pick_adapter("wifi")
    tweaks = build_network_tweaks()
    restored, total = profiles.restore_profile(SECTION, name, tweaks, adapter=a)
    ui.ok(f"Restored {restored} of {total} tweaks from '{name}'.")
    ui.pause()


def _delete_profile() -> None:
    ui.clear()
    ui.header("DELETE NETWORK PROFILE")
    if not profiles.list_profiles(SECTION):
        ui.err("No saved profiles.")
        ui.pause()
        return

    name = _pick_profile("Delete which profile: ")
    if not name:
        ui.info("Cancelled.")
        ui.pause()
        return

    if not profiles.has_profile(SECTION, name):
        ui.err(f"No profile named '{name}'.")
        ui.pause()
        return

    if ui.prompt(f"Delete '{name}' permanently? (y/n): ").lower() != "y":
        ui.info("Cancelled.")
        ui.pause()
        return

    profiles.delete_profile(SECTION, name)
    ui.ok(f"Deleted '{name}'.")
    ui.pause()


# ---------------------------------------------------------------------------
# menus
# ---------------------------------------------------------------------------

class NetworkMenu:
    def run(self) -> None:
        while True:
            ui.clear()
            ui.header("NETWORK TWEAKS")
            print("     [1]  Ethernet   - Manual tweaks")
            print("     [2]  WiFi       - Manual tweaks")
            print("     [3]  Auto Apply - Ethernet")
            print("     [4]  Auto Apply - WiFi")
            print("     [5]  Capture Network Stats")
            print("     [6]  Add Path To Firewall  (recursive)")
            print("     [7]  Remove SensibleTweaks Firewall Rules")
            print("     [8]  Save Network Profile")
            print("     [9]  Restore Network Profile")
            print("     [D]  Delete Network Profile")
            print("     [0]  Back")
            print()
            c = ui.prompt().lower()
            if c == "1":
                AdapterMenu("eth").run()
            elif c == "2":
                AdapterMenu("wifi").run()
            elif c == "3":
                auto_apply.run("eth")
            elif c == "4":
                auto_apply.run("wifi")
            elif c == "5":
                stats.menu()
            elif c == "6":
                firewall.add_path_menu()
            elif c == "7":
                firewall.remove_all()
            elif c == "8":
                _save_profile()
            elif c == "9":
                _restore_profile()
            elif c == "d":
                _delete_profile()
            elif c == "0":
                return


class AdapterMenu:
    def __init__(self, kind: str):
        self.kind = kind

    def run(self) -> None:
        a = adp.pick_adapter(self.kind)
        if not a:
            ui.clear()
            ui.err(f"No active {self.kind} adapter found.")
            ui.pause()
            return

        tweaks = build_network_tweaks()
        ctx = TweakContext(adapter=a)

        while True:
            ui.clear()
            ui.header(f"{self.kind.upper()} TWEAKS - {a.name}")
            for t in tweaks:
                print(f"     [{t.id:>2}]  {t.name}")
            print()
            print("     [A] Apply ALL   [R] Revert ALL   [0] Back")
            print()
            print("   Enter an ID to apply, or -ID to revert (e.g. 3 or -3).")
            c = ui.prompt()
            if c in ("0", ""):
                return

            if c.lower() == "a":
                ok = skipped = failed = 0
                for t in tweaks:
                    r = t.apply(ctx)
                    if r is True:
                        ok += 1
                    elif r is None:
                        skipped += 1
                    else:
                        failed += 1
                    _report(t.name, "Applied", r)
                print()
                ui.ok(f"Summary: {ok} applied, {skipped} unsupported, {failed} failed.")
                ui.pause()
                continue

            if c.lower() == "r":
                for t in tweaks:
                    _report(t.name, "Reverted", t.revert(ctx))
                ui.pause()
                continue

            try:
                tid = int(c)
            except ValueError:
                continue
            revert = tid < 0
            tid = abs(tid)
            t = next((x for x in tweaks if x.id == tid), None)
            if not t:
                ui.err("Unknown tweak ID.")
                ui.pause()
                continue
            if t.requires_adapter and not ctx.adapter:
                ui.err("This tweak requires an adapter.")
                ui.pause()
                continue

            r = t.revert(ctx) if revert else t.apply(ctx)
            _report(t.name, "Reverted" if revert else "Applied", r)
            ui.pause()