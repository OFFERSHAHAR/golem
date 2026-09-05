"""see.py - משדר תבנית לקיר ומצלם אותה במצלמה, בסנכרון. הכלי לעבודה עצמאית.

  python see.py --pattern bandsx --w 256 --h 64 --band 64 --out shot.jpg
  python see.py --pattern solid --color 255,255,255
  python see.py --pattern rect --rx 0 --ry 0 --rw 64 --rh 64
"""
import argparse, threading, time, sys, os
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

ap = argparse.ArgumentParser()
ap.add_argument("--iface", default=r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}")
ap.add_argument("--mac", default="11:22:33:44:55:66")
ap.add_argument("--w", type=int, default=256)
ap.add_argument("--h", type=int, default=64)
ap.add_argument("--brightness", type=int, default=30)
ap.add_argument("--pattern", default="bandsx")
ap.add_argument("--band", type=int, default=64)
ap.add_argument("--color", default="255,255,255")
ap.add_argument("--rx", type=int, default=0)
ap.add_argument("--ry", type=int, default=0)
ap.add_argument("--rw", type=int, default=64)
ap.add_argument("--rh", type=int, default=64)
ap.add_argument("--bgr", type=int, default=1)
ap.add_argument("--cam", type=int, default=0)
ap.add_argument("--out", default="shot.jpg")
ap.add_argument("--seconds", type=float, default=14)
a = ap.parse_args()

W, H, B = a.w, a.h, a.band
COLORS = [(255,0,0),(0,255,0),(0,0,255),(255,255,255),
          (255,255,0),(0,255,255),(255,0,255),(255,120,0)]
NAMES = ["red","green","blue","white","yellow","cyan","magenta","orange"]

img = np.zeros((H, W, 3), np.uint8)
if a.pattern == "solid":
    img[:, :] = tuple(int(v) for v in a.color.split(","))
elif a.pattern == "bandsx":
    for i in range(W // B):
        img[:, i*B:(i+1)*B] = COLORS[i % 8]
        print(f"x {i*B:3d}-{(i+1)*B-1:3d} -> {NAMES[i%8]}")
elif a.pattern == "bandsy":
    for i in range(H // B):
        img[i*B:(i+1)*B, :] = COLORS[i % 8]
        print(f"y {i*B:3d}-{(i+1)*B-1:3d} -> {NAMES[i%8]}")
elif a.pattern == "rect":
    img[a.ry:a.ry+a.rh, a.rx:a.rx+a.rw] = tuple(int(v) for v in a.color.split(","))
    print(f"rect x={a.rx} y={a.ry} {a.rw}x{a.rh} color={a.color}")

stop = threading.Event()

def pump():
    wall = ColorlightWall(iface=a.iface, width=W, height=H, dst_mac=a.mac,
                          brightness=a.brightness, bgr=bool(a.bgr))
    while not stop.is_set():
        wall.send_frame(img)
        time.sleep(0.04)
    wall.blank()
    wall.sock.close()

th = threading.Thread(target=pump, daemon=True)
th.start()

cap = cv2.VideoCapture(a.cam, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
t0 = time.time()
frame = None
while time.time() - t0 < a.seconds:
    ok, f = cap.read()
    if ok:
        frame = f
    time.sleep(0.03)
cap.release()
stop.set(); th.join(timeout=5)
if frame is not None:
    cv2.imwrite(a.out, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    print("saved", a.out)
else:
    print("camera failed")
