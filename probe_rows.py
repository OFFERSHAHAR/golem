"""ניסוי מיפוי: שם רצועה אחת ברוחב 256 ברצועת שורות אחת, ובודק לאן היא נופלת.
    python probe_rows.py --band 0      שורות 0..63   (רצועת J1 לפי המודל הנוכחי)
    python probe_rows.py --band 0 --x0 0
"""
import argparse, time, numpy as np
from PIL import Image, ImageDraw, ImageFont
from colorlight.driver import ColorlightWall
import wall_map as WM

ap = argparse.ArgumentParser()
ap.add_argument("--iface", default=r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}")
ap.add_argument("--band", type=int, default=0, help="איזו רצועת 64 שורות בקנבס")
ap.add_argument("--x0", type=int, default=0, help="עמודת התחלה בקנבס")
ap.add_argument("--width", type=int, default=256)
ap.add_argument("--seconds", type=float, default=90)
a = ap.parse_args()

COLORS = [(210,30,30), (30,180,70), (40,90,230), (230,180,20)]
strip = Image.new("RGB", (a.width, 64), (0, 0, 0))
d = ImageDraw.Draw(strip)
try:
    font = ImageFont.truetype("arial.ttf", 42)
except OSError:
    font = None
for n in range(a.width // 64):
    x = n * 64
    d.rectangle([x, 0, x+63, 63], fill=COLORS[n % 4], outline=(255, 255, 255))
    d.text((x+20, 8), str(n+1), fill=(255, 255, 255), font=font)

canvas = np.zeros((WM.CANVAS_H, WM.CANVAS_W, 3), np.uint8)
y = a.band * 64
w = min(a.width, WM.CANVAS_W - a.x0)
canvas[y:y+64, a.x0:a.x0+w] = np.asarray(strip, dtype=np.uint8)[:, :w]

wall = ColorlightWall(iface=a.iface, width=WM.CANVAS_W, height=WM.CANVAS_H)
wall.set_brightness(45)
print(f"band={a.band} rows {y}..{y+63}  x {a.x0}..{a.x0+w-1}", flush=True)
t0 = time.monotonic()
while time.monotonic() - t0 < a.seconds:
    wall.send_frame(canvas)
    time.sleep(0.05)
