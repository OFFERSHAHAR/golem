"""blink.py - מבחן חד משמעי עם הדרייבר המתוקן."""
import argparse, time, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

ap = argparse.ArgumentParser()
ap.add_argument("--iface", required=True)
ap.add_argument("--mac", default="11:22:33:44:55:66")
ap.add_argument("--w", type=int, default=128)
ap.add_argument("--h", type=int, default=128)
ap.add_argument("--brightness", type=int, default=40)
ap.add_argument("--cycles", type=int, default=5)
a = ap.parse_args()

W, H = a.w, a.h
WHITE = np.full((H, W, 3), 255, np.uint8)
BLACK = np.zeros((H, W, 3), np.uint8)

wall = ColorlightWall(iface=a.iface, width=W, height=H,
                      dst_mac=a.mac, brightness=a.brightness)
print(f"mac={a.mac}  {W}x{H}  brightness={a.brightness}%", flush=True)
for i in range(a.cycles):
    for name, img in (("לבן", WHITE), ("שחור", BLACK)):
        print(f"  {i+1}: {name}", flush=True)
        t = time.time()
        while time.time() - t < 1.5:
            wall.send_frame(img)
            time.sleep(0.05)
wall.sock.close()
print("סיום")
