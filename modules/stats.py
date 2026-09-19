from datetime import datetime

from core import ui, shell, backup, benchmark


def menu() -> None:
    while True:
        ui.clear()
        ui.header("NETWORK STATS")
        print("     [1]  Capture snapshot")
        print("     [2]  Compare last two snapshots")
        print("     [0]  Back")
        print()
        c = ui.prompt()
        if c == "1":
            _capture()
        elif c == "2":
            _compare()
        elif c == "0":
            return


def _capture() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = backup.LOGS_DIR / f"stats_{stamp}.txt"
    with out.open("w", encoding="utf-8") as f:
        f.write(f"Sensible Tweaks - Snapshot {datetime.now()}\n\n")
        for host in ("8.8.8.8", "1.1.1.1"):
            s = benchmark.ping_stats(host, 20)
            f.write(f"--- Ping {host} (20) ---\n")
            f.write(f"avg={s['avg']}ms  min={s['min']}ms  max={s['max']}ms  "
                    f"n={s['count']}\n\n")
        f.write("--- netsh int tcp show global ---\n")
        f.write(shell.netsh("int", "tcp", "show", "global").stdout)
    ui.ok(f"Saved: {out.name}")
    ui.pause()


def _compare() -> None:
    files = sorted(backup.LOGS_DIR.glob("stats_*.txt"), reverse=True)[:2]
    if len(files) < 2:
        ui.err("Need at least two snapshots.")
        ui.pause()
        return
    ui.clear()
    ui.header("COMPARE SNAPSHOTS")
    for f in files:
        print(f"   --- {f.name} ---")
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith(("avg=", "--- Ping")):
                print("     " + line)
        print()
    ui.pause()