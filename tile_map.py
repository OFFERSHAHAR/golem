"""tile_map.py - מדליק אריח 64x64 אחד בכל פעם בקנבס 256x256,
מצלם, ומדפיס איפה בפריים המצלמה נדלק אור. ככה בונים את המיפוי בלי לנחש.
"""
import time, sys, os, threading
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

IFACE = r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}"
MAC = "11:22:33:44:55:66"
W = H = 256

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
for _ in range(20):
    cap.read(); time.sleep(0.05)

wall = ColorlightWall(iface=IFACE, width=W, height=H, dst_mac=MAC, brightness=60)
cur = np.zeros((H, W, 3), np.uint8)
stop = threading.Event()


def pump():
    while not stop.is_set():
        wall.send_frame(cur)
        time.sleep(0.04)


th = threading.Thread(target=pump, daemon=True)
th.start()


def show(img, secs=1.6):
    global cur
    cur = img
    t0 = time.time(); f = None
    while time.time() - t0 < secs:
        ok, x = cap.read()
        if ok: f = x
        time.sleep(0.03)
    return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16)


ref = show(np.zeros((H, W, 3), np.uint8), 2.5)
cv2.imwrite("tm_ref.jpg", ref.astype(np.uint8))
print("ref mean", ref.mean().round(1), flush=True)

for ty in range(0, H, 64):
    for tx in range(0, W, 64):
        img = np.zeros((H, W, 3), np.uint8)
        img[ty:ty+64, tx:tx+64] = 255
        g = show(img)
        d = np.clip(g - ref, 0, 255).astype(np.uint8)
        _, m = cv2.threshold(d, 45, 255, cv2.THRESH_BINARY)
        n = int(m.sum() // 255)
        if n > 400:
            ys, xs = np.nonzero(m)
            print(f"tile x={tx:3d} y={ty:3d}  lit px={n:6d}  centroid=({int(xs.mean()):4d},{int(ys.mean()):4d})"
                  f"  box=({xs.min()},{ys.min()})-({xs.max()},{ys.max()})", flush=True)
        else:
            print(f"tile x={tx:3d} y={ty:3d}  ---- כלום ({n})", flush=True)
        cv2.imwrite(f"tm_{tx}_{ty}.jpg", cv2.resize(m, (480, 270)))

stop.set(); th.join(timeout=3)
wall.blank(); wall.sock.close(); cap.release()
print("done")
