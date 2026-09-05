"""בדיקת קיר: תמונת בדיקה סטטית, ואז 10 שניות של הניצוץ.
    python scripts/test_wall.py --iface "Ethernet 2" --mac aa:bb:cc:dd:ee:ff
"""
import argparse, time, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from colorlight.driver import ColorlightWall
from face.spark import Spark

ap = argparse.ArgumentParser()
ap.add_argument("--iface", required=True)
ap.add_argument("--mac", required=True)
ap.add_argument("--brightness", type=int, default=30)
a = ap.parse_args()

wall = ColorlightWall(iface=a.iface, dst_mac=a.mac, brightness=a.brightness)

# 1. ארבעה רבעים בארבעה צבעים — מאמת מיד שהמיפוי 2×2 נכון
img = np.zeros((128, 128, 3), np.uint8)
img[:64, :64] = (255, 0, 0)      # J1 שמאל-עליון  — אדום
img[:64, 64:] = (0, 255, 0)      # J2 ימין-עליון   — ירוק
img[64:, :64] = (0, 0, 255)      # J3 שמאל-תחתון  — כחול
img[64:, 64:] = (255, 255, 255)  # J4 ימין-תחתון   — לבן
wall.send_frame(img)
print("רבעים: אדום ש״ע · ירוק י״ע · כחול ש״ת · לבן י״ת — אם לא ככה, המיפוי הפוך")
time.sleep(5)

# 2. הניצוץ חי
face = Spark()
t0 = time.time()
while time.time() - t0 < 10:
    face.state = "speak"
    face.amp = abs(np.sin((time.time() - t0) * 4)) * .9
    wall.send_frame(np.asarray(face.render(), dtype=np.uint8))
    time.sleep(1 / 60)
wall.close()
