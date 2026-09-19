"""All network tweaks.

IDs 1-16   : original set (unchanged)
IDs 17-30  : additions (QoS, Fast Open, Heuristics, advanced EEE/Green,
             checksum offloads, ARP/NS offloads, RX/TX buffers)
IDs 31-32  : OS-level RSC and Pacing Profile (netsh-accessible)
IDs 55-57  : DNS server + DNS-over-HTTPS (Cloudflare)
IDs 58-59  : Delivery Optimization throttle, NIC MSI mode
"""
from __future__ import annotations

import json

from .base import (
    Tweak, TweakContext, RegTweak,
    _reg_set, _reg_del, _reg_query, _reg_verify, _reg_backup,
)
from core import shell, backup, adapter as adp
from core.shell import ps_quote

BACKUP_DIR = backup.BACKUP_DIR


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------

def _netsh_set(option: str, value: str) -> bool:
    r = shell.netsh("int", "tcp", "set", "global", f"{option}={value}")
    return r.returncode == 0


def _netsh_get_global() -> dict:
    r = shell.netsh("int", "tcp", "show", "global")
    parsed = {}
    for line in r.stdout.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().lower()
        v = v.strip().lower()
        if k and v:
            parsed[k] = v
    return parsed


def _cmdlet_exists(name: str) -> bool:
    ps = f"if (Get-Command {name} -ErrorAction SilentlyContinue) {{ 'YES' }} else {{ 'NO' }}"
    return "YES" in shell.powershell(ps).stdout


# ---------------------------------------------------------------------------
# reusable tweak types
# ---------------------------------------------------------------------------

class NetshUdpTweak(Tweak):
    """Flips a value exposed by `netsh interface udp show global`."""

    _SEARCH = {
        "uro": "receive offload state",
        "uso": "segmentation offload state",
    }

    def __init__(self, id, name, description, option, apply_value, revert_value):
        super().__init__(id, name, description, category="stack")
        self.option = option
        self.apply_value = apply_value
        self.revert_value = revert_value

    def _read_current(self):
        r = shell.netsh("interface", "udp", "show", "global")
        parsed = {}
        for line in r.stdout.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip().lower()
            v = v.strip().lower()
            if k and v:
                parsed[k] = v
        keyword = self._SEARCH.get(self.option, self.option)
        for k, v in parsed.items():
            if keyword in k:
                return v
        return None

    def _set_and_verify(self, value: str):
        if self._read_current() is None:
            return None
        r = shell.netsh("interface", "udp", "set", "global",
                        f"{self.option}={value}")
        if r.returncode != 0:
            return False
        return self._read_current() == value.lower()

    def apply(self, ctx):
        return self._set_and_verify(self.apply_value)

    def revert(self, ctx):
        return self._set_and_verify(self.revert_value)

    def snapshot(self, ctx):
        v = self._read_current()
        return {"value": v if v is not None else self.revert_value}

    def restore(self, ctx, snap):
        v = snap.get("value")
        if not v:
            return False
        return shell.netsh("interface", "udp", "set", "global",
                           f"{self.option}={v}").returncode == 0

class NetshGlobalTweak(Tweak):
    """Flips a value exposed by `netsh int tcp show global`.

    Returns:
        True  - applied and read-back confirms the change
        False - value exists, set attempted, but read-back disagrees
        None  - option not exposed by this Windows build (e.g. TCP Chimney on Win8+)
    """

    _SEARCH = {
        "autotuninglevel": "receive window auto-tuning level",
        "ecncapability":   "ecn capability",
        "timestamps":      "rfc 1323 timestamps",
        "chimney":         "chimney offload state",
        "rss":             "receive-side scaling state",
        "fastopen":        "fast open",
        "rsc":             "receive segment coalescing state",
        "pacingprofile":   "pacing profile",
    }

    def __init__(self, id, name, description, option, apply_value, revert_value):
        super().__init__(id, name, description, category="stack")
        self.option = option
        self.apply_value = apply_value
        self.revert_value = revert_value

    def _read_current(self):
        parsed = _netsh_get_global()
        keyword = self._SEARCH.get(self.option, self.option)
        for k, v in parsed.items():
            if keyword in k:
                return v
        return None

    def _set_and_verify(self, value: str):
        if self._read_current() is None:
            return None
        if not _netsh_set(self.option, value):
            return False
        return self._read_current() == value.lower()

    def apply(self, ctx):
        return self._set_and_verify(self.apply_value)

    def revert(self, ctx):
        return self._set_and_verify(self.revert_value)

    def snapshot(self, ctx):
        v = self._read_current()
        return {"value": v if v is not None else self.revert_value}

    def restore(self, ctx, snap):
        v = snap.get("value")
        if not v:
            return False
        return _netsh_set(self.option, v)


