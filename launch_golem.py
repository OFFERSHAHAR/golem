"""Small Windows launcher behind CLAUDE.bat."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PIDS = DATA / "golem-processes.json"
PYTHON = Path(sys.executable)
URL = "http://127.0.0.1:8765/"
PROFILE = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "GOLEM" / "owner-lbph.yml"


def send_shutdown() -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b'{"shutdown":true}', ("127.0.0.1", 9999))
    except OSError:
        pass


def command_line(pid: int) -> str:
    query = f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", query],
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.stdout.strip()


def stop() -> None:
    send_shutdown()
    time.sleep(0.8)
    try:
        entries = json.loads(PIDS.read_text(encoding="utf-8"))
    except Exception:
        entries = []
    for entry in entries:
        try:
            pid, marker = int(entry["pid"]), str(entry["marker"])
        except (KeyError, TypeError, ValueError):
            continue
        if marker not in command_line(pid):
            continue
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    PIDS.unlink(missing_ok=True)


def camera_ready() -> bool:
    try:
        import cv2

        camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        ok, _ = camera.read()
        camera.release()
        return bool(ok)
    except Exception:
        return False


def enroll() -> int:
    stop()
    if not camera_ready():
        print("No camera is connected. Enrollment was skipped.")
        return 2
    return subprocess.call(
        [str(PYTHON), "-u", "-B", "-m", "senses.vision", "--cam", "0",
         "--enroll", "עופר"],
        cwd=ROOT,
    )


def spawn(marker: str, args: list[str], log_name: str) -> dict[str, object]:
    log = (ROOT / log_name).open("ab")
    try:
        process = subprocess.Popen(
            [str(PYTHON), "-u", "-B", *args],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                           | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)),
        )
    finally:
        log.close()
    return {"pid": process.pid, "marker": marker}


def wait_for_control(seconds: float = 6.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def start(with_vision: bool = False) -> int:
    stop()
    if with_vision and not camera_ready():
        print("No camera is connected. Starting display only.")
        with_vision = False
    if with_vision and not PROFILE.exists() and enroll() != 0:
        return 2

    DATA.mkdir(parents=True, exist_ok=True)
    entries = [spawn(
        "golem_live.py",
        ["golem_live.py", "--mode", "critter", "--j2", "spark",
         "--brightness", "25", "--fps", "30", "--idle", "0"],
        "wall.log",
    )]
    if with_vision:
        entries.append(spawn(
            "senses.vision",
            ["-m", "senses.vision", "--cam", "0", "--flip", "--speak",
             "--show", "--analyze-seconds", "10"],
            "vision.log",
        ))
    entries.append(spawn("j2_control.py", ["j2_control.py"], "control.log"))
    PIDS.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    if not wait_for_control():
        print("ERROR: the control panel did not start. See control.log.")
        return 1
    if os.environ.get("GOLEM_NO_BROWSER") != "1":
        webbrowser.open(URL)
    print("GOLEM is running: J1=Claude, J2=spark, J4=128x64 ready.")
    print(f"Control panel: {URL}")
    print("Camera and microphone are off." if not with_vision else "Camera is on; microphone is off.")
    return 0


def main() -> int:
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    if action == "stop":
        stop()
        print("GOLEM stopped.")
        return 0
    if action == "enroll":
        return enroll()
    if action == "vision":
        return start(with_vision=True)
    if action not in {"start", ""}:
        print("Usage: CLAUDE.bat [start|stop|vision|enroll]")
        return 2
    return start()


if __name__ == "__main__":
    raise SystemExit(main())
