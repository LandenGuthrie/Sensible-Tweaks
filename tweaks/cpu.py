"""CPU scheduling, power, and priority tweaks."""
from .base import Tweak, RegTweak, PowerCfgValueTweak, _reg_set, _reg_del, _reg_query
from core import shell

SUB_PROCESSOR = "54533251-82be-4824-96c1-47b60b740d00"
CPMINCORES = "0cc5b647-c1df-4637-891a-dec35c318583"
PROCTHROTTLEMIN = "893dee8e-2bef-41e0-89c6-b55d0929964c"
SYSCOOLPOLICY = "94d3a615-a899-4ac5-ae2b-e4d8f634367f"
IDLEDISABLE = "5d76a2ca-e8c0-402f-a133-2158492d58ad"
PERFBOOSTMODE = "be337238-0d82-4146-a960-4f3749d470c7"

SUB_USB = "2a737441-1930-4402-8d77-b2bebba308a3"
USB_SELECTIVE_SUSPEND = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"

SUB_PCIEXPRESS = "501a4d13-42af-4429-9fd1-a8218c268e20"
PCIE_ASPM = "ee12f906-d277-404b-b6da-e5fa1a576df5"

PRIORITY_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl"
MMCSS_KEY = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
GAMES_TASK_KEY = MMCSS_KEY + r"\Tasks\Games"
POWER_THROTTLE_KEY = r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling"
TCPIP_INTERFACES_ROOT = r"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"


class GlobalNagleDisableTweak(Tweak):
    """Sets TCPNoDelay + TcpAckFrequency on every network interface at once,
    rather than the single adapter picked in the Network menu."""

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="cpu")
        self._pre_apply_snap = None

    def _interface_keys(self):
        r = shell.reg("query", TCPIP_INTERFACES_ROOT)
        if r.returncode != 0:
            return []
        return [
            line.strip() for line in r.stdout.splitlines()
            if "Interfaces\\{" in line and line.strip()
        ]

    def apply(self, ctx):
        self._pre_apply_snap = self.snapshot(ctx)
        keys = self._interface_keys()
        if not keys:
            return None
        any_ok = False
        for k in keys:
            ok1 = _reg_set(k, "TCPNoDelay", "REG_DWORD", 1)
            ok2 = _reg_set(k, "TcpAckFrequency", "REG_DWORD", 1)
            if ok1 and ok2:
                any_ok = True
        return any_ok

    def revert(self, ctx):
        """Restore this run's pre-apply state; fall back to deleting both
        values on every interface if apply() was never called this session."""
        if self._pre_apply_snap is not None:
            return self.restore(ctx, self._pre_apply_snap)
        keys = self._interface_keys()
        if not keys:
            return False
        for k in keys:
            _reg_del(k, "TCPNoDelay")
            _reg_del(k, "TcpAckFrequency")
        return True

    def snapshot(self, ctx):
        data = {}
        for k in self._interface_keys():
            t1, v1 = _reg_query(k, "TCPNoDelay")
            t2, v2 = _reg_query(k, "TcpAckFrequency")
            data[k] = {
                "nodelay": {"existed": t1 is not None, "value": v1},
                "ackfreq": {"existed": t2 is not None, "value": v2},
            }
        return {"interfaces": data}

    def restore(self, ctx, snap):
        data = snap.get("interfaces", {})
        if not data:
            return False
        for k, info in data.items():
            nd, af = info.get("nodelay", {}), info.get("ackfreq", {})
            if nd.get("existed"):
                _reg_set(k, "TCPNoDelay", "REG_DWORD", nd.get("value", 0))
            else:
                _reg_del(k, "TCPNoDelay")
            if af.get("existed"):
                _reg_set(k, "TcpAckFrequency", "REG_DWORD", af.get("value", 0))
            else:
                _reg_del(k, "TcpAckFrequency")
        return True


def build_cpu_tweaks():
    return [
        RegTweak(1, "Foreground App Boost",
                 "Win32PrioritySeparation: favor the foreground app with a short, fixed quantum",
                 PRIORITY_KEY, "Win32PrioritySeparation", "REG_DWORD", 38),

        PowerCfgValueTweak(2, "Core Parking Off",
                           "Keep all CPU cores unparked instead of idling them under light load",
                           SUB_PROCESSOR, CPMINCORES, 100, 5),

        PowerCfgValueTweak(3, "Min Processor State 100%",
                           "Stop the CPU from downclocking at idle (higher power draw, lower latency)",
                           SUB_PROCESSOR, PROCTHROTTLEMIN, 100, 5),

        PowerCfgValueTweak(4, "Active Cooling Policy",
                           "Ramp the fan before throttling the CPU instead of throttling first",
                           SUB_PROCESSOR, SYSCOOLPOLICY, 1, 0),

        PowerCfgValueTweak(5, "Disable CPU Idle States (C-States)",
                           "Keep cores fully active; reduces latency spikes but raises heat/power "
                           "noticeably - on laptops this can cause thermal throttling and hurts "
                           "battery life badly, use with caution off AC power",
                           SUB_PROCESSOR, IDLEDISABLE, 0, 1),

        PowerCfgValueTweak(6, "Disable USB Selective Suspend",
                           "Stop Windows power-suspending USB devices (helps HID/controller latency)",
                           SUB_USB, USB_SELECTIVE_SUSPEND, 0, 1),

        PowerCfgValueTweak(7, "Disable PCIe Link State Power Management",
                           "Keep PCIe links at full power instead of ASPM power-saving states",
                           SUB_PCIEXPRESS, PCIE_ASPM, 0, 2),

        RegTweak(8, "Disable Power Throttling",
                 "Stop Windows from applying EcoQoS power throttling to processes",
                 POWER_THROTTLE_KEY, "PowerThrottlingOff", "REG_DWORD", 1),

        RegTweak(9, "MMCSS No Lazy Mode",
                 "Disable MMCSS 'lazy mode' CPU throttling for low-latency multimedia tasks",
                 MMCSS_KEY, "NoLazyMode", "REG_DWORD", 1),

        RegTweak(10, "Games Task GPU Priority",
                 "Raise the MMCSS 'Games' task GPU priority",
                 GAMES_TASK_KEY, "GPU Priority", "REG_DWORD", 8),

        RegTweak(11, "Games Task Priority",
                 "Raise the MMCSS 'Games' task thread priority",
                 GAMES_TASK_KEY, "Priority", "REG_DWORD", 6),

        RegTweak(12, "Games Task Scheduling Category",
                 "Set the MMCSS 'Games' task scheduling category to High",
                 GAMES_TASK_KEY, "Scheduling Category", "REG_SZ", "High"),

        RegTweak(13, "Games Task SFIO Priority",
                 "Set the MMCSS 'Games' task storage I/O priority to High",
                 GAMES_TASK_KEY, "SFIO Priority", "REG_SZ", "High"),

        PowerCfgValueTweak(14, "Aggressive Processor Boost Mode",
                           "Set CPU turbo/boost behavior to Aggressive instead of the default",
                           SUB_PROCESSOR, PERFBOOSTMODE, 2, 0),

        GlobalNagleDisableTweak(15, "Disable Nagle (All Interfaces)",
                                "Apply TCPNoDelay/TcpAckFrequency to every network interface, "
                                "not just the one adapter picked in Network Tweaks. "
                                "Overlaps with Network Tweaks #7/#8 (TcpAckFrequency/TCPNoDelay) - "
                                "use one or the other, not both, to avoid inconsistent state"),
    ]