class NetshHeuristicsTweak(Tweak):
    """`netsh int tcp set heuristics disabled` -- separate subcommand."""

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="stack")

    def _set(self, value: str) -> bool:
        r = shell.netsh("int", "tcp", "set", "heuristics", value)
        return r.returncode == 0

    def _current(self) -> str:
        r = shell.netsh("int", "tcp", "show", "heuristics")
        for line in r.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                if "heuristic" in k.strip().lower():
                    return v.strip().lower()
        return ""

    def apply(self, ctx):
        if not self._set("disabled"):
            return False
        cur = self._current()
        return cur == "disabled" or cur == ""

    def revert(self, ctx):
        return self._set("default")

    def snapshot(self, ctx):
        return {"value": self._current() or "default"}

    def restore(self, ctx, snap):
        return self._set(snap.get("value", "default"))


class IfRegTweak(Tweak):
    def __init__(self, id, name, description, value_name, apply_value):
        super().__init__(id, name, description, category="interface", requires_adapter=True)
        self.value_name = value_name
        self.apply_value = apply_value
        self._pre_apply_snap = None

    def _key(self, ctx: TweakContext) -> str:
        return (
            r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            f"\\{ctx.adapter.if_guid}"
        )

    def apply(self, ctx):
        self._pre_apply_snap = self.snapshot(ctx)
        key = self._key(ctx)
        _reg_backup(key, f"{self.value_name}_{ctx.adapter.if_guid}")
        if not _reg_set(key, self.value_name, "REG_DWORD", self.apply_value):
            return False
        return _reg_verify(key, self.value_name, "REG_DWORD", self.apply_value)

    def revert(self, ctx):
        """Restore this run's pre-apply state; fall back to deleting the
        value if apply() was never called this session."""
        if self._pre_apply_snap is not None:
            return self.restore(ctx, self._pre_apply_snap)
        return _reg_del(self._key(ctx), self.value_name)

    def snapshot(self, ctx):
        if not ctx.adapter:
            return {}
        key = self._key(ctx)
        type_, value = _reg_query(key, self.value_name)
        if type_ is None:
            return {"existed": False}
        return {"existed": True, "type": type_, "value": value}

    def restore(self, ctx, snap):
        if not ctx.adapter:
            return False
        key = self._key(ctx)
        if snap.get("existed"):
            return _reg_set(key, self.value_name,
                            snap.get("type", "REG_DWORD"),
                            snap.get("value", 1))
        _reg_del(key, self.value_name)
        return True


