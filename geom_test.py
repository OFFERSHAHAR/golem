"""geom_test.py - סורק גדלי קנבס ומצלם כל אחד, כדי לגלות את הגיאומטריה שהכרטיס מוגדר אליה."""
import time, sys, os
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall

IFACE = r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}"
MAC = "11:22:33:44:55:66"
GEOMS = [(64, 64), (128, 64), (64, 128), (128, 128), (256, 64), (256, 128), (256, 256)]

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
for _ in range(15):
    cap.read(); time.sleep(0.05)


def stream(w, h, img, secs):
    wall = ColorlightWall(iface=IFACE, width=w, height=h, dst_mac=MAC, brightness=35)
    t0 = time.time()
    while time.time() - t0 < secs:
        wall.send_frame(img); time.sleep(0.04)
    wall.sock.close()


def grab(path, secs=3):
    t0 = time.time(); f = None
    while time.time() - t0 < secs:
        ok, x = cap.read()
        if ok: f = x
        time.sleep(0.03)
    if f is not None:
        cv2.imwrite(path, f, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        print("saved", path, flush=True)


for w, h in GEOMS:
    for cw, ch in GEOMS:                       # ניקוי מלא בכל הגדלים
        stream(cw, ch, np.zeros((ch, cw, 3), np.uint8), 0.4)
    white = np.full((h, w, 3), 255, np.uint8)
    import threading
    stop = threading.Event()
    def pump(w=w, h=h, img=white):
        wall = ColorlightWall(iface=IFACE, width=w, height=h, dst_mac=MAC, brightness=35)
        while not stop.is_set():
            wall.send_frame(img); time.sleep(0.04)
        wall.sock.close()
    th = threading.Thread(target=pump, daemon=True); th.start()
    time.sleep(1.5)
    grab(f"g_{w}x{h}.jpg", 2.5)
    stop.set(); th.join(timeout=3)

cap.release()
print("done")
