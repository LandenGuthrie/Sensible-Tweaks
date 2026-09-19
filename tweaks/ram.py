"""RAM / memory manager tweaks."""
from .base import Tweak, RegTweak
from core import shell

MM_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
PREFETCH_KEY = MM_KEY + r"\PrefetchParameters"


class MemoryCompressionTweak(Tweak):
    """Toggles Windows' in-RAM memory compression via the MMAgent cmdlets."""

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="ram")

    def _current(self):
        out = shell.powershell(
            "(Get-MMAgent).MemoryCompression"
        ).stdout.strip().lower()
        if out in ("true", "false"):
            return out == "true"
        return None

    def _set(self, enable: bool) -> bool:
        verb = "Enable-MMAgent" if enable else "Disable-MMAgent"
        shell.powershell(f"{verb} -MemoryCompression -ErrorAction SilentlyContinue")
        return self._current() == enable

    def apply(self, ctx):
        if self._current() is None:
            return None
        return self._set(False)

    def revert(self, ctx):
        return self._set(True)

    def snapshot(self, ctx):
        cur = self._current()
        return {"enabled": cur if cur is not None else True}

    def restore(self, ctx, snap):
        return self._set(bool(snap.get("enabled", True)))


def build_ram_tweaks():
    return [
        RegTweak(1, "Disable Superfetch/SysMain Service",
                 "Stop the SysMain service from pre-loading apps into RAM based on usage patterns",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\SysMain",
                 "Start", "REG_DWORD", 4),

        RegTweak(2, "Disable Prefetcher",
                 "Stop Windows from prefetching app launch data to disk/RAM caches",
                 PREFETCH_KEY, "EnablePrefetcher", "REG_DWORD", 0),

        RegTweak(3, "Disable Superfetch (Memory Management)",
                 "Disable the Superfetch memory-management feature directly",
                 PREFETCH_KEY, "EnableSuperfetch", "REG_DWORD", 0),

        RegTweak(4, "Disable Paging Executive",
                 "Keep kernel-mode drivers/system code pinned in RAM instead of pageable to disk "
                 "(best on systems with plenty of RAM)",
                 MM_KEY, "DisablePagingExecutive", "REG_DWORD", 1),

        RegTweak(5, "Favor Programs Over File Cache",
                 "Disable Large System Cache so foreground programs get memory priority over disk cache",
                 MM_KEY, "LargeSystemCache", "REG_DWORD", 0),

        RegTweak(6, "Fast Shutdown (Don't Clear Pagefile)",
                 "Skip zeroing the pagefile at shutdown for a faster power-off",
                 MM_KEY, "ClearPageFileAtShutdown", "REG_DWORD", 0),

        RegTweak(7, "Raise I/O Page Lock Limit",
                 "Allow larger pinned I/O buffers (64MB) for high-throughput disk/network transfers",
                 MM_KEY, "IoPageLockLimit", "REG_DWORD", 0x4000000),

        RegTweak(8, "Disable Modern Standby Swapfile",
                 "Stop swapfile.sys from being used during Modern Standby, favoring RAM",
                 MM_KEY, "SwapfileControl", "REG_DWORD", 0),

        MemoryCompressionTweak(9, "Disable Memory Compression",
                               "Trade some RAM headroom for CPU cycles by disabling in-RAM page compression"),
    ]