class AdapterAdvancedTweak(Tweak):
    def __init__(self, id, name, description, prop_names,
                 apply_value="Disabled", revert_value="Enabled"):
        super().__init__(id, name, description, category="adapter", requires_adapter=True)
        self.prop_names = prop_names
        self.apply_value = apply_value
        self.revert_value = revert_value

    def _set_and_verify(self, ctx, target_value):
        any_supported = False
        any_succeeded = False
        for p in self.prop_names:
            r = adp.set_advanced(ctx.adapter.name, p, target_value)
            if r is None:
                continue
            any_supported = True
            if r:
                any_succeeded = True
        if not any_supported:
            return None
        return any_succeeded

    def apply(self, ctx):
        return self._set_and_verify(ctx, self.apply_value)

    def revert(self, ctx):
        return self._set_and_verify(ctx, self.revert_value)

    def _read_all(self, ctx):
        ps = (
            f"Get-NetAdapterAdvancedProperty -Name '{ctx.adapter.name}' "
            f"-ErrorAction SilentlyContinue | "
            f"Select-Object DisplayName, DisplayValue | ConvertTo-Json -Compress"
        )
        out = shell.powershell(ps).stdout.strip()
        if not out:
            return {}
        try:
            data = json.loads(out)
        except Exception:
            return {}
        if isinstance(data, dict):
            data = [data]
        return {d.get("DisplayName", ""): d.get("DisplayValue", "") for d in data}

    def snapshot(self, ctx):
        if not ctx.adapter:
            return {}
        all_props = self._read_all(ctx)
        captured = {p: all_props[p] for p in self.prop_names if p in all_props}
        return {"props": captured}

    def restore(self, ctx, snap):
        if not ctx.adapter:
            return False
        ok = False
        for prop, val in snap.get("props", {}).items():
            if adp.set_advanced(ctx.adapter.name, prop, val) is True:
                ok = True
        return ok


class BuffersTweak(Tweak):
    """Set a numeric advanced property (Receive/Transmit Buffers) to its maximum."""

    def __init__(self, id, name, description, prop_names):
        super().__init__(id, name, description, category="adapter", requires_adapter=True)
        self.prop_names = prop_names

    def _valid_values(self, adapter_name: str, prop: str):
        ps = (
            f"$p = Get-NetAdapterAdvancedProperty -Name '{adapter_name}' "
            f"-DisplayName '{prop}' -ErrorAction SilentlyContinue; "
            f"if ($p) {{ $p.ValidDisplayValues -join '|' }} else {{ '__MISSING__' }}"
        )
        out = shell.powershell(ps).stdout.strip()
        if not out or out == "__MISSING__":
            return None
        return out.split("|")

    def _max_numeric(self, values):
        best = None
        for v in values:
            v = v.strip()
            if "-" in v:
                try:
                    _, hi = v.split("-", 1)
                    n = int(hi)
                except Exception:
                    continue
            else:
                try:
                    n = int(v)
                except Exception:
                    continue
            if best is None or n > best:
                best = n
        return best

    def _set_and_verify(self, ctx):
        any_supported = False
        any_succeeded = False
        for p in self.prop_names:
            vals = self._valid_values(ctx.adapter.name, p)
            if not vals:
                continue
            maxv = self._max_numeric(vals)
            if maxv is None:
                continue
            any_supported = True
            if adp.set_advanced(ctx.adapter.name, p, str(maxv)) is True:
                any_succeeded = True
        if not any_supported:
            return None
        return any_succeeded

    def apply(self, ctx):
        return self._set_and_verify(ctx)

    def revert(self, ctx):
        return True

    def snapshot(self, ctx):
        if not ctx.adapter:
            return {}
        snap = {}
        for p in self.prop_names:
            v = adp.get_advanced(ctx.adapter.name, p)
            if v is not None:
                snap[p] = v
        return {"props": snap}

    def restore(self, ctx, snap):
        if not ctx.adapter:
            return False
        ok = False
        for prop, val in snap.get("props", {}).items():
            if adp.set_advanced(ctx.adapter.name, prop, val) is True:
                ok = True
        return ok


