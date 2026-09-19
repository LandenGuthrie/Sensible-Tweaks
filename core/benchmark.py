"""Latency measurement via PowerShell Test-Connection."""
from .shell import powershell


def ping_average(host: str = "8.8.8.8", count: int = 10) -> float:
    ps = (
        f"$r = Test-Connection {host} -Count {count} -ErrorAction SilentlyContinue "
        f"| Measure-Object -Property ResponseTime -Average; "
        f"if ($r.Average) {{ [math]::Round($r.Average, 2) }} else {{ 9999 }}"
    )
    out = powershell(ps, timeout=count * 2 + 15).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 9999.0


def ping_stats(host: str = "8.8.8.8", count: int = 20) -> dict:
    ps = (
        f"$t = (Test-Connection {host} -Count {count} -ErrorAction SilentlyContinue)"
        f".ResponseTime; "
        f"if ($t.Count -gt 0) {{ "
        f"$s = $t | Measure-Object -Average -Maximum -Minimum; "
        f"'{{0}}|{{1}}|{{2}}|{{3}}' -f [math]::Round($s.Average,2), $s.Maximum, "
        f"$s.Minimum, $t.Count }} else {{ '9999|9999|9999|0' }}"
    )
    out = powershell(ps, timeout=count * 2 + 15).stdout.strip()
    try:
        avg, mx, mn, cnt = out.split("|")
        return {"avg": float(avg), "max": float(mx), "min": float(mn), "count": int(cnt)}
    except Exception:
        return {"avg": 9999.0, "max": 9999.0, "min": 9999.0, "count": 0}