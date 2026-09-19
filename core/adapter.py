"""NIC discovery and advanced-property manipulation.

Return-value contract for set_* functions:
    True   applied AND verified by read-back
    False  property exists, set attempted, but value did not change
    None   property does not exist on this adapter
"""
import json
from dataclasses import dataclass
from .shell import powershell, ps_quote


@dataclass
class Adapter:
    name: str
    description: str
    mac: str
    if_guid: str
    media_type: str


def list_adapters(up_only: bool = True):
    flt = "{ $_.Status -eq 'Up' }" if up_only else "{ $true }"
    ps = (
        f"Get-NetAdapter | Where-Object {flt} | "
        f"Select-Object Name, InterfaceDescription, MacAddress, "
        f"InterfaceGuid, PhysicalMediaType | ConvertTo-Json -Compress"
    )
    out = powershell(ps).stdout.strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    return [
        Adapter(
            name=d.get("Name", ""),
            description=d.get("InterfaceDescription", ""),
            mac=d.get("MacAddress", ""),
            if_guid=d.get("InterfaceGuid", ""),
            media_type=d.get("PhysicalMediaType", "") or "",
        )
        for d in data
    ]


def pick_adapter(kind: str):
    for a in list_adapters(up_only=True):
        mt = a.media_type.lower()
        if kind == "eth" and "802.3" in mt:
            return a
        if kind == "wifi" and ("802.11" in mt or "wireless" in mt or "wi-fi" in mt):
            return a
    return None


# ---------------------------------------------------------------------------
# advanced property helpers
# ---------------------------------------------------------------------------

def get_advanced(adapter_name: str, prop: str):
    """Return current DisplayValue, or None if the property doesn't exist."""
    ps = (
        f"$p = Get-NetAdapterAdvancedProperty -Name '{ps_quote(adapter_name)}' "
        f"-DisplayName '{ps_quote(prop)}' -ErrorAction SilentlyContinue; "
        f"if ($p) {{ $p.DisplayValue }} else {{ '__MISSING__' }}"
    )
    out = powershell(ps).stdout.strip()
    if not out or out == "__MISSING__":
        return None
    return out


def set_advanced(adapter_name: str, prop: str, value: str):
    """Returns True (applied+verified), False (exists but failed), None (missing)."""
    # Does the property exist at all?
    exists = (
        f"$p = Get-NetAdapterAdvancedProperty -Name '{ps_quote(adapter_name)}' "
        f"-DisplayName '{ps_quote(prop)}' -ErrorAction SilentlyContinue; "
        f"if ($p) {{ 'YES' }} else {{ 'NO' }}"
    )
    if "YES" not in powershell(exists).stdout:
        return None

    # Try to set it
    set_ps = (
        f"try {{ Set-NetAdapterAdvancedProperty -Name '{ps_quote(adapter_name)}' "
        f"-DisplayName '{ps_quote(prop)}' -DisplayValue '{ps_quote(value)}' -ErrorAction Stop; 'OK' }} "
        f"catch {{ 'FAIL' }}"
    )
    if "OK" not in powershell(set_ps).stdout:
        return False

    # Verify by reading back
    actual = get_advanced(adapter_name, prop)
    if actual is None:
        return False
    return actual.strip().lower() == value.strip().lower()


def get_power_saving(adapter_name: str):
    """Return 'Enabled' / 'Disabled', or None if unsupported."""
    ps = (
        f"try {{ "
        f"$p = Get-NetAdapterPowerManagement -Name '{ps_quote(adapter_name)}' -ErrorAction Stop; "
        f"if ($p.AllowComputerToTurnOffDevice) {{ $p.AllowComputerToTurnOffDevice }} "
        f"else {{ '__NONE__' }} "
        f"}} catch {{ '__NONE__' }}"
    )
    out = powershell(ps).stdout.strip()
    if out in ("Enabled", "Disabled"):
        return out
    # Fall back to driver property
    for prop in ("Power Saving Mode", "Green Ethernet",
                 "Reduce Power", "Energy Efficient Ethernet",
                 "Advanced EEE"):
        v = get_advanced(adapter_name, prop)
        if v is not None:
            return v
    return None


def set_power_saving(adapter_name: str, enabled: bool):
    """Returns True (applied+verified), False (exists but failed), None (unsupported)."""
    val = "Enabled" if enabled else "Disabled"

    # Path 1: cmdlet
    check_ps = (
        f"try {{ "
        f"$p = Get-NetAdapterPowerManagement -Name '{ps_quote(adapter_name)}' -ErrorAction Stop; "
        f"if ($p.AllowComputerToTurnOffDevice) {{ $p.AllowComputerToTurnOffDevice }} "
        f"else {{ '__NONE__' }} "
        f"}} catch {{ '__NONE__' }}"
    )
    current = powershell(check_ps).stdout.strip()
    if current in ("Enabled", "Disabled"):
        set_ps = (
            f"try {{ Set-NetAdapterPowerManagement -Name '{ps_quote(adapter_name)}' "
            f"-AllowComputerToTurnOffDevice {val} -ErrorAction Stop; 'OK' }} "
            f"catch {{ 'FAIL' }}"
        )
        if "OK" in powershell(set_ps).stdout:
            actual = powershell(check_ps).stdout.strip()
            if actual.lower() == val.lower():
                return True
        # fall through to driver property

    # Path 2: driver-level advanced property
    for prop in ("Power Saving Mode", "Green Ethernet", "Reduce Power",
                 "Energy Efficient Ethernet", "Advanced EEE"):
        r = set_advanced(adapter_name, prop, val)
        if r is not None:
            return r

    return None