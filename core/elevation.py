"""Admin elevation helpers."""
import ctypes
import os
import sys


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin() -> bool:
    if is_admin():
        return True
    try:
        # argv[0] may be a bare relative filename (e.g. "main.py") -- resolve it
        # to an absolute path so the elevated relaunch can find it regardless
        # of what working directory Windows hands the new (UAC) process.
        script = os.path.abspath(sys.argv[0])
        script_dir = os.path.dirname(script)
        params = " ".join(f'"{a}"' for a in [script, *sys.argv[1:]])

        print("Requesting administrator privileges (UAC prompt)...")
        # SW_SHOWNORMAL = 1. Return value <= 32 means ShellExecuteW failed
        # (see MSDN); a common cause is the user clicking "No" on the prompt.
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, script_dir, 1
        )
        if rc <= 32:
            print(f"Elevation request failed or was declined (code {rc}).")
            print("Sensible Tweaks needs administrator rights to run.")
    except Exception as e:
        print(f"Failed to elevate: {e}")
    return False