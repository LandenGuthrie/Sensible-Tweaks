"""Benchmark each tweak, keep what helps, revert what doesn't."""
import time
from datetime import datetime

from core import ui, backup, benchmark, adapter as adp
from tweaks.network import build_network_tweaks
from tweaks.base import TweakContext

TOLERANCE_MS = 2.0
COOLDOWN_S = 2.0


def run(kind: str) -> None:
    a = adp.pick_adapter(kind)
    if not a:
        ui.clear()
        ui.err(f"No active {kind} adapter.")
        ui.pause()
        return

    ui.clear()
    ui.header(f"AUTO APPLY - {kind.upper()} - {a.name}")
    print("   Each tweak is benchmarked against 8.8.8.8 (10 pings).")
    print(f"   A tweak is reverted if average latency rises by >{TOLERANCE_MS:.0f} ms.")
    print("   Approximate duration: 8-10 minutes.")
    print()
    ui.pause("Press Enter to begin...")

    log_path = backup.LOGS_DIR / f"auto_{kind}_{datetime.now():%Y%m%d_%H%M%S}.log"
    log = log_path.open("w", encoding="utf-8")

    def L(msg: str) -> None:
        print("   " + msg)
        log.write(msg + "\n")
        log.flush()

    ctx = TweakContext(adapter=a)
    L(f"Adapter : {a.name}")
    L(f"Started : {datetime.now()}")
    L("")

    L("Taking baseline...")
    base = benchmark.ping_average()
    L(f"Baseline: {base} ms")

    for t in build_network_tweaks():
        L("")
        L("-" * 58)
        L(f"Testing {t.id:>2}: {t.name}")
        if not t.apply(ctx):
            L("  [SKIP] Could not be applied (adapter unsupported?).")
            continue
        time.sleep(COOLDOWN_S)
        now = benchmark.ping_average()
        delta = now - base
        L(f"  Before={base} ms  After={now} ms  Delta={delta:+.2f} ms")
        if now > base + TOLERANCE_MS:
            t.revert(ctx)
            L("  [REVERT] Worse - undone.")
        else:
            L("  [KEEP] Neutral or better.")
            base = now

    L("")
    L(f"Finished: {datetime.now()}")
    log.close()
    ui.ok(f"Done. Log: {log_path.name}")
    ui.pause()