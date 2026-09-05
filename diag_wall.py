"""diag_wall.py - סדרת בדיקות איטית לזיהוי גיאומטריה וצבע על הקיר."""
import argparse, time, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

ap = argparse.ArgumentParser()
ap.add_argument("--iface", required=True)
ap.add_argument("--mac", default="ff:ff:ff:ff:ff:ff")
ap.add_argument("--brightness", type=int, default=25)
ap.add_argument("--w", type=int, default=128)
ap.add_argument("--h", type=int, default=128)
ap.add_argument("--hold", type=float, default=6.0)
a = ap.parse_args()

W, H = a.w, a.h
wall = ColorlightWall(iface=a.iface, width=W, height=H, dst_mac=a.mac, brightness=a.brightness)

def hold(img, label, secs=None):
    secs = secs or a.hold
    print(">>> " + label, flush=True)
    t0 = time.time()
    while time.time() - t0 < secs:
        wall.send_frame(img)
        time.sleep(0.05)

def solid(c):
    img = np.zeros((H, W, 3), np.uint8); img[:, :] = c; return img

hold(solid((0, 0, 0)), "1/7 black", 4)
hold(solid((255, 0, 0)), "2/7 RED full")
hold(solid((0, 255, 0)), "3/7 GREEN full")
hold(solid((0, 0, 255)), "4/7 BLUE full")

img = np.zeros((H, W, 3), np.uint8); img[:H // 2, :] = (255, 255, 255)
hold(img, "5/7 TOP half white")

img = np.zeros((H, W, 3), np.uint8); img[:, :W // 2] = (255, 255, 255)
hold(img, "6/7 LEFT half white")

img = np.zeros((H, W, 3), np.uint8)
img[:H // 2, :W // 2] = (255, 0, 0)
img[:H // 2, W // 2:] = (0, 255, 0)
img[H // 2:, :W // 2] = (0, 0, 255)
img[H // 2:, W // 2:] = (255, 255, 255)
hold(img, "7/7 quadrants R-G-B-W", 10)

wall.close()
print("done - screen should be black")
