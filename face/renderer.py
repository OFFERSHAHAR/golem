"""
face/renderer.py — תהליך הפרצוף. רץ לבד, 60fps, ולא נעצר בשביל אף אחד.

מקבל פקודות ב-UDP על 127.0.0.1:9999 בפורמט:
    {"state":"speak","amp":0.62,"gaze":[0.2,-0.1],"emote":"pulse"}

    python -m face.renderer --out preview          # שומר PNG כל שנייה, בלי חומרה
    python -m face.renderer --out wall --iface "Ethernet 2"

עיקרון: אם המוח נופל, הפרצוף ממשיך לנשום. אף פעם לא לחסום את הלולאה הזאת.
"""
import argparse
import json
import socket
import time

import numpy as np

from .spark import Spark

HOST, PORT = "127.0.0.1", 9999
FPS = 60


def run(out="preview", iface=None, mac=None, theme="dark", brightness=0.8, wall_brightness=35):
    face = Spark(theme=theme, brightness=brightness)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.setblocking(False)

    wall = None
    if out == "wall":
        from colorlight.driver import ColorlightWall
        wall = ColorlightWall(iface=iface, dst_mac=mac, brightness=wall_brightness)
        print(f"מחובר לקיר דרך {iface} → {mac}")
    else:
        print("מצב תצוגה מקדימה — שומר face_preview.png כל שנייה")

    last_cmd, last_png, frames, t_fps = time.monotonic(), 0.0, 0, time.monotonic()
    period = 1.0 / FPS

    try:
        while True:
            t0 = time.monotonic()

            # --- פקודות נכנסות: לרוקן את התור, להשתמש רק באחרונה ---
            cmd = None
            while True:
                try:
                    data, _ = sock.recvfrom(2048)
                    cmd = data
                except BlockingIOError:
                    break
            if cmd:
                try:
                    m = json.loads(cmd)
                    face.set(state=m.get("state"), amp=m.get("amp"),
                             gaze=m.get("gaze"), emote=m.get("emote"))
                    last_cmd = t0
                except Exception as e:
                    print("פקודה לא תקינה:", e)

            # --- אין קשר עם המוח 8 שניות? חוזרים למנוחה, אבל ממשיכים לחיות ---
            if t0 - last_cmd > 8 and face.state != "idle":
                face.set(state="idle", amp=0)

            img = face.render()

            if wall:
                wall.send_frame(np.asarray(img, dtype=np.uint8))
            elif t0 - last_png > 1.0:
                img.resize((384, 384)).save("face_preview.png")
                last_png = t0

            frames += 1
            if t0 - t_fps >= 5:
                print(f"{frames / (t0 - t_fps):.1f} fps · state={face.state}")
                frames, t_fps = 0, t0

            dt = period - (time.monotonic() - t0)
            if dt > 0:
                time.sleep(dt)
    except KeyboardInterrupt:
        pass
    finally:
        if wall:
            wall.close()
        sock.close()
        print("\nהפרצוף כבה.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", choices=["preview", "wall"], default="preview")
    ap.add_argument("--iface")
    ap.add_argument("--mac", default="11:22:33:44:55:66")
    ap.add_argument("--theme", choices=["dark", "brand"], default="dark")
    ap.add_argument("--wall-brightness", type=int, default=35)
    a = ap.parse_args()
    if a.out == "wall" and not a.iface:
        raise SystemExit("צריך --iface. הרץ python -m colorlight.driver כדי לראות רשימה.")
    run(a.out, a.iface, a.mac, a.theme, wall_brightness=a.wall_brightness)
