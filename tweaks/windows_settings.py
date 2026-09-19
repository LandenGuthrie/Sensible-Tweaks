"""Windows feature / shell settings: power plan, hibernation, storage, shell chrome."""
from .base import Tweak, RegTweak
from core import shell

POWER_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\Power"


def _query_dword(key: str, name: str):
    r = shell.reg("query", key, "/v", name)
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == name:
            for i, p in enumerate(parts):
                if p == "REG_DWORD" and i + 1 < len(parts):
                    try:
                        return int(parts[i + 1], 0)
                    except ValueError:
                        return None
    return None


class UltimatePerformancePlanTweak(Tweak):
    """Activates (creating if needed) the hidden Ultimate Performance power plan."""

    ULTIMATE_TEMPLATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="power")
        self._pre_apply_guid = None

    @staticmethod
    def _extract_guid(text: str):
        for tok in text.split():
            if tok.count("-") == 4:
                return tok
        return None

    def _active_guid(self):
        r = shell.run(["powercfg", "/getactivescheme"])
        for line in r.stdout.splitlines():
            if "GUID:" in line:
                return self._extract_guid(line.split("GUID:", 1)[1])
        return None

    def _find_scheme_guid(self, name_substr: str):
        r = shell.run(["powercfg", "/list"])
        for line in r.stdout.splitlines():
            if name_substr.lower() in line.lower():
                g = self._extract_guid(line)
                if g:
                    return g
        return None

    def apply(self, ctx):
        self._pre_apply_guid = self._active_guid()
        guid = self._find_scheme_guid("Ultimate Performance")
        if not guid:
            r = shell.run(["powercfg", "-duplicatescheme", self.ULTIMATE_TEMPLATE])
            guid = self._extract_guid(r.stdout)
        if not guid:
            return False
        if shell.run(["powercfg", "/setactive", guid]).returncode != 0:
            return False
        return self._active_guid() == guid

    def revert(self, ctx):
        """Switch back to whatever plan was active before this run's apply();
        fall back to Balanced if apply() was never called this session."""
        guid = self._pre_apply_guid or self._find_scheme_guid("Balanced")
        if not guid:
            return False
        return shell.run(["powercfg", "/setactive", guid]).returncode == 0

    def snapshot(self, ctx):
        return {"guid": self._active_guid()}

    def restore(self, ctx, snap):
        guid = snap.get("guid")
        if not guid:
            return False
        return shell.run(["powercfg", "/setactive", guid]).returncode == 0


class HibernateTweak(Tweak):
    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="system")

    def _enabled(self):
        v = _query_dword(POWER_KEY, "HibernateEnabled")
        return bool(v) if v is not None else None

    def _set(self, on: bool) -> bool:
        shell.run(["powercfg", "/hibernate", "on" if on else "off"], timeout=60)
        return self._enabled() == on

    def apply(self, ctx):
        if self._enabled() is None:
            return None
        return self._set(False)

    def revert(self, ctx):
        return self._set(True)

    def snapshot(self, ctx):
        v = self._enabled()
        return {"enabled": v if v is not None else True}

    def restore(self, ctx, snap):
        return self._set(bool(snap.get("enabled", True)))


class ReservedStorageTweak(Tweak):
    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="system")

    def _state(self):
        r = shell.run(["dism", "/Online", "/Get-ReservedStorageState"], timeout=60)
        out = r.stdout.lower()
        if "disabled" in out:
            return False
        if "enabled" in out:
            return True
        return None

    def _set(self, enable: bool) -> bool:
        state = "Enabled" if enable else "Disabled"
        r = shell.run(["dism", "/Online", "/Set-ReservedStorageState", f"/State:{state}"], timeout=180)
        return r.returncode == 0

    def apply(self, ctx):
        if self._state() is None:
            return None
        return self._set(False)

    def revert(self, ctx):
        return self._set(True)

    def snapshot(self, ctx):
        v = self._state()
        return {"enabled": v if v is not None else True}

    def restore(self, ctx, snap):
        return self._set(bool(snap.get("enabled", True)))


def build_windows_settings_tweaks():
    return [
        UltimatePerformancePlanTweak(1, "Ultimate Performance Power Plan",
                                     "Switch to the hidden Ultimate Performance power plan"),

        HibernateTweak(2, "Disable Hibernation",
                       "Turn off hibernation and remove hiberfil.sys (frees disk space equal to RAM size)"),

        RegTweak(3, "Disable Fast Startup",
                 "Disable hybrid shutdown/Fast Startup (fixes some driver-state and dual-boot issues)",
                 r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                 "HiberbootEnabled", "REG_DWORD", 0),

        RegTweak(4, "No Forced Reboots During Updates",
                 "Stop Windows Update from auto-rebooting while you're logged in",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
                 "NoAutoRebootWithLoggedOnUsers", "REG_DWORD", 1),

        RegTweak(5, "Disable Storage Sense",
                 "Stop Windows from automatically running disk cleanup in the background",
                 r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy",
                 "01", "REG_DWORD", 0),

        ReservedStorageTweak(6, "Disable Reserved Storage",
                             "Free the disk space Windows reserves for updates/temp files"),

        RegTweak(7, "Disable Widgets",
                 "Remove the Widgets icon/panel from the taskbar",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Dsh",
                 "AllowNewsAndInterests", "REG_DWORD", 0),

        RegTweak(8, "Disable Chat Icon",
                 "Remove the Chat (Teams) icon from the taskbar",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Chat",
                 "ChatIcon", "REG_DWORD", 3),

        RegTweak(9, "Disable Notification Center",
                 "Turn off Windows toast notifications and the notification center",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Explorer",
                 "DisableNotificationCenter", "REG_DWORD", 1),

        RegTweak(10, "Visual Effects: Best Performance",
                  "Switch visual effects to 'Adjust for best performance'",
                  r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                  "VisualFXSetting", "REG_DWORD", 2),

        RegTweak(11, "Disable Transparency Effects",
                  "Turn off the translucent/acrylic taskbar and window effects",
                  r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                  "EnableTransparency", "REG_DWORD", 0),

        RegTweak(12, "Enable Windows Game Mode",
                  "Turn on Game Mode so Windows deprioritizes background work "
                  "and driver-store updates while a game has focus",
                  r"HKCU\SOFTWARE\Microsoft\GameBar",
                  "AutoGameModeEnabled", "REG_DWORD", 1),
    ]