class QosDscpTweak(Tweak):
    """Windows QoS policy marking outbound traffic with DSCP 46 (EF)."""

    POLICY_NAME = "SensibleTweaks-Game"

    def __init__(self, id, name, description, dscp: int = 46):
        super().__init__(id, name, description, category="qos")
        self.dscp = dscp

    def _exists(self) -> bool:
        r = shell.powershell(
            f"Get-NetQosPolicy -Name '{self.POLICY_NAME}' -ErrorAction SilentlyContinue"
        )
        return self.POLICY_NAME in r.stdout

    def apply(self, ctx):
        if not _cmdlet_exists("New-NetQosPolicy"):
            return None
        shell.powershell(
            f"Remove-NetQosPolicy -Name '{self.POLICY_NAME}' "
            f"-Confirm:$false -ErrorAction SilentlyContinue"
        )
        ps = (
            f"try {{ New-NetQosPolicy -Name '{self.POLICY_NAME}' "
            f"-AppPathNameMatchCondition '*' "
            f"-DSCPAction {self.dscp} -NetworkProfile All -ErrorAction Stop; 'OK' }} "
            f"catch {{ 'FAIL' }}"
        )
        if "OK" not in shell.powershell(ps).stdout:
            return False
        return self._exists()

    def revert(self, ctx):
        shell.powershell(
            f"Remove-NetQosPolicy -Name '{self.POLICY_NAME}' "
            f"-Confirm:$false -ErrorAction SilentlyContinue"
        )
        return not self._exists()

    def snapshot(self, ctx):
        return {"existed": self._exists()}

    def restore(self, ctx, snap):
        if snap.get("existed"):
            return self.apply(ctx) is True
        return self.revert(ctx)


class AdapterPowerTweak(Tweak):
    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="adapter", requires_adapter=True)

    def apply(self, ctx):
        return adp.set_power_saving(ctx.adapter.name, False)

    def revert(self, ctx):
        return adp.set_power_saving(ctx.adapter.name, True)

    def snapshot(self, ctx):
        if not ctx.adapter:
            return {}
        v = adp.get_power_saving(ctx.adapter.name)
        return {"value": v or "Enabled"}

    def restore(self, ctx, snap):
        if not ctx.adapter:
            return False
        v = snap.get("value", "Enabled").lower()
        return adp.set_power_saving(ctx.adapter.name, v == "enabled") is True


NETTHROTTLE_KEY = (
    r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    r"\Multimedia\SystemProfile"
)


class DnsServerTweak(Tweak):
    """Sets a fixed primary+secondary DNS server on the adapter, replacing
    whatever DHCP/static config was there."""

    def __init__(self, id, name, description, primary: str, secondary: str):
        super().__init__(id, name, description, category="interface", requires_adapter=True)
        self.primary = primary
        self.secondary = secondary

    def _show(self, adapter_name: str) -> str:
        return shell.run(["netsh", "interface", "ip", "show", "dns", f"name={adapter_name}"]).stdout

    def _current(self, adapter_name: str):
        out = self._show(adapter_name)
        is_dhcp = "configured through dhcp" in out.lower()
        addrs = []
        for line in out.splitlines():
            line = line.strip()
            if line.replace(".", "").isdigit() and line.count(".") == 3:
                addrs.append(line)
            elif ":" in line:
                tail = line.split(":", 1)[1].strip()
                if tail and tail.count(".") == 3:
                    addrs.append(tail)
        return {"dhcp": is_dhcp, "servers": addrs}

    def _set(self, adapter_name: str, servers) -> bool:
        if not servers:
            r = shell.run(["netsh", "interface", "ip", "set", "dns",
                          f"name={adapter_name}", "dhcp"])
            return r.returncode == 0
        r = shell.run(["netsh", "interface", "ip", "set", "dns",
                      f"name={adapter_name}", "static", servers[0], "primary"])
        if r.returncode != 0:
            return False
        for i, addr in enumerate(servers[1:], start=2):
            shell.run(["netsh", "interface", "ip", "add", "dns",
                      f"name={adapter_name}", addr, f"index={i}"])
        return True

    def apply(self, ctx):
        if not ctx.adapter:
            return None
        return self._set(ctx.adapter.name, [self.primary, self.secondary])

    def revert(self, ctx):
        if not ctx.adapter:
            return False
        return self._set(ctx.adapter.name, [])

    def snapshot(self, ctx):
        if not ctx.adapter:
            return {}
        return self._current(ctx.adapter.name)

    def restore(self, ctx, snap):
        if not ctx.adapter:
            return False
        if snap.get("dhcp", True) or not snap.get("servers"):
            return self._set(ctx.adapter.name, [])
        return self._set(ctx.adapter.name, snap["servers"])


