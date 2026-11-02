"""Keep Windows from idle-sleeping while stage runs are going, then let go.

    py tools/hold_awake.py [pattern,pattern,...]

Holds an ES_SYSTEM_REQUIRED power request (the same kind a media player makes; no settings
change) for as long as any python process whose command line contains `pattern` (default
run_parallel.py) is alive, checking once a minute, then exits and the request ends with it.
Modern standby has wedged long sessions on this laptop before. It does not stop sleep on a
closed lid or a manual Sleep.
"""
import ctypes
import subprocess
import sys
import time

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def alive(patterns):
    """True if any python process's command line contains any of the comma-separated
    patterns."""
    cond = " -or ".join("$_.CommandLine -like '*%s*'" % p for p in patterns.split(","))
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object "
         "{ %s }).Count" % cond],
        capture_output=True, text=True).stdout.strip()
    return out not in ("", "0")


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "run_parallel.py"
    k = ctypes.windll.kernel32
    k.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    t0 = time.time()
    try:
        # a ten-minute grace period, so work queued behind other work is not missed
        idle = 0
        while idle < 10:
            idle = 0 if alive(pattern) else idle + 1
            time.sleep(60)
    finally:
        k.SetThreadExecutionState(ES_CONTINUOUS)
    print("released after %.0f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
