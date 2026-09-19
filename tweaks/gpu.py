"""GPU / display pipeline tweaks."""
from .base import Tweak, RegTweak, PowerCfgValueTweak, _reg_set, _reg_del, _reg_query
from core import shell

GFX_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
DWM_KEY = r"HKLM\SOFTWARE\Microsoft\Windows\Dwm"
GAMEDVR_POLICY_KEY = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
GAMECONFIG_KEY = r"HKCU\System\GameConfigStore"

SUB_VIDEO = "7516b95f-f776-4464-8c53-06167f40cc99"
ADAPTIVE_BRIGHTNESS = "fbd9aa66-9553-4097-ba44-ed6e9d65eab8"


class GpuMsiModeTweak(Tweak):
    """Enables Message-Signaled Interrupts on the display adapter(s), replacing
    legacy line-based IRQ sharing. Reduces interrupt latency on most GPUs."""

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="gpu")

    def _instance_ids(self):
        ps = (
            "Get-PnpDevice -Class Display -Status OK -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty InstanceId"
        )
        out = shell.powershell(ps).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]

    def _key(self, instance_id: str) -> str:
        return (
            f"HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{instance_id}"
            r"\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"
        )

    def apply(self, ctx):
        ids = self._instance_ids()
        if not ids:
            return None
        any_ok = False
        for iid in ids:
            if _reg_set(self._key(iid), "MSISupported", "REG_DWORD", 1):
                any_ok = True
        return any_ok

    def revert(self, ctx):
        ids = self._instance_ids()
        if not ids:
            return False
        ok = False
        for iid in ids:
            if _reg_set(self._key(iid), "MSISupported", "REG_DWORD", 0):
                ok = True
        return ok

    def snapshot(self, ctx):
        devices = {}
        for iid in self._instance_ids():
            type_, value = _reg_query(self._key(iid), "MSISupported")
            devices[iid] = {"existed": type_ is not None, "value": value}
        return {"devices": devices}

    def restore(self, ctx, snap):
        devices = snap.get("devices", {})
        if not devices:
            return False
        ok = False
        for iid, info in devices.items():
            key = self._key(iid)
            if info.get("existed"):
                if _reg_set(key, "MSISupported", "REG_DWORD", info.get("value", 0)):
                    ok = True
            else:
                _reg_del(key, "MSISupported")
                ok = True
        return ok


def build_gpu_tweaks():
    return [
        RegTweak(1, "Hardware-Accelerated GPU Scheduling",
                 "Let the GPU manage its own VRAM scheduling instead of Windows",
                 GFX_KEY, "HwSchMode", "REG_DWORD", 2),

        RegTweak(2, "TDR Delay",
                 "Raise the Timeout Detection & Recovery delay to 8s (default 2s) "
                 "to avoid false 'driver crashed' resets under heavy load",
                 GFX_KEY, "TdrDelay", "REG_DWORD", 8),

        RegTweak(3, "TDR DDI Delay",
                 "Raise the DDI-level TDR delay alongside TdrDelay",
                 GFX_KEY, "TdrDdiDelay", "REG_DWORD", 8),

        RegTweak(4, "Disable Multiplane Overlay",
                 "Fixes flickering/black-flash issues some GPUs have with MPO",
                 DWM_KEY, "OverlayTestMode", "REG_DWORD", 5),

        RegTweak(5, "Fullscreen Optimizations Behavior",
                 "Prefer true exclusive fullscreen over the FSO compatibility layer",
                 GAMECONFIG_KEY, "GameDVR_FSEBehaviorMode", "REG_DWORD", 2),

        RegTweak(6, "FSE DXGI Compatibility",
                 "Disable the DXGI Windows-compatible fullscreen swap-effect path",
                 GAMECONFIG_KEY, "GameDVR_DXGIHonorFSEWindowsCompatible", "REG_DWORD", 0),

        RegTweak(7, "Disable Game DVR / Game Bar Capture",
                 "Stop the background Game DVR capture service from using GPU/encoder resources",
                 GAMEDVR_POLICY_KEY, "AllowGameDVR", "REG_DWORD", 0),

        PowerCfgValueTweak(8, "Disable Adaptive Brightness",
                           "Stop the display from auto-dimming based on ambient light sensors",
                           SUB_VIDEO, ADAPTIVE_BRIGHTNESS, 0, 1),

        GpuMsiModeTweak(9, "GPU MSI Mode",
                        "Switch the display adapter to Message-Signaled Interrupts"),
    ]
