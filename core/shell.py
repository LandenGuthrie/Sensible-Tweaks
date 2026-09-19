"""Thin wrappers around subprocess for cmd / powershell / netsh / reg.

run() never raises on "exe not found" or timeouts. It returns a CompletedProcess
with returncode=9001 (missing) or 9002 (timeout) so callers can check rc.
"""
import subprocess

CREATE_NO_WINDOW = 0x08000000

RC_MISSING = 9001
RC_TIMEOUT = 9002


def run(cmd, timeout: int = 60):
    shell_flag = isinstance(cmd, str)
    try:
        return subprocess.run(
            cmd,
            shell=shell_flag,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(
            args=cmd, returncode=RC_MISSING,
            stdout="", stderr=f"Executable not found: {e}",
        )
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args=cmd, returncode=RC_TIMEOUT,
            stdout=(e.stdout or ""), stderr=f"Timed out after {timeout}s",
        )
    except OSError as e:
        return subprocess.CompletedProcess(
            args=cmd, returncode=RC_MISSING,
            stdout="", stderr=f"OS error: {e}",
        )


def ps_quote(value) -> str:
    """Escape a value for safe interpolation inside a single-quoted
    PowerShell string literal (doubles embedded single quotes)."""
    return str(value).replace("'", "''")


def netsh(*args: str):
    return run(["netsh", *args])


def reg(*args: str):
    return run(["reg", *args])


def powershell(script: str, timeout: int = 60):
    return run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        timeout=timeout,
    )


def cmd(command: str, timeout: int = 60):
    return run(command, timeout=timeout)