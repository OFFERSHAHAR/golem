"""stripes.py - פסים בצבעים ידועים לזיהוי מיפוי הקנבס אל הפאנלים.
  --axis x  : צבע משתנה לפי העמודה (מגלה מיפוי אופקי)
  --axis y  : צבע משתנה לפי השורה (מגלה מיפוי אנכי)
"""
import argparse, time, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

ap = argparse.ArgumentParser()
ap.add_argument("--iface", required=True)
ap.add_argument("--mac", default="ff:ff:ff:ff:ff:ff")
ap.add_argument("--brightness", type=int, default=20)
ap.add_argument("--w", type=int, default=256)
ap.add_argument("--h", type=int, default=256)
ap.add_argument("--band", type=int, default=32)
ap.add_argument("--axis", choices=["x", "y"], default="x")
ap.add_argument("--seconds", type=float, default=30)
a = ap.parse_args()

W, H, B = a.w, a.h, a.band
COLORS = [(255,0,0),(0,255,0),(0,0,255),(255,255,255),
          (255,255,0),(0,255,255),(255,0,255),(255,120,0)]
NAMES = ["red","green","blue","white","yellow","cyan","magenta","orange"]

img = np.zeros((H, W, 3), np.uint8)
n = (W if a.axis == "x" else H) // B
for i in range(n):
    c = COLORS[i % 8]
    if a.axis == "x":
        img[:, i*B:(i+1)*B] = c
        print(f"x {i*B:3d}-{(i+1)*B-1:3d} -> {NAMES[i%8]}")
    else:
        img[i*B:(i+1)*B, :] = c
        print(f"y {i*B:3d}-{(i+1)*B-1:3d} -> {NAMES[i%8]}")

wall = ColorlightWall(iface=a.iface, width=W, height=H, dst_mac=a.mac, brightness=a.brightness)
print(f"\nמשדר {a.seconds} שניות - תצלם", flush=True)
t0 = time.time()
while time.time() - t0 < a.seconds:
    wall.send_frame(img)
    time.sleep(0.08)
wall.close()
print("done")