class NicMsiModeTweak(Tweak):
    """Enables Message-Signaled Interrupts on network adapters, same pattern
    as GpuMsiModeTweak in tweaks/gpu.py - reduces NIC interrupt latency."""

    def __init__(self, id, name, description):
        super().__init__(id, name, description, category="adapter", requires_adapter=True)

    def _key(self, ctx: TweakContext) -> str:
        return (
            f"HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{ctx.adapter.if_guid}"
            r"\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"
        )

    def _instance_key(self, ctx: TweakContext):
        """The adapter's InterfaceGuid isn't a PnP instance path, so resolve
        the actual Enum instance id via WMI before touching the registry."""
        ps = (
            "Get-CimInstance Win32_NetworkAdapter -Filter "
            f"\"GUID='{ps_quote(ctx.adapter.if_guid)}'\" | "
            "Select-Object -ExpandProperty PNPDeviceID"
        )
        out = shell.powershell(ps).stdout.strip()
        if not out:
            return None
        return (
            f"HKLM\\SYSTEM\\CurrentControlSet\\Enum\\{out}"
            r"\Device Parameters\Interrupt Management\MessageSignaledInterruptProperties"
        )

    def apply(self, ctx):
        if not ctx.adapter:
            return None
        key = self._instance_key(ctx)
        if not key:
            return None
        return _reg_set(key, "MSISupported", "REG_DWORD", 1)

    def revert(self, ctx):
        if not ctx.adapter:
            return False
        key = self._instance_key(ctx)
        if not key:
            return False
        return _reg_set(key, "MSISupported", "REG_DWORD", 0)

    def snapshot(self, ctx):
        if not ctx.adapter:
            return {}
        key = self._instance_key(ctx)
        if not key:
            return {}
        type_, value = _reg_query(key, "MSISupported")
        return {"key": key, "existed": type_ is not None, "value": value}

    def restore(self, ctx, snap):
        key = snap.get("key")
        if not key:
            return False
        if snap.get("existed"):
            return _reg_set(key, "MSISupported", "REG_DWORD", snap.get("value", 0))
        _reg_del(key, "MSISupported")
        return True


class DohTemplateTweak(Tweak):
    """Registers a Windows-native DNS-over-HTTPS encryption profile for a
    DNS server IP. Requires Windows 10 2004+ / Server 2022+."""

    def __init__(self, id, name, description, server_ip: str, template: str):
        super().__init__(id, name, description, category="stack")
        self.server_ip = server_ip
        self.template = template

    def _exists(self) -> bool:
        r = shell.run(["netsh", "dns", "show", "encryption", f"server={self.server_ip}"])
        return r.returncode == 0 and self.template in r.stdout

    def apply(self, ctx):
        probe = shell.run(["netsh", "dns", "show", "encryption"])
        if probe.returncode != 0:
            return None
        r = shell.run(["netsh", "dns", "add", "encryption",
                      f"server={self.server_ip}", f"dohtemplate={self.template}",
                      "autoupgrade=yes", "udpfallback=no"])
        if r.returncode != 0:
            return False
        return self._exists()

    def revert(self, ctx):
        shell.run(["netsh", "dns", "delete", "encryption", f"server={self.server_ip}"])
        return not self._exists()

    def snapshot(self, ctx):
        return {"existed": self._exists()}

    def restore(self, ctx, snap):
        if snap.get("existed"):
            return self.apply(ctx) is True
        return self.revert(ctx)


