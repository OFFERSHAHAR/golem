"""cam_shot.py - מצלם פריים מכל מצלמה מחוברת ושומר JPG."""
import cv2, sys, time

idxs = [int(x) for x in (sys.argv[1:] or ["0", "1"])]
for i in idxs:
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"cam {i}: לא נפתחה")
        continue
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    for _ in range(12):          # חימום / איזון חשיפה
        cap.read()
        time.sleep(0.05)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print(f"cam {i}: לא הצליח לקרוא פריים")
        continue
    path = f"cam{i}.jpg"
    cv2.imwrite(path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    print(f"cam {i}: נשמר {path}  {frame.shape[1]}x{frame.shape[0]}")
