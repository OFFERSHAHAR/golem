"""תבנית בדיקה סטטית ישירות לכרטיס, בלי המנוע ובלי הרנדררים.
    python probe_wall.py            ארבעה בלוקים ממוספרים
    python probe_wall.py --white    הכל לבן
"""
import argparse, numpy as np
from PIL import Image, ImageDraw, ImageFont
from colorlight.driver import ColorlightWall
import wall_map as WM

ap = argparse.ArgumentParser()
ap.add_argument("--iface", default=r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}")
ap.add_argument("--white", action="store_true")
ap.add_argument("--seconds", type=float, default=25)
a = ap.parse_args()

COLORS = [(210,30,30), (30,180,70), (40,90,230), (230,180,20),
          (200,60,200), (60,200,200), (255,255,255), (120,120,120)]
im = Image.new("RGB", (WM.PHYS_W, WM.PHYS_H), (0,0,0))
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 42)
except OSError:
    font = None
if a.white:
    d.rectangle([0, 0, WM.PHYS_W-1, WM.PHYS_H-1], fill=(255,255,255))
else:
    for n in range(WM.PHYS_W // 64):                 # בלוק לכל 64 עמודות
        x = n * 64
        d.rectangle([x, 0, x+63, WM.PHYS_H-1], fill=COLORS[n % len(COLORS)])
        d.rectangle([x, 0, x+63, WM.PHYS_H-1], outline=(255,255,255))
        d.text((x+20, 8), str(n+1), fill=(255,255,255), font=font)

phys = np.asarray(im, dtype=np.uint8)
wall = ColorlightWall(iface=a.iface, width=WM.CANVAS_W, height=WM.CANVAS_H)
wall.set_brightness(45)
canvas = WM.to_canvas(phys)
import time
t0 = time.monotonic()
while time.monotonic() - t0 < a.seconds:            # רענון מתמשך, אחרת הכרטיס נשאר על פריים ישן
    wall.send_frame(canvas)
    time.sleep(0.05)
print("probe done")
