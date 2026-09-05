"""golem_brain.py - האוזניים, המוח והקול. רץ במקביל ל-golem_live.py.

    python golem_brain.py                 # מודל תמלול small על CPU
    python golem_brain.py --model medium  # תמלול טוב יותר, איטי יותר
    python golem_brain.py --open          # בלי מילת הפעלה, מגיב לכל דבר

קורא לו: "קלוד" (או קלאוד / claude). אחרי שהוא ער, אפשר להמשיך לדבר 30 שניות
בלי לחזור על השם.
"""
import argparse, json, re, socket, sys, time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from senses.ears import Ears
from senses.brain import Brain
from senses import voice

ADDR = ("127.0.0.1", 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

WAKE = re.compile(r"(קל[ואי]*ד|קלאוד|כלוד|claude|klaud)", re.I)
BYE = re.compile(r"(ביי|להתראות|לילה טוב|תישן|די קלוד)", re.I)


CHAT_LOG = "chat.log"


def send(**kw):
    try:
        sock.sendto(json.dumps(kw).encode(), ADDR)
    except Exception:
        pass


def log(who, what):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {who}: {what}"
    print(line, flush=True)
    try:
        with open(CHAT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def strip_wake(t):
    return WAKE.sub("", t).strip(" ,.!?־-")


# פקודות תחפושת בקול — נענות מיד, בלי לעבור דרך המודל
COSTUMES = [
    (r"(קוסם|מכשף|הארי פוטר)",            {"hat": "wizard", "expr": "happy"}, "אברקדברה"),
    (r"(שף|טבח|מבשל)",                    {"hat": "chef"},                   "מה מבשלים"),
    (r"(בוקר|קאובוי|מערבון)",             {"hat": "cowboy"},                 "יאללה"),
    (r"(גלימה|גיבור|סופרמן|על)",          {"hat": "cape", "expr": "happy"},  "אני מציל את היום"),
    (r"(חליפה|עניבה|מנהל|עסקים)",         {"hat": "suit", "expr": "cool"},   "בוא נדבר עסקים"),
    (r"(כתר|מלך|מלכה)",                   {"hat": "crown"},                  "כבודו"),
    (r"(אוזניות|מוזיקה|די ג)",            {"hat": "headphones"},             "שים מוזיקה"),
    (r"(מסיבה|יום הולדת|חוגג)",           {"hat": "party", "expr": "happy"}, "מסיבה"),
    (r"(מדען|משקפי מגן|מעבדה|נאס)",       {"hat": "goggles"},                "לניסוי"),
    (r"(תוריד את הכובע|בלי כובע|תתפשט|רגיל)", {"hat": "none", "expr": "neutral"}, "בסדר"),
    (r"(משקפי שמש|מגניב|קול\b)",          {"expr": "cool"},                  "מגניב"),
    (r"(תחייך|חייך|שמח)",                 {"expr": "happy"},                 None),
    (r"(תקרוץ|קריצה)",                    {"expr": "wink"},                  None),
    (r"(תעצום|עיניים עצומות|תנוח)",       {"expr": "closed"},                None),
    (r"(עצוב|תתעצבן)",                    {"expr": "sad"},                   None),
    (r"(מופתע|וואו)",                     {"expr": "surprised"},             None),
    (r"(תהיה ניצוץ|תחזור לניצוץ|ניצוץ)",  {"mode": "spark"},                 None),
    (r"(פרצוף|עיניים ופה)",               {"mode": "face"},                  None),
    (r"(תחזור להיות אתה|תהיה קלוד|היצור)", {"mode": "critter"},              None),
]
COSTUMES = [(re.compile(p), kw, say) for p, kw, say in COSTUMES]


def try_costume(text):
    """אם זו בקשת תחפושת — מבצע ומחזיר True."""
    for pat, kw, phrase in COSTUMES:
        if pat.search(text):
            send(**kw)
            log("קלוד", f"[{', '.join(f'{k}={v}' for k, v in kw.items())}]")
            return phrase or True
    return None


ap = argparse.ArgumentParser()
ap.add_argument("--model", default="large-v3")
ap.add_argument("--device", default="cuda")
ap.add_argument("--compute", default="float16")
ap.add_argument("--window", type=float, default=30.0)
ap.add_argument("--open", action="store_true", help="בלי מילת הפעלה")
ap.add_argument("--voice", default=voice.VOICE)
ap.add_argument("--mic", default=None, help="אינדקס או חלק משם המיקרופון")
ap.add_argument("--silence", type=float, default=1.45,
                help="כמה שקט צריך כדי להחליט שסיימת משפט")
a = ap.parse_args()

mic = a.mic
if mic is not None and mic.lstrip("-").isdigit():
    mic = int(mic)
ears = Ears(model=a.model, device=a.device, compute_type=a.compute, mic=mic,
            silence=a.silence)
brain = Brain()
awake_until = 0.0

print('קלוד מקשיב. תקרא לו בשם.', flush=True)
send(state="idle")


def answer(text):
    send(state="think", expr="neutral")
    reply = brain.ask(text)
    log("קלוד", reply)
    ears.muted = True
    send(state="speak", expr="neutral")
    voice.say(reply, on_amp=lambda v: send(state="speak", amp=round(float(v), 3)),
              voice=a.voice)
    send(state="listen", amp=0)
    time.sleep(0.35)
    ears.muted = False


for text in ears.listen():
    now = time.time()
    log("עופר", text)
    heard_wake = bool(WAKE.search(text))
    awake = a.open or now < awake_until or heard_wake

    if not awake:
        continue
    if BYE.search(text):
        send(state="idle", expr="closed", amp=0)
        awake_until = 0
        ears.muted = True
        voice.say("לילה טוב.", on_amp=lambda v: send(state="speak", amp=round(float(v), 3)))
        ears.muted = False
        send(state="idle", amp=0)
        continue

    body = strip_wake(text) if heard_wake else text
    awake_until = now + a.window

    if heard_wake and len(body) < 2:
        send(mode="critter", expr="happy", state="listen")
        ears.muted = True
        voice.say("כן?", on_amp=lambda v: send(state="speak", amp=round(float(v), 3)))
        ears.muted = False
        send(state="listen", amp=0)
        continue

    costume = try_costume(body)
    if costume:
        if isinstance(costume, str):
            ears.muted = True
            voice.say(costume, on_amp=lambda v: send(state="speak", amp=round(float(v), 3)))
            ears.muted = False
        send(state="listen", amp=0)
        awake_until = time.time() + a.window
        continue

    send(mode="critter", expr="neutral", state="listen")
    answer(body)
    awake_until = time.time() + a.window