def build_network_tweaks():
    return [
        # --- 1-16: original set ---
        RegTweak(1, "Network Throttling Index",
                 "Disables the 10 pkt/ms non-multimedia throttle",
                 NETTHROTTLE_KEY, "NetworkThrottlingIndex",
                 "REG_DWORD", 0xFFFFFFFF),
        NetshGlobalTweak(2, "TCP Auto-Tuning",
                         "Set autotuning to highlyrestricted",
                         "autotuninglevel", "highlyrestricted", "normal"),
        NetshGlobalTweak(3, "TCP ECN",
                         "Enable Explicit Congestion Notification (can reduce bufferbloat "
                         "latency, but some routers/ISPs mishandle ECN-marked packets and "
                         "it can increase jitter/loss on those networks - test before keeping)",
                         "ecncapability", "enabled", "disabled"),
        NetshGlobalTweak(4, "TCP Timestamps",
                         "Disable TCP timestamps (less overhead)",
                         "timestamps", "disabled", "allowed"),
        NetshGlobalTweak(5, "TCP Chimney Offload",
                         "Disable chimney (removed from Windows 8+)",
                         "chimney", "disabled", "default"),
        NetshGlobalTweak(6, "TCP RSS",
                         "Enable Receive-Side Scaling",
                         "rss", "enabled", "default"),
        IfRegTweak(7, "TcpAckFrequency",
                   "ACK every packet instead of batching",
                   "TcpAckFrequency", 1),
        IfRegTweak(8, "TCPNoDelay",
                   "Disable Nagle on this interface",
                   "TCPNoDelay", 1),
        AdapterAdvancedTweak(9, "Interrupt Moderation",
                             "Reduce NIC interrupt batching delay",
                             ["Interrupt Moderation", "ITR"]),
        AdapterAdvancedTweak(10, "Energy Efficient Ethernet",
                             "Disable EEE to avoid wake-up latency",
                             ["Energy Efficient Ethernet",
                              "Energy-Efficient Ethernet",
                              "EEE"]),
        AdapterAdvancedTweak(11, "Flow Control",
                             "Disable pause frames",
                             ["Flow Control"]),
        AdapterAdvancedTweak(12, "Large Send Offload v2 (IPv4)",
                             "Disable LSO IPv4",
                             ["Large Send Offload V2 (IPv4)",
                              "Large Send Offload v2 (IPv4)"]),
        AdapterAdvancedTweak(13, "Large Send Offload v2 (IPv6)",
                             "Disable LSO IPv6",
                             ["Large Send Offload V2 (IPv6)",
                              "Large Send Offload v2 (IPv6)"]),
        AdapterAdvancedTweak(14, "Recv Segment Coalescing (IPv4)",
                             "Disable RSC IPv4 at NIC level",
                             ["Recv Segment Coalescing (IPv4)",
                              "Receive Segment Coalescing (IPv4)",
                              "RSC IPv4"]),
        AdapterAdvancedTweak(15, "Recv Segment Coalescing (IPv6)",
                             "Disable RSC IPv6 at NIC level",
                             ["Recv Segment Coalescing (IPv6)",
                              "Receive Segment Coalescing (IPv6)",
                              "RSC IPv6"]),
        AdapterPowerTweak(16, "Adapter Power Saving",
                          "Prevent NIC from sleeping on idle"),

        # --- 17-30: additions ---
        QosDscpTweak(17, "QoS DSCP Marking",
                     "Mark outbound packets with DSCP 46 (Expedited Forwarding)",
                     dscp=46),
        NetshGlobalTweak(18, "TCP Fast Open",
                         "Enable TCP Fast Open (0-RTT reconnect)",
                         "fastopen", "enabled", "disabled"),
        NetshHeuristicsTweak(19, "TCP Heuristics",
                             "Stop Windows overriding your manual TCP settings"),
        AdapterAdvancedTweak(20, "Advanced EEE",
                             "Disable Realtek Advanced EEE",
                             ["Advanced EEE", "AdvancedEEE"]),
        AdapterAdvancedTweak(21, "Green Ethernet",
                             "Disable Green Ethernet power saving",
                             ["Green Ethernet", "Gigabit Lite"]),
        AdapterAdvancedTweak(22, "IPv4 Checksum Offload",
                             "Disable IPv4 header checksum offload",
                             ["IPv4 Checksum Offload",
                              "IP Checksum Offload"],
                             apply_value="Disabled",
                             revert_value="Rx & Tx Enabled"),
        AdapterAdvancedTweak(23, "TCP Checksum Offload (IPv4)",
                             "Disable TCP checksum offload IPv4",
                             ["TCP Checksum Offload (IPv4)"],
                             apply_value="Disabled",
                             revert_value="Rx & Tx Enabled"),
        AdapterAdvancedTweak(24, "TCP Checksum Offload (IPv6)",
                             "Disable TCP checksum offload IPv6",
                             ["TCP Checksum Offload (IPv6)"],
                             apply_value="Disabled",
                             revert_value="Rx & Tx Enabled"),
        AdapterAdvancedTweak(25, "UDP Checksum Offload (IPv4)",
                             "Disable UDP checksum offload IPv4",
                             ["UDP Checksum Offload (IPv4)"],
                             apply_value="Disabled",
                             revert_value="Rx & Tx Enabled"),
        AdapterAdvancedTweak(26, "UDP Checksum Offload (IPv6)",
                             "Disable UDP checksum offload IPv6",
                             ["UDP Checksum Offload (IPv6)"],
                             apply_value="Disabled",
                             revert_value="Rx & Tx Enabled"),
        AdapterAdvancedTweak(27, "ARP Offload",
                             "Disable ARP offload power saving",
                             ["ARP Offload", "ARP Offload Power Saving"]),
        AdapterAdvancedTweak(28, "NS Offload",
                             "Disable NS offload power saving",
                             ["NS Offload", "NS Offload Power Saving"]),
        BuffersTweak(29, "Receive Buffers",
                     "Set receive buffers to their maximum",
                     ["Receive Buffers", "Receive Buffer Size"]),
        BuffersTweak(30, "Transmit Buffers",
                     "Set transmit buffers to their maximum",
                     ["Transmit Buffers", "Transmit Buffer Size"]),

        # --- 31-32: OS-level TCP stack options ---
        NetshGlobalTweak(31, "Receive Segment Coalescing (OS)",
                         "Disable RSC at the OS stack level (Win10 1709+)",
                         "rsc", "disabled", "enabled"),
        NetshGlobalTweak(32, "TCP Pacing Profile",
                         "Turn off TCP packet pacing (latency friendly)",
                         "pacingprofile", "off", "default"),
        # --- 33-35: UDP offloads & congestion ---
        NetshUdpTweak(33, "UDP Receive Offload (URO)",
                      "Disable UDP receive offload (reduces micro-latency)",
                      "uro", "disabled", "enabled"),

        NetshUdpTweak(34, "UDP Segmentation Offload (USO)",
                      "Disable UDP segmentation offload",
                      "uso", "disabled", "enabled"),

        NetshGlobalTweak(35, "Congestion Provider (CTCP)",
                         "Enable Compound TCP for high-latency links",
                         "congestionprovider", "ctcp", "none"),

        # --- 36: SystemResponsiveness (same key as NetworkThrottlingIndex) ---
        RegTweak(36, "System Responsiveness",
                 "Reserve only 10% CPU for background tasks (default 20%)",
                 NETTHROTTLE_KEY, "SystemResponsiveness",
                 "REG_DWORD", 10),

        # --- 37-41: Tcpip\Parameters ---
        RegTweak(37, "MaxUserPort",
                 "Expand ephemeral port range to 65534",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "MaxUserPort", "REG_DWORD", 65534),

        RegTweak(38, "TcpTimedWaitDelay",
                 "Reduce TIME_WAIT from 240s to 30s (faster port reuse)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "TcpTimedWaitDelay", "REG_DWORD", 30),

        RegTweak(39, "DefaultTTL",
                 "Set default TTL to 64 (standard internet value)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "DefaultTTL", "REG_DWORD", 64),

        RegTweak(40, "SackOpts",
                 "Enable TCP Selective Acknowledgements "
                 "(legacy - Windows has used auto-tuning since Vista/7, limited effect on Win10/11)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "SackOpts", "REG_DWORD", 1),

        RegTweak(41, "Tcp1323Opts",
                 "Enable RFC 1323 window scaling only "
                 "(legacy - Windows has used auto-tuning since Vista/7, limited effect on Win10/11)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "Tcp1323Opts", "REG_DWORD", 1),

        RegTweak(42, "EnableWsd",
                 "Disable window scaling heuristics (keep manual control) "
                 "(legacy - Windows has used auto-tuning since Vista/7, limited effect on Win10/11)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "EnableWsd", "REG_DWORD", 0),

        RegTweak(43, "EnablePMTUDiscovery",
                 "Keep path MTU discovery enabled (prevents fragmentation)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "EnablePMTUDiscovery", "REG_DWORD", 1),

        RegTweak(44, "EnablePMTUBHDetect",
                 "Disable black-hole router detection "
                 "(legacy - Windows has used auto-tuning since Vista/7, limited effect on Win10/11)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                 "EnablePMTUBHDetect", "REG_DWORD", 0),

        # --- 45: AFD fast UDP datagram path ---
        RegTweak(45, "FastSendDatagramThreshold",
                 "Raise fast-path UDP threshold to 64 KB",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\AFD\Parameters",
                 "FastSendDatagramThreshold", "REG_DWORD", 65536),

        # --- 46-47: DNS client cache ---
        RegTweak(46, "DNS MaxNegativeCacheTtl",
                 "Don't cache failed DNS lookups",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters",
                 "MaxNegativeCacheTtl", "REG_DWORD", 0),

        RegTweak(47, "DNS NetFailureCacheTime",
                 "Don't hang 30s after a network failure",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters",
                 "NetFailureCacheTime", "REG_DWORD", 0),

        # --- 48: QoS reservation ---
        RegTweak(48, "QoS NonBestEffortLimit",
                 "Release the 20% QoS bandwidth reservation",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Psched",
                 "NonBestEffortLimit", "REG_DWORD", 0),

        # --- 49: NetBT name table size ---
        RegTweak(49, "NetBT Name Cache Size",
                 "Set NetBT name table to Large (256 buckets)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\NetBT\Parameters",
                 "Size/Small/Medium/Large", "REG_DWORD", 3),

        # --- 50-53: ServiceProvider priorities ---
        RegTweak(50, "ServiceProvider DnsPriority",
                 "Raise DNS priority (default 2000)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider",
                 "DnsPriority", "REG_DWORD", 6),

        RegTweak(51, "ServiceProvider HostsPriority",
                 "Raise hosts file priority (default 500)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider",
                 "HostsPriority", "REG_DWORD", 5),

        RegTweak(52, "ServiceProvider LocalPriority",
                 "Raise local priority (default 499)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider",
                 "LocalPriority", "REG_DWORD", 4),

        RegTweak(53, "ServiceProvider NetbtPriority",
                 "Raise NetBT priority (default 2001)",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider",
                 "NetbtPriority", "REG_DWORD", 7),

        # --- 54: LLMNR multicast disable ---
        RegTweak(54, "LLMNR Multicast Disable",
                 "Disable Link-Local Multicast Name Resolution (security + latency)",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient",
                 "EnableMulticast", "REG_DWORD", 0),

        # --- 55-57: DNS server + DNS-over-HTTPS ---
        DnsServerTweak(55, "Set DNS to Cloudflare (1.1.1.1)",
                       "Point this adapter at Cloudflare's 1.1.1.1 / 1.0.0.1 resolvers",
                       "1.1.1.1", "1.0.0.1"),

        DohTemplateTweak(56, "DNS-over-HTTPS (1.1.1.1)",
                         "Encrypt DNS queries to 1.1.1.1 via Windows-native DoH",
                         "1.1.1.1", "https://cloudflare-dns.com/dns-query"),

        DohTemplateTweak(57, "DNS-over-HTTPS (1.0.0.1)",
                         "Encrypt DNS queries to 1.0.0.1 via Windows-native DoH",
                         "1.0.0.1", "https://cloudflare-dns.com/dns-query"),

        # --- 58-59: Delivery Optimization + NIC MSI mode ---
        RegTweak(58, "Disable Delivery Optimization P2P",
                 "Stop Windows Update from uploading/downloading update chunks "
                 "to/from other PCs in the background, which steals bandwidth while gaming",
                 r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization",
                 "DODownloadMode", "REG_DWORD", 0),

        NicMsiModeTweak(59, "NIC MSI Mode",
                        "Switch the network adapter to Message-Signaled Interrupts, "
                        "reducing interrupt latency (same benefit as GPU MSI Mode)"),
    ]