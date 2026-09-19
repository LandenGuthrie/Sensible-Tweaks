"""Generic apply/revert + profile menu for adapter-less tweak sections
(CPU, GPU, RAM, Registry, Windows Settings)."""
from core import ui, profiles
from tweaks.base import TweakContext


def _report(name: str, action: str, result) -> None:
    if result is True:
        ui.ok(f"{action}: {name}")
    elif result is None:
        ui.info(f"Not supported on this system: {name}")
    else:
        ui.err(f"Failed (could not verify): {name}")


class SimpleTweakMenu:
    def __init__(self, title: str, section: str, build_fn):
        self.title = title
        self.section = section
        self.build_fn = build_fn

    # -----------------------------------------------------------------
    # profile helpers
    # -----------------------------------------------------------------

    def _pick_profile(self, prompt_msg: str = "Profile name: ") -> str | None:
        items = profiles.list_profiles(self.section)
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
        if c.isdigit() and items:
            idx = int(c) - 1
            if 0 <= idx < len(items):
                return items[idx][0]
            ui.err("Number out of range.")
            return None
        return c

    def _save_profile(self) -> None:
        ui.clear()
        ui.header(f"SAVE {self.title} PROFILE")
        name = self._pick_profile("New profile name: ")
        if not name:
            ui.info("Cancelled.")
            ui.pause()
            return
        if profiles.has_profile(self.section, name):
            if ui.prompt(f"Overwrite '{name}'? (y/n): ").lower() != "y":
                ui.info("Cancelled.")
                ui.pause()
                return
        tweaks = self.build_fn()
        profiles.save_profile(self.section, name, tweaks, adapter=None)
        ui.ok(f"Saved '{name}'  ({profiles.saved_at(self.section, name)})")
        ui.pause()

    def _restore_profile(self) -> None:
        ui.clear()
        ui.header(f"RESTORE {self.title} PROFILE")
        if not profiles.list_profiles(self.section):
            ui.err("No saved profiles. Use [S] to save one first.")
            ui.pause()
            return
        name = self._pick_profile("Restore which profile: ")
        if not name:
            ui.info("Cancelled.")
            ui.pause()
            return
        if not profiles.has_profile(self.section, name):
            ui.err(f"No profile named '{name}'.")
            ui.pause()
            return
        tweaks = self.build_fn()
        restored, total = profiles.restore_profile(self.section, name, tweaks, adapter=None)
        ui.ok(f"Restored {restored} of {total} tweaks from '{name}'.")
        ui.pause()

    def _delete_profile(self) -> None:
        ui.clear()
        ui.header(f"DELETE {self.title} PROFILE")
        if not profiles.list_profiles(self.section):
            ui.err("No saved profiles.")
            ui.pause()
            return
        name = self._pick_profile("Delete which profile: ")
        if not name:
            ui.info("Cancelled.")
            ui.pause()
            return
        if not profiles.has_profile(self.section, name):
            ui.err(f"No profile named '{name}'.")
            ui.pause()
            return
        if ui.prompt(f"Delete '{name}' permanently? (y/n): ").lower() != "y":
            ui.info("Cancelled.")
            ui.pause()
            return
        profiles.delete_profile(self.section, name)
        ui.ok(f"Deleted '{name}'.")
        ui.pause()

    # -----------------------------------------------------------------
    # main loop
    # -----------------------------------------------------------------

    def run(self) -> None:
        tweaks = self.build_fn()
        ctx = TweakContext()

        while True:
            ui.clear()
            ui.header(self.title)
            for t in tweaks:
                print(f"     [{t.id:>2}]  {t.name}")
            print()
            print("     [A] Apply ALL   [R] Revert ALL")
            print("     [S] Save Profile   [L] Load Profile   [D] Delete Profile")
            print("     [0] Back")
            print()
            print("   Enter an ID to apply, or -ID to revert (e.g. 3 or -3).")
            c = ui.prompt()
            if c in ("0", ""):
                return

            low = c.lower()
            if low == "a":
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

            if low == "r":
                for t in tweaks:
                    _report(t.name, "Reverted", t.revert(ctx))
                ui.pause()
                continue

            if low == "s":
                self._save_profile()
                continue

            if low == "l":
                self._restore_profile()
                continue

            if low == "d":
                self._delete_profile()
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

            r = t.revert(ctx) if revert else t.apply(ctx)
            _report(t.name, "Reverted" if revert else "Applied", r)
            ui.pause()
