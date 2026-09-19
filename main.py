"""Sensible Tweaks - entry point with crash reporting."""
import sys
import traceback


def _crash(exc: BaseException) -> None:
    from datetime import datetime
    from pathlib import Path

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    print()
    print("=" * 62)
    print("  CRASH")
    print("=" * 62)
    print(tb)

    try:
        log = Path(__file__).resolve().parent / "Logs" / "crash.log"
        log.parent.mkdir(exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"\n\n=== {datetime.now()} ===\n")
            f.write(tb)
        print(f"  Written to: {log}")
    except Exception:
        pass

    try:
        input("  Press Enter to close...")
    except EOFError:
        pass


def _run() -> int:
    from core.elevation import ensure_admin
    if not ensure_admin():
        return 0
    from modules.main_menu import MainMenu
    MainMenu().run()
    return 0


def main() -> int:
    try:
        return _run()
    except KeyboardInterrupt:
        return 0
    except BaseException as e:
        _crash(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())