"""שומר על גולם חי: מרים את מנוע הקיר ואת שרת הבקרה, ומחזיר אותם אחרי נפילה.
    python keepalive.py            רץ עד שעוצרים אותו
"""
import subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PYW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
JOBS = [
    ("wall", [str(PY), "golem_live.py", "--brightness", "38", "--idle", "0"]),
    ("control", [str(PYW), "-u", "-B", "golem_app.py", "--port", "8770"]),
]
BACKOFF_MAX = 30


def spawn(name, cmd):
    log = open(ROOT / f"{name}.log", "a", encoding="utf-8")
    err = open(ROOT / f"{name}.err", "a", encoding="utf-8")
    return subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=err)


def main():
    procs = {name: spawn(name, cmd) for name, cmd in JOBS}
    fails = {name: 0 for name, _ in JOBS}
    while True:
        time.sleep(3)
        for name, cmd in JOBS:
            p = procs[name]
            if p.poll() is None:
                fails[name] = 0
                continue
            fails[name] += 1
            wait = min(BACKOFF_MAX, 2 ** fails[name])   # ponytail: backoff פשוט, מספיק לשני תהליכים
            print(f"{name} נפל (קוד {p.returncode}), מרים שוב בעוד {wait}s", flush=True)
            time.sleep(wait)
            procs[name] = spawn(name, cmd)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
