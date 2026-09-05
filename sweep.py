"""sweep.py - סורק פסים ומודד כמה אור יצא, לפי בהירות ממוצעת בפריים המצלמה.
מגלה איזה חלק מהקנבס בכלל מגיע לפאנלים.
  python sweep.py x 256 256 16
"""
import time, sys, os, threading
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

axis = sys.argv[1] if len(sys.argv) > 1 else "x"
W = int(sys.argv[2]) if len(sys.argv) > 2 else 256
H = int(sys.argv[3]) if len(sys.argv) > 3 else 256
STEP = int(sys.argv[4]) if len(sys.argv) > 4 else 16
IFACE = r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}"

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
for _ in range(20):
    cap.read(); time.sleep(0.04)

wall = ColorlightWall(iface=IFACE, width=W, height=H,
                      dst_mac="11:22:33:44:55:66", brightness=60)
cur = np.zeros((H, W, 3), np.uint8)
stop = threading.Event()
threading.Thread(target=lambda: [ (wall.send_frame(cur), time.sleep(0.04))
                                  for _ in iter(lambda: not stop.is_set(), False) ],
                 daemon=True).start()


def level(img, secs=1.2):
    global cur
    cur = img
    t0 = time.time(); vals = []
    while time.time() - t0 < secs:
        ok, f = cap.read()
        if ok: vals.append(f.mean())
        time.sleep(0.03)
    return float(np.mean(vals[-6:])) if vals else 0.0


base = level(np.zeros((H, W, 3), np.uint8), 2.5)
print(f"רקע (הכל שחור): {base:.1f}\n", flush=True)
n = (W if axis == "x" else H) // STEP
for i in range(n):
    img = np.zeros((H, W, 3), np.uint8)
    if axis == "x":
        img[:, i*STEP:(i+1)*STEP] = 255
    else:
        img[i*STEP:(i+1)*STEP, :] = 255
    v = level(img)
    bar = "#" * int(max(0, v - base) * 2)
    print(f"{axis} {i*STEP:3d}-{(i+1)*STEP-1:3d}  {v:6.1f}  Δ{v-base:+6.1f} {bar}", flush=True)

stop.set(); time.sleep(0.3)
wall.blank(); wall.sock.close(); cap.release()
print("done")
