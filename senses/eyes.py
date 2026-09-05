"""senses/eyes.py - העיניים. מוצא פנים במצלמה והופך את המיקום למבט.

    python -m senses.eyes                 # רץ ושולח gaze ל-golem_live
    python -m senses.eyes --show          # שומר eyes_debug.jpg כדי לראות מה הוא רואה
"""
import argparse, json, socket, time

import cv2

ADDR = ("127.0.0.1", 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(**kw):
    try:
        sock.sendto(json.dumps(kw).encode(), ADDR)
    except Exception:
        pass


ap = argparse.ArgumentParser()
ap.add_argument("--cam", type=int, default=0)
ap.add_argument("--fps", type=float, default=12)
ap.add_argument("--flip", action="store_true", help="להפוך את ציר X")
ap.add_argument("--greet", type=float, default=25, help="שניות היעדרות שאחריהן הוא שמח לראות אותך")
ap.add_argument("--show", action="store_true")
a = ap.parse_args()

cap = cv2.VideoCapture(a.cam, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

gx = gy = 0.0
last_seen = 0.0
period = 1.0 / a.fps
print("העיניים פקוחות. Ctrl+C כדי לעצור.", flush=True)

try:
    while True:
        t0 = time.time()
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.2)
            continue
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = cascade.detectMultiScale(gray, 1.2, 5, minSize=(60, 60))

        if len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            cx, cy = x + fw / 2, y + fh / 2
            tx = (cx / w) * 2 - 1
            ty = (cy / h) * 2 - 1
            if a.flip:
                tx = -tx
            if t0 - last_seen > a.greet:
                send(expr="happy", state="listen")        # שם לב שנכנסת
                print("רואה אותך", flush=True)
            last_seen = t0
            gx += (tx - gx) * 0.35
            gy += (ty - gy) * 0.35
            send(gaze=[round(gx, 3), round(gy, 3)], passive=True)
        else:
            gx += (0 - gx) * 0.06
            gy += (0 - gy) * 0.06
            if abs(gx) > 0.02 or abs(gy) > 0.02:
                send(gaze=[round(gx, 3), round(gy, 3)], passive=True)

        if a.show:
            for (x, y, fw, fh) in faces:
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 200, 255), 2)
            cv2.imwrite("eyes_debug.jpg", frame)

        dt = period - (time.time() - t0)
        if dt > 0:
            time.sleep(dt)
except KeyboardInterrupt:
    pass
finally:
    cap.release()
    print("העיניים נעצמו.")
