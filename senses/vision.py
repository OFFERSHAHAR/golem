"""מצלמת GOLEM: מעקב מבט, זיהוי בעלים מקומי וניתוח סצנה ב-Ollama."""
import argparse
import base64
import collections
import datetime as dt
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "GOLEM"
PROFILE = LOCAL_DATA / "owner-lbph.yml"
STATE_FILE = ROOT / "vision_state.json"
DEBUG_FILE = ROOT / "eyes_debug.jpg"
ADDR = ("127.0.0.1", 9999)


def send(sock, **message):
    try:
        sock.sendto(json.dumps(message).encode(), ADDR)
    except OSError:
        pass


def face_recognizer():
    if not hasattr(cv2, "face"):
        raise SystemExit("חסר opencv-contrib-python; הפעל את CLAUDE.bat להתקנה.")
    return cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)


def face_cascade():
    """OpenCV on Windows cannot open its XML from a path containing Hebrew."""
    source = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    target = Path(tempfile.gettempdir()) / "golem-haarcascade-frontalface.xml"
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        target.write_bytes(source.read_bytes())
    cascade = cv2.CascadeClassifier(str(target))
    if cascade.empty():
        raise SystemExit("קובץ זיהוי הפנים של OpenCV לא נטען.")
    return cascade


def normalized_face(gray, rect):
    x, y, w, h = (int(v) for v in rect)
    px, py = int(w * 0.12), int(h * 0.12)
    crop = gray[max(0, y-py):min(gray.shape[0], y+h+py),
                max(0, x-px):min(gray.shape[1], x+w+px)]
    crop = cv2.resize(crop, (160, 160), interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(crop)


def enroll(camera, name, profile):
    recognizer = face_recognizer()
    cascade = face_cascade()
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"המצלמה {camera} לא נפתחה.")

    samples, last_sample = [], 0.0
    deadline = time.time() + 60
    print("שב לבד מול המצלמה והזז מעט את הראש. ESC מבטל.", flush=True)
    try:
        while len(samples) < 48 and time.time() < deadline:
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(80, 80))
            if len(faces) == 1 and time.time() - last_sample >= 0.12:
                samples.append(normalized_face(gray, faces[0]))
                last_sample = time.time()
            for x, y, w, h in faces:
                color = (0, 220, 0) if len(faces) == 1 else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.putText(frame, f"Owner enrollment: {len(samples)}/48", (20, 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 220, 255), 2)
            cv2.putText(frame, "Look left / right / up / down slowly", (20, 72),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            cv2.imshow("GOLEM - owner enrollment", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if len(samples) < 24:
        raise SystemExit("ההרשמה לא הושלמה: נדרשו לפחות 24 תמונות פנים ברורות.")

    holdout = samples[::4]
    training = [sample for i, sample in enumerate(samples) if i % 4]
    recognizer.train(training, np.zeros(len(training), dtype=np.int32))
    scores = [recognizer.predict(sample)[1] for sample in holdout]
    threshold = float(max(42, min(68, np.percentile(scores, 95) + 14)))
    recognizer.update(holdout, np.zeros(len(holdout), dtype=np.int32))

    profile.parent.mkdir(parents=True, exist_ok=True)
    recognizer.write(str(profile))
    meta = {
        "name": name,
        "threshold": round(threshold, 2),
        "samples": len(samples),
        "enrolled_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "storage": "local LBPH template; enrollment frames were not saved",
    }
    profile.with_name("owner.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ההרשמה הושלמה: {name} · סף {threshold:.1f}", flush=True)


def load_owner(profile):
    meta_path = profile.with_name("owner.json")
    if not profile.exists() or not meta_path.exists():
        return None, {"name": "עופר", "threshold": 55.0}
    recognizer = face_recognizer()
    recognizer.read(str(profile))
    return recognizer, json.loads(meta_path.read_text(encoding="utf-8"))


def native_say(text):
    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=[System.Speech.Synthesis.SpeechSynthesizer]::new();"
        "try{$s.SelectVoice('Microsoft Asaf')}catch{};"
        f"$s.Speak('{safe}');$s.Dispose()"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def analyze_scene(jpg, model, identity_hint):
    prompt = (
        "תאר במשפט אחד קצר בעברית מה נראה כרגע במצלמה: מספר אנשים, פעולה וחפצים "
        "בולטים. אל תנחש זהויות, רגשות או תכונות רגישות. " + identity_hint
    )
    payload = json.dumps({
        "model": model, "stream": False, "think": False,
        "messages": [{"role": "user", "content": prompt,
                      "images": [base64.b64encode(jpg).decode("ascii")]}],
        "options": {"temperature": 0.2, "num_predict": 100},
    }).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        text = json.loads(response.read()).get("message", {}).get("content", "")
    return " ".join(text.strip().split())


def self_test():
    recognizer = face_recognizer()
    base = np.tile(np.arange(160, dtype=np.uint8), (160, 1))
    samples = [base, np.roll(base, 2, axis=1), np.roll(base, -2, axis=1)]
    recognizer.train(samples, np.zeros(3, dtype=np.int32))
    label, confidence = recognizer.predict(base)
    assert label == 0 and np.isfinite(confidence)
    assert normalized_face(np.zeros((240, 320), np.uint8), (80, 40, 120, 140)).shape == (160, 160)
    print("vision self-test: ok")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam", type=int, default=0)
    parser.add_argument("--fps", type=float, default=10)
    parser.add_argument("--flip", action="store_true")
    parser.add_argument("--greet", type=float, default=20)
    parser.add_argument("--show", action="store_true", help="לשמור eyes_debug.jpg")
    parser.add_argument("--window", action="store_true")
    parser.add_argument("--speak", action="store_true")
    parser.add_argument("--enroll", metavar="NAME")
    parser.add_argument("--profile", default=str(PROFILE))
    parser.add_argument("--vision-model", default="qwen3.5:9b")
    parser.add_argument("--analyze-seconds", type=float, default=10)
    parser.add_argument("--no-analyze", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    profile = Path(args.profile)
    if args.enroll:
        enroll(args.cam, args.enroll, profile)
        return

    recognizer, owner = load_owner(profile)
    owner_name = owner.get("name", "עופר")
    threshold = float(owner.get("threshold", 55.0))
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"המצלמה {args.cam} לא נפתחה.")
    cascade = face_cascade()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    state_lock = threading.Lock()
    state = {
        "timestamp": None, "camera": args.cam, "people": 0, "identity": "none",
        "owner_name": owner_name, "owner_present": False, "unknown_people": 0,
        "confidence": None, "scene": "המצלמה התחילה לפעול.",
    }

    def update_state(**changes):
        with state_lock:
            state.update(changes)
            state["timestamp"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
            temp = STATE_FILE.with_suffix(".json.tmp")
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, STATE_FILE)

    jobs = queue.Queue(maxsize=1)
    stop = threading.Event()

    def vision_worker():
        while not stop.is_set():
            try:
                jpg, hint = jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                scene = analyze_scene(jpg, args.vision_model, hint)
                if scene:
                    update_state(scene=scene)
                    print("רואה:", scene, flush=True)
            except Exception as error:
                print("ניתוח התמונה לא זמין:", error, flush=True)

    if not args.no_analyze:
        threading.Thread(target=vision_worker, daemon=True).start()

    gx = gy = 0.0
    period = 1.0 / max(1.0, args.fps)
    history = collections.deque(maxlen=5)
    stable_identity = "none"
    last_face = 0.0
    last_greet = 0.0
    last_debug = 0.0
    next_analysis = 0.0
    speaker = None
    started = time.monotonic()
    print(f"העיניים פקוחות · מצלמה {args.cam} · בעלים: {owner_name if recognizer else 'לא נרשם'}", flush=True)

    try:
        while True:
            tick = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.2)
                continue
            h, w = frame.shape[:2]
            gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(70, 70))

            known = 0
            scores = []
            labels = []
            for rect in faces:
                if recognizer:
                    _, confidence = recognizer.predict(normalized_face(gray, rect))
                    is_owner = confidence <= threshold
                    scores.append(float(confidence))
                else:
                    confidence, is_owner = None, False
                known += int(is_owner)
                labels.append((owner_name if is_owner else "guest", confidence))

            unknown = len(faces) - known
            raw_identity = "owner" if known else ("guest" if len(faces) else "none")
            history.append(raw_identity)
            if len(history) == history.maxlen and len(set(history)) == 1:
                new_stable = history[-1]
                if new_stable != stable_identity:
                    away_long_enough = tick - last_face >= args.greet
                    stable_identity = new_stable
                    if stable_identity in ("owner", "guest") and (away_long_enough or tick-last_greet > 8):
                        if stable_identity == "owner":
                            phrase = f"שלום {owner_name}, טוב לראות אותך."
                        else:
                            phrase = "שלום, נעים להכיר. אני קלוד."
                        send(udp, mode="critter", expr="happy", state="listen", emote="wake")
                        print("זיהוי:", owner_name if stable_identity == "owner" else "אורח", flush=True)
                        if args.speak and (speaker is None or speaker.poll() is not None):
                            speaker = native_say(phrase)
                        last_greet = tick

            if len(faces):
                x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                tx = ((x + fw/2) / w) * 2 - 1
                ty = ((y + fh/2) / h) * 2 - 1
                if args.flip:
                    tx = -tx
                gx += (tx-gx) * 0.35
                gy += (ty-gy) * 0.35
                send(udp, gaze=[round(gx, 3), round(gy, 3)], passive=True)
                last_face = tick
            else:
                gx += -gx * 0.06
                gy += -gy * 0.06
                if abs(gx) > 0.02 or abs(gy) > 0.02:
                    send(udp, gaze=[round(gx, 3), round(gy, 3)], passive=True)

            update_state(
                people=len(faces), identity=raw_identity, owner_present=bool(known),
                unknown_people=unknown, confidence=round(min(scores), 2) if scores else None)

            if not args.no_analyze and tick >= next_analysis and jobs.empty():
                small = frame if w <= 960 else cv2.resize(
                    frame, (960, int(h * 960 / w)), interpolation=cv2.INTER_AREA)
                encoded_ok, jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if encoded_ok:
                    if raw_identity == "owner":
                        hint = f"זיהוי מקומי קבע שהבעלים {owner_name} נמצא מול המצלמה."
                    elif raw_identity == "guest":
                        hint = "זיהוי מקומי קבע שהאדם אינו הבעלים; קרא לו אורח."
                    else:
                        hint = "לא זוהה אדם כרגע."
                    jobs.put_nowait((jpg.tobytes(), hint))
                next_analysis = tick + max(3.0, args.analyze_seconds)

            if args.show or args.window:
                for (x, y, fw, fh), (label, confidence) in zip(faces, labels):
                    color = (0, 210, 0) if label == owner_name else (0, 180, 255)
                    cv2.rectangle(frame, (x, y), (x+fw, y+fh), color, 2)
                    caption = label if confidence is None else f"{label} {confidence:.1f}"
                    cv2.putText(frame, caption, (x, max(20, y-8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
                if args.show and tick-last_debug >= 1:
                    cv2.imwrite(str(DEBUG_FILE), frame)
                    last_debug = tick
                if args.window:
                    cv2.imshow("GOLEM vision", frame)
                    if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                        break

            if args.seconds and time.monotonic()-started >= args.seconds:
                break
            delay = period - (time.monotonic()-tick)
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        cap.release()
        udp.close()
        if args.window:
            cv2.destroyAllWindows()
        print("העיניים נעצמו.", flush=True)


if __name__ == "__main__":
    main()
