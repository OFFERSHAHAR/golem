"""talk.py - קונסולת אינטראקציה עם גולם. הרץ במקביל ל-golem_live.py.

    טקסט חופשי               -> הוא מדבר אותו
    /happy /wink /cool /closed /surprised /sad /neutral   -> הבעה
    /chef /wizard /cowboy /cape /nohat                    -> כובע
    /critter /spark /face                                 -> החלפת דמות
    /listen /think /idle /error                           -> מצב
    /gaze 0.4 -0.2   /look   /pulse                       -> מבט ומחוות
    /q                                                    -> יציאה
"""
import json, math, random, socket, time

ADDR = ("127.0.0.1", 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
EXPRS = {"happy", "wink", "cool", "closed", "surprised", "sad", "neutral"}
HATS = {"chef", "wizard", "cowboy", "cape"}
MODES = {"critter", "spark", "face"}
STATES = {"listen", "think", "idle", "speak", "error"}


def send(**kw):
    sock.sendto(json.dumps(kw).encode(), ADDR)


def speak(text):
    dur = max(1.0, min(len(text) * 0.075, 12.0))
    t0 = time.time()
    while time.time() - t0 < dur:
        t = time.time() - t0
        env = abs(math.sin(t / 0.14)) ** 0.6
        env *= 0.55 + 0.45 * math.sin(t * 0.9)
        send(state="speak", amp=round(min(1.0, env * random.uniform(.8, 1.15)), 3))
        time.sleep(0.05)
    send(state="idle", amp=0)


print(__doc__)
send(state="idle")
while True:
    try:
        line = input("קלוד> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not line:
        continue
    if line == "/q":
        break
    if line.startswith("/gaze"):
        p = line.split()
        send(state="listen", gaze=[float(p[1]), float(p[2])] if len(p) > 2 else [0, 0])
        continue
    if line == "/look":
        for i in range(24):
            send(gaze=[math.sin(i / 3.5), math.cos(i / 5.0) * .5])
            time.sleep(0.08)
        send(gaze=[0, 0])
        continue
    if line.startswith("/"):
        w = line[1:].strip()
        if w in EXPRS:
            send(expr=w)
        elif w in HATS:
            send(hat=w)
        elif w == "nohat":
            send(hat="none")
        elif w in MODES:
            send(mode=w)
        elif w in STATES:
            send(state=w)
        elif w == "pulse":
            send(emote="pulse")
        else:
            print("לא מכיר את הפקודה הזאת")
        continue
    speak(line)

send(state="idle", amp=0)
print("להתראות.")
