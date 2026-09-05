"""map_probe.py - ממפה איזה אזור בקנבס נוחת על איזה פאנל פיזי.
כל אריח 64x64 בקנבס מקבל צבע ייחודי; מצלמים פעם אחת ומזהים.
"""
import argparse, time, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

ap = argparse.ArgumentParser()
ap.add_argument("--iface", required=True)
ap.add_argument("--mac", default="ff:ff:ff:ff:ff:ff")
ap.add_argument("--brightness", type=int, default=25)
ap.add_argument("--w", type=int, default=256)
ap.add_argument("--h", type=int, default=256)
ap.add_argument("--seconds", type=float, default=25)
a = ap.parse_args()

W, H = a.w, a.h
COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255),
    (255, 255, 0), (0, 255, 255), (255, 0, 255), (255, 128, 0),
    (128, 0, 255), (0, 128, 64), (128, 128, 128), (255, 96, 160),
    (64, 64, 255), (160, 255, 64), (255, 200, 120), (90, 0, 0),
]
NAMES = ["red", "green", "blue", "white", "yellow", "cyan", "magenta", "orange",
         "purple", "darkgreen", "gray", "pink", "lightblue", "lime", "peach", "darkred"]

img = np.zeros((H, W, 3), np.uint8)
i = 0
for ty in range(0, H, 64):
    for tx in range(0, W, 64):
        c = COLORS[i % len(COLORS)]
        img[ty:ty + 64, tx:tx + 64] = c
        print(f"tile x={tx:3d} y={ty:3d}  ->  {NAMES[i % len(NAMES)]}")
        i += 1

wall = ColorlightWall(iface=a.iface, width=W, height=H, dst_mac=a.mac, brightness=a.brightness)
print(f"\nמשדר {W}x{H} למשך {a.seconds} שניות - תצלם את הקיר", flush=True)
t0 = time.time()
while time.time() - t0 < a.seconds:
    wall.send_frame(img)
    time.sleep(0.08)
wall.close()
print("done")
