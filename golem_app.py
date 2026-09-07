"""golem_app.py - הממשק המקומי של גולם.

שרת אחד שמגיש את הדף ומתרגם אותו לפקודות UDP למנוע הקיר.
    python golem_app.py                     על 8765
    python golem_app.py --open              ופותח דפדפן
    python golem_app.py --selftest          בדיקה עצמית
"""
import argparse, base64, hmac, json, os, random, secrets, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import wall_map as WM

PASSWORD = os.environ.get("GOLEM_PASSWORD", "1892346")
ENGINE = ("127.0.0.1", 9999)
SESSIONS = set()
LOGIN_FAILS = []                   # חותמות זמן של ניסיונות כושלים
MAX_BODY = 80_000_000              # תקרת גוף בקשה (וידאו קצר מותר)
STATE = {"panels": {}, "focus": WM.PANELS[0]["name"], "brightness": 38,
         "presence": False, "level": 0.0, "updated": 0, "desktop": False}
LIVE_PORTS = ("J1", "J2")          # היציאות המחוברות בפועל
MEDIA = ROOT / "media"             # מדיה שהועלתה מהממשק
PERSONAS = json.loads((ROOT / "personas.json").read_text(encoding="utf-8"))
# אישיות לכל פאנל. כל דמות עם אופי וזיכרון משלה.
PERSONA_OF = {"J1.1": "claude", "J1.2": "sharp", "J2.1": "nudge", "J2.2": "lazy"}

CHARACTERS = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
# כובעים והבעות שהיצור (critter) יודע ללבוש — מתוך face/critter.py
HATS = {"none": "בלי", "chef": "🧑‍🍳 שף", "wizard": "🧙 קוסם", "cowboy": "🤠 בוקר",
        "cape": "🦸 גלימה", "suit": "🕴️ חליפה", "crown": "👑 כתר",
        "headphones": "🎧 אוזניות", "party": "🎉 מסיבה", "goggles": "🥽 משקפי מגן"}
EXPRS = {"neutral": "רגיל", "happy": "😄 שמח", "wink": "😉 קריצה", "closed": "😌 עצום",
         "cool": "😎 מגניב", "surprised": "😲 מופתע", "sad": "🙁 עצוב"}


def udp(msg):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(json.dumps(msg).encode(), ENGINE)


def live_panels():
    return [p for p in WM.PANELS if p["port"] in LIVE_PORTS]


SPEAKING = threading.Lock()        # ponytail: רמקול אחד, דובר אחד בכל רגע


def speak_from(panel, text):
    """מדבר בקול, ופותח את הפה של הפאנל שנבחר. אם קלוד על שולחן העבודה,
    הפה שלו שם זז יחד איתו."""
    from senses import voice

    def mouth(amp):
        udp({"state": "speak", "amp": float(amp)})
        if STATE.get("desktop"):
            desk({"state": "speak", "amp": float(amp)})

    with SPEAKING:
        udp({"goto": panel})
        udp({"panel": panel, "panel_mode": "face"})
        try:
            voice.say(text, on_amp=mouth)
        except Exception as exc:
            print("קול נכשל:", exc, flush=True)
        udp({"state": "idle", "amp": 0.0})
        if STATE.get("desktop"):
            desk({"state": "idle", "amp": 0.0})


PARTY = {"running": False}
DESKTOP_ADDR = ("127.0.0.1", 9998)
DESKTOP_PROC = {"handle": None}


def desk(msg):
    """פקודה לקלוד שעל שולחן העבודה."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(json.dumps(msg).encode(), DESKTOP_ADDR)


def desktop_running():
    proc = DESKTOP_PROC["handle"]
    return proc is not None and proc.poll() is None


def start_desktop():
    """מרים את חלון שולחן העבודה. אותו מפרש פייתון, כדי שיעבוד גם מ-USB."""
    import subprocess
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    DESKTOP_PROC["handle"] = subprocess.Popen(
        [str(pyw if pyw.exists() else exe), str(ROOT / "desktop_claude.py")],
        cwd=str(ROOT))
    time.sleep(1.5)                       # להספיק לתפוס את הפורט לפני הפקודה
    return DESKTOP_PROC["handle"]


def party_lights(step):
    """אורות מסיבה: הבזקי צבע על כל הקיר, גוון מתחלף."""
    for i in range(10):
        udp({"paint": [random.random(), random.random(), 0.9,
                       (step * 40 + i * 36) % 360]})


def run_party(seed=None):
    """סבב מסיבה מלא: כל דמות מדברת מהפאנל שלה, עם אורות ופוסטים."""
    from senses import minds, social
    PARTY["running"] = True
    try:
        panels = [(p["name"], PERSONA_OF.get(p["name"], "claude"))
                  for p in live_panels()]
        step = 0

        def speak(panel, text):
            nonlocal step
            step += 1
            party_lights(step)
            speak_from(panel, text)

        social.party_round(panels, minds.ask, speak, seed)
    except Exception as exc:
        print("מסיבה נכשלה:", exc, flush=True)
    finally:
        udp({"paint_clear": True})
        PARTY["running"] = False


def ask_brain(panel, text):
    """שואל את הדמות של הפאנל, עם האישיות והזיכרון הפרטי שלה."""
    try:
        from senses import minds
        reply, source = minds.ask(panel, text, PERSONA_OF.get(panel, "claude"))
        print(f"[{source}] {panel}: {reply}", flush=True)
        return reply
    except Exception as exc:
        print("מוח לא זמין:", exc, flush=True)
        return "אין לי מוח זמין כרגע."


def html_page():
    panels = json.dumps([{"name": p["name"], "port": p["port"], "chain": p["chain"],
                          "persona": PERSONA_OF.get(p["name"], "claude")}
                         for p in live_panels()], ensure_ascii=False)
    chars = json.dumps(CHARACTERS, ensure_ascii=False)
    people = json.dumps(PERSONAS, ensure_ascii=False)
    return (TEMPLATE.replace("__PANELS__", panels)
                    .replace("__CHARACTERS__", chars)
                    .replace("__PERSONAS__", people)
                    .replace("__HATS__", json.dumps(HATS, ensure_ascii=False))
                    .replace("__EXPRS__", json.dumps(EXPRS, ensure_ascii=False)))


class Handler(BaseHTTPRequestHandler):
    server_version = "golem"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", cookie=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", f"golem={cookie}; Path=/; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(data)

    def _authed(self):
        for part in self.headers.get("Cookie", "").split(";"):
            part = part.strip()
            if part.startswith("golem="):
                return part[6:] in SESSIONS
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, html_page().encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/state":
            if not self._authed():
                return self._send(401, {"error": "auth"})
            return self._send(200, {"state": STATE, "characters": CHARACTERS,
                                    "panels": [p["name"] for p in live_panels()]})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._send(413, {"error": "בקשה גדולה מדי"})
        # חוסם בקשות ממקור אחר בדפדפן, גם אם הגיעו עם עוגייה
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            return self._send(403, {"error": "origin חסום"})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad json"})

        if path == "/api/login":
            now = time.time()
            LOGIN_FAILS[:] = [t for t in LOGIN_FAILS if now - t < 300]
            if len(LOGIN_FAILS) >= 8:         # נעילה אחרי 8 כשלונות ב-5 דקות
                return self._send(429, {"error": "יותר מדי ניסיונות. נסה בעוד כמה דקות."})
            if hmac.compare_digest(str(body.get("password", "")), PASSWORD):
                token = secrets.token_urlsafe(24)
                SESSIONS.add(token)
                LOGIN_FAILS.clear()
                return self._send(200, {"ok": True}, cookie=token)
            LOGIN_FAILS.append(now)
            time.sleep(0.6)                   # ponytail: השהיה פשוטה נגד ניחוש סיסמה
            return self._send(401, {"error": "קוד שגוי"})

        if not self._authed():
            return self._send(401, {"error": "auth"})

        if path == "/api/panel":
            name, mode = body.get("panel"), body.get("mode")
            if name not in WM.PANEL_INDEX or mode not in CHARACTERS:
                return self._send(400, {"error": "bad panel or mode"})
            udp({"panel": name, "panel_mode": CHARACTERS[mode]["engine"]})
            STATE["panels"][name] = mode
            STATE["updated"] = time.time()
            return self._send(200, {"ok": True})

        if path == "/api/dress":
            # כובע והבעה לפאנל — עובד רק על היצור (critter)
            name = body.get("panel")
            hat, expr = body.get("hat"), body.get("expr")
            if name not in WM.PANEL_INDEX:
                return self._send(400, {"error": "bad panel"})
            if hat and hat not in HATS:
                return self._send(400, {"error": "bad hat"})
            if expr and expr not in EXPRS:
                return self._send(400, {"error": "bad expr"})
            msg = {"panel": name}
            if hat:
                msg["panel_hat"] = hat
            if expr:
                msg["panel_expr"] = expr
            udp(msg)
            return self._send(200, {"ok": True})

        if path == "/api/focus":
            name = body.get("panel")
            if name not in WM.PANEL_INDEX:
                return self._send(400, {"error": "bad panel"})
            udp({"goto": name})
            STATE["focus"] = name
            return self._send(200, {"ok": True})

        if path == "/api/sense":
            level = max(0.0, min(1.0, float(body.get("level", 0))))
            gaze = body.get("gaze") or [0, 0]
            present = bool(body.get("present"))
            STATE.update(presence=present, level=level, updated=time.time())
            udp({"state": "speak" if level > 0.12 else ("listen" if present else "idle"),
                 "amp": level, "gaze": [float(gaze[0]), float(gaze[1])]})
            return self._send(200, {"ok": True})

        if path == "/api/brightness":
            STATE["brightness"] = max(5, min(100, int(body.get("value", 38))))
            udp({"brightness": STATE["brightness"]})
            return self._send(200, {"ok": True})

        if path == "/api/say":
            # מדבר מפאנל מסוים: הפה נפתח שם, לא על כל הקיר
            name = body.get("panel")
            text = str(body.get("text", "")).strip()
            if name not in WM.PANEL_INDEX or not text:
                return self._send(400, {"error": "bad panel or empty text"})
            threading.Thread(target=speak_from, args=(name, text[:400]),
                             daemon=True).start()
            return self._send(200, {"ok": True})

        if path == "/api/media":
            # מדיה מקומית לפאנל: תמונה או GIF, נשמרת ומותאמת ל-64x64 במנוע
            name = body.get("panel")
            data_url = str(body.get("data", ""))
            if name not in WM.PANEL_INDEX or "," not in data_url:
                return self._send(400, {"error": "bad panel or data"})
            head, b64 = data_url.split(",", 1)
            if "gif" in head: ext = ".gif"
            elif "mp4" in head or "video/mp4" in head: ext = ".mp4"
            elif "webm" in head: ext = ".webm"
            elif "quicktime" in head or "mov" in head: ext = ".mov"
            elif "png" in head: ext = ".png"
            else: ext = ".jpg"
            try:
                raw = base64.b64decode(b64, validate=True)
            except Exception:
                return self._send(400, {"error": "bad base64"})
            if len(raw) > 60_000_000:
                return self._send(413, {"error": "הקובץ גדול מדי — נסה וידאו קצר יותר"})
            MEDIA.mkdir(exist_ok=True)
            dest = MEDIA / f"{name.replace('.', '_')}{ext}"
            dest.write_bytes(raw)
            udp({"panel": name, "panel_image": str(dest)})
            STATE["panels"][name] = "media"
            return self._send(200, {"ok": True, "file": dest.name})

        if path == "/api/ask":
            # שאלה למוח המקומי, והתשובה נאמרת מהפאנל שנבחר
            name = body.get("panel")
            text = str(body.get("text", "")).strip()
            if name not in WM.PANEL_INDEX or not text:
                return self._send(400, {"error": "bad panel or empty text"})
            reply = ask_brain(name, text)
            threading.Thread(target=speak_from, args=(name, reply),
                             daemon=True).start()
            return self._send(200, {"ok": True, "reply": reply})

        if path == "/api/desktop":
            # קלוד עובר בין הקיר לשולחן העבודה
            action = body.get("action")
            if action == "out":
                if not desktop_running():
                    start_desktop()
                udp({"panel": STATE["focus"], "panel_mode": "off"})
                desk({"show": True, "mode": body.get("mode", "critter"),
                      "size": int(body.get("size", 160))})
                STATE["desktop"] = True
            elif action == "back":
                desk({"hide": True})
                udp({"panel": STATE["focus"], "panel_mode": "clear"})
                udp({"goto": STATE["focus"]})
                STATE["desktop"] = False
            elif action == "size":
                desk({"size": int(body.get("size", 160))})
            else:
                return self._send(400, {"error": "bad action"})
            return self._send(200, {"ok": True, "desktop": STATE["desktop"]})

        if path == "/api/party":
            if PARTY["running"]:
                return self._send(409, {"error": "המסיבה כבר רצה"})
            threading.Thread(target=run_party, args=(body.get("seed"),),
                             daemon=True).start()
            return self._send(200, {"ok": True})

        if path == "/api/feed":
            from senses import social
            if body.get("clear"):
                return self._send(200, {"ok": True, "cleared": social.clear()})
            if body.get("write"):
                name = body.get("panel")
                if name not in WM.PANEL_INDEX:
                    return self._send(400, {"error": "bad panel"})
                from senses import minds
                post = social.write_post(name, PERSONA_OF.get(name, "claude"),
                                         minds.ask, body.get("topic"))
                return self._send(200, {"ok": True, "post": post})
            return self._send(200, {"ok": True, "posts": social.feed(40),
                                    "personas": PERSONAS,
                                    "party": PARTY["running"]})

        if path == "/api/hear":
            # אודיו מהדפדפן -> תמלול מקומי -> הדמות של הפאנל עונה בקול
            name = body.get("panel") or STATE["focus"]
            data_url = str(body.get("data", ""))
            if name not in WM.PANEL_INDEX or "," not in data_url:
                return self._send(400, {"error": "bad panel or audio"})
            try:
                raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
            except Exception:
                return self._send(400, {"error": "bad base64"})
            MEDIA.mkdir(exist_ok=True)
            clip = MEDIA / "heard.webm"
            clip.write_bytes(raw)
            try:
                from senses import hearing
                heard = hearing.transcribe(clip)
            except Exception as exc:
                print("תמלול נכשל:", exc, flush=True)
                return self._send(200, {"ok": False, "heard": "", "error": str(exc)})
            if not heard:
                return self._send(200, {"ok": True, "heard": ""})
            reply = ask_brain(name, heard)
            threading.Thread(target=speak_from, args=(name, reply), daemon=True).start()
            return self._send(200, {"ok": True, "heard": heard, "reply": reply})

        if path == "/api/paint":
            # מכחול הקסם: המצלמה שולחת נקודות, הקיר מצייר אותן
            if body.get("clear"):
                udp({"paint_clear": True})
                return self._send(200, {"ok": True})
            dabs = body.get("dabs") or []
            for dab in dabs[:12]:
                udp({"paint": dab})
            return self._send(200, {"ok": True, "dabs": len(dabs[:12])})

        if path == "/api/persona":
            name, who = body.get("panel"), body.get("persona")
            if name not in WM.PANEL_INDEX or who not in PERSONAS:
                return self._send(400, {"error": "bad panel or persona"})
            PERSONA_OF[name] = who
            return self._send(200, {"ok": True, "persona": PERSONAS[who]["name"]})

        if path == "/api/forget":
            # איפוס זיכרון: פאנל אחד, או הכול לפני מסירה במתנה
            from senses import minds
            name = body.get("panel")
            count = minds.forget(name if name in WM.PANEL_INDEX else None)
            return self._send(200, {"ok": True, "cleared": count})

        return self._send(404, {"error": "not found"})


TEMPLATE = r"""<!doctype html>
<html lang="he" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GOLEM</title>
<style>
:root{color-scheme:dark;--bg:#0a0a0c;--card:#141419;--line:#26262f;--ink:#eceae6;
      --dim:#8b8b98;--brand:#e8703a;--ok:#4cc38a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font-family:system-ui,"Segoe UI",Arial,sans-serif;font-weight:300}
.wrap{max-width:960px;margin:0 auto;padding:22px 16px 60px}
h1{font-size:1.4rem;margin:0 0 4px}.sub{color:var(--dim);font-size:.9rem;margin:0 0 22px}
.gate{max-width:340px;margin:16vh auto;text-align:center}
input,button{font:inherit}
input[type=password]{width:100%;min-height:48px;border:1px solid var(--line);
  border-radius:10px;background:#101014;color:var(--ink);padding:0 14px;text-align:center;
  letter-spacing:.3em}
.btn{min-height:48px;border:0;border-radius:10px;background:var(--brand);color:#12100f;
  font-weight:800;cursor:pointer;padding:0 18px;width:100%;margin-top:10px}
.err{color:#ff8f6b;font-size:.86rem;min-height:1.2em;margin-top:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.panel h3{margin:0 0 2px;font-size:1rem}
.tag{color:var(--dim);font-size:.76rem;font-family:ui-monospace,monospace}
.chars{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.chip{border:1px solid var(--line);background:#1b1b22;color:var(--ink);border-radius:9px;
  padding:8px 10px;cursor:pointer;font-size:.85rem;min-height:42px}
.chip[aria-pressed=true]{border-color:var(--brand);background:#241812;color:#ffc0a3;font-weight:700}
.row{display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap}
.send{flex:1;min-height:42px;border:1px solid var(--line);background:#1b1b22;color:var(--ink);
  border-radius:9px;cursor:pointer}
.send.on{border-color:var(--ok);color:var(--ok)}
.talk{width:100%;min-height:42px;border:1px solid var(--line);border-radius:9px;
  background:#101014;color:var(--ink);padding:0 12px;text-align:right}
.say,.ask{flex:1;min-height:40px;border:1px solid var(--line);border-radius:9px;
  background:#1b1b22;color:var(--ink);cursor:pointer;font-size:.85rem}
.say{border-color:var(--brand);color:#ffc0a3}
.reply{color:var(--dim);font-size:.8rem;margin-top:6px;min-height:1.1em}
.media{flex:1;min-height:40px;display:flex;align-items:center;justify-content:center;
  border:1px dashed var(--line);border-radius:9px;cursor:pointer;font-size:.85rem;
  color:var(--dim)}
.media:hover{border-color:var(--brand);color:#ffc0a3}
.prow{margin-top:8px}
.hat,.expr{flex:1;min-height:40px;border:1px solid var(--line);border-radius:9px;
  background:#101014;color:var(--ink);padding:0 8px;font-size:.82rem}
.persona{width:100%;min-height:42px;border:1px solid var(--line);border-radius:9px;
  background:#101014;color:var(--ink);padding:0 10px;font-size:.85rem}
.forget{width:100%;min-height:38px;border:1px solid var(--line);border-radius:9px;
  background:#1b1b22;color:var(--dim);cursor:pointer;font-size:.8rem}
.forget:hover{border-color:#ff8f6b;color:#ff8f6b}
.crop{margin-top:10px;padding:10px;border:1px solid var(--line);border-radius:10px;
  background:#0e0e12}
.cropcv{width:100%;max-width:200px;display:block;margin:0 auto 8px;border-radius:6px;
  cursor:grab;touch-action:none;image-rendering:auto}
.croprow{display:flex;gap:8px;align-items:center;margin-top:6px}
.croprow label{font-size:.78rem}
.apply,.cancel{flex:1;min-height:38px;border:1px solid var(--line);border-radius:9px;
  background:#1b1b22;color:var(--ink);cursor:pointer;font-size:.82rem}
.apply{border-color:var(--brand);color:#ffc0a3}
#magicBtn[aria-pressed=true],#hearBtn[aria-pressed=true]{border-color:var(--brand);
  background:#241812;color:#ffc0a3}
#feed{display:grid;gap:8px;margin-top:12px}
.post{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.post.party{border-color:var(--brand)}
.post .who{display:flex;gap:8px;align-items:baseline;font-size:.9rem}
.post .meta{color:var(--dim);font-size:.74rem;font-family:ui-monospace,monospace}
.post .text{margin-top:6px;font-size:.92rem;line-height:1.5}
.empty{color:var(--dim);font-size:.85rem;padding:14px;text-align:center}
.bar{margin:0 0 12px;padding:14px;background:var(--card);border:1px solid var(--line);
  border-radius:14px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.dot{width:10px;height:10px;border-radius:50%;background:#444}.dot.live{background:var(--ok)}
.meter{flex:1;height:8px;background:#1b1b22;border-radius:99px;overflow:hidden;min-width:120px}
.meter i{display:block;height:100%;width:0;background:var(--brand)}
video{display:none}
label{font-size:.85rem;color:var(--dim)}
input[type=range]{accent-color:var(--brand);flex:1;min-width:140px}
:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
</style></head><body>

<div id="gate" class="gate">
  <h1>GOLEM</h1>
  <p class="sub">הזן קוד כניסה</p>
  <input id="pw" type="password" inputmode="numeric" autocomplete="off" aria-label="קוד כניסה">
  <button class="btn" id="go">כניסה</button>
  <div class="err" id="err"></div>
</div>

<div id="app" class="wrap" hidden>
  <h1>לוח הבקרה</h1>
  <p class="sub">בחר מי יושב על כל פאנל, ולאן קלוד הולך</p>

  <div class="bar">
    <span class="dot" id="dot"></span>
    <span id="senseLabel">חיישנים כבויים</span>
    <div class="meter"><i id="meter"></i></div>
    <button class="chip" id="senseBtn">הפעל מצלמה ומיקרופון</button>
    <button class="chip" id="magicBtn">✨ מצב קסם</button>
    <button class="chip" id="clearBtn">נקה</button>
    <button class="chip" id="hearBtn">🎤 הוא מקשיב</button>
  </div>
  <div class="bar">
    <button class="chip" id="outBtn">🖥️ צא לשולחן העבודה</button>
    <button class="chip" id="backBtn">↩️ חזור לקיר</button>
    <label for="dsize">גודל</label>
    <input id="dsize" type="range" min="64" max="512" value="160">
    <span id="dsizeVal">160</span>
  </div>
  <div class="bar"><span id="heardLabel">מה שנשמע יופיע כאן</span></div>

  <div class="bar">
    <label for="bright">בהירות</label>
    <input id="bright" type="range" min="5" max="100" value="38">
    <span id="brightVal">38%</span>
  </div>

  <div class="grid" id="grid"></div>

  <div class="bar" style="margin-top:22px">
    <button class="chip" id="partyBtn">🎉 PARTY MODE</button>
    <button class="chip" id="postBtn">✍️ שיכתבו פוסטים</button>
    <button class="chip" id="feedBtn">רענן</button>
    <button class="chip" id="wipeBtn">נקה רשת</button>
  </div>
  <div id="feed"></div>
</div>

<video id="cam" playsinline muted></video>
<script>
const PANELS = __PANELS__, CHARACTERS = __CHARACTERS__, PERSONAS = __PERSONAS__;
const HATS = __HATS__, EXPRS = __EXPRS__;
const $ = s => document.querySelector(s);
let sensing = false, magic = false, hue = 20;
let focusPanel = PANELS.length ? PANELS[0].name : null;   // מי עונה כשמדברים

async function api(path, body){
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                               body: JSON.stringify(body || {})});
  if(!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
  return r.json();
}

$('#go').onclick = async () => {
  try{
    await api('/api/login', {password: $('#pw').value});
    $('#gate').hidden = true; $('#app').hidden = false;
    build();
    loadFeed();
  }catch(e){ $('#err').textContent = e.message; }
};
$('#pw').addEventListener('keydown', e => { if(e.key === 'Enter') $('#go').click(); });

function build(){
  const grid = $('#grid');
  grid.innerHTML = '';
  PANELS.forEach((p, i) => {
    const el = document.createElement('div');
    el.className = 'panel';
    el.innerHTML = '<h3>פאנל ' + (i+1) + '</h3><div class="tag">' + p.name + '</div>' +
                   '<div class="chars"></div>' +
                   '<div class="row"><button class="send">שלח לכאן את קלוד</button></div>' +
                   '<div class="row"><input class="talk" type="text" placeholder="דבר מהפאנל הזה..."></div>' +
                   '<div class="row"><button class="say">אמור</button>' +
                   '<button class="ask">שאל את המוח</button></div>' +
                   '<div class="row"><select class="hat"></select><select class="expr"></select></div>' +
                   '<div class="row"><label class="media">🖼️ תמונה / וידאו' +
                   '<input type="file" accept="image/*,video/*" hidden></label></div>' +
                   '<div class="crop" hidden><canvas class="cropcv" width="128" height="128"></canvas>' +
                   '<div class="croprow"><label>גודל</label>' +
                   '<input class="zoom" type="range" min="100" max="400" value="100"></div>' +
                   '<div class="croprow"><button class="apply">שלח לפאנל</button>' +
                   '<button class="cancel">בטל</button></div></div>' +
                   '<div class="prow"><select class="persona"></select></div>' +
                   '<div class="prow"><button class="forget" title="מוחק את הזיכרון של הדמות הזאת">אפס זיכרון</button></div>' +
                   '<div class="reply"></div>';
    const chars = el.querySelector('.chars');
    Object.entries(CHARACTERS).forEach(([key, c]) => {
      const b = document.createElement('button');
      b.className = 'chip'; b.type = 'button';
      b.setAttribute('aria-pressed', 'false');
      b.textContent = c.emoji + ' ' + c.name;
      b.title = c.desc;
      b.onclick = async () => {
        await api('/api/panel', {panel: p.name, mode: key});
        chars.querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', 'false'));
        b.setAttribute('aria-pressed', 'true');
      };
      chars.appendChild(b);
    });
    const send = el.querySelector('.send');
    send.onclick = async () => {
      await api('/api/focus', {panel: p.name});
      document.querySelectorAll('.send').forEach(x => x.classList.remove('on'));
      send.classList.add('on');
      focusPanel = p.name;                 // מי שקלוד אצלו הוא גם מי שעונה
    };
    // כובע והבעה — נחשפים כל מה שהמנוע יודע ללבוש
    const hatSel = el.querySelector('.hat'), exprSel = el.querySelector('.expr');
    const optName = '— כובע —';
    Object.entries(HATS).forEach(([k, label]) => {
      const o = document.createElement('option'); o.value = k; o.textContent = label; hatSel.appendChild(o);
    });
    Object.entries(EXPRS).forEach(([k, label]) => {
      const o = document.createElement('option'); o.value = k; o.textContent = label; exprSel.appendChild(o);
    });
    hatSel.onchange = () => api('/api/dress', {panel: p.name, hat: hatSel.value});
    exprSel.onchange = () => api('/api/dress', {panel: p.name, expr: exprSel.value});

    const box = el.querySelector('.talk'), reply = el.querySelector('.reply');
    const run = async (route) => {
      const text = box.value.trim();
      if(!text) return;
      reply.textContent = '...';
      try{
        const r = await api(route, {panel: p.name, text});
        reply.textContent = r.reply || 'מדבר';
        box.value = '';
      }catch(e){ reply.textContent = 'שגיאה: ' + e.message; }
    };
    el.querySelector('.say').onclick = () => run('/api/say');
    el.querySelector('.ask').onclick = () => run('/api/ask');
    // עורך מדיה: גוררים כדי למקם, מחוון לגודל, ורואים בדיוק מה יוצג
    const crop = el.querySelector('.crop'), cropcv = el.querySelector('.cropcv');
    const zoom = el.querySelector('.zoom'), cg = cropcv.getContext('2d');
    let img = null, ox = 0, oy = 0, drag = null, raw = null;

    function paintCrop(){
      if(!img) return;
      cg.fillStyle = '#000'; cg.fillRect(0, 0, 128, 128);
      const scale = (+zoom.value / 100) * Math.max(128 / img.width, 128 / img.height);
      const w = img.width * scale, h = img.height * scale;
      cg.imageSmoothingEnabled = true;
      cg.drawImage(img, ox, oy, w, h);
      cg.strokeStyle = 'rgba(232,112,58,.9)'; cg.lineWidth = 2;
      cg.strokeRect(1, 1, 126, 126);
    }
    cropcv.addEventListener('pointerdown', e => { drag = {x: e.offsetX - ox, y: e.offsetY - oy}; });
    cropcv.addEventListener('pointermove', e => {
      if(!drag) return;
      ox = e.offsetX - drag.x; oy = e.offsetY - drag.y; paintCrop();
    });
    addEventListener('pointerup', () => { drag = null; });
    zoom.oninput = paintCrop;
    el.querySelector('.cancel').onclick = () => { crop.hidden = true; };

    el.querySelector('.media input').onchange = ev => {
      const file = ev.target.files[0];
      if(!file) return;
      const fr = new FileReader();
      fr.onload = () => {
        raw = fr.result;
        if(file.type === 'image/gif' || file.type.startsWith('video/')){  // נשלח שלם, בלי חיתוך
          reply.textContent = file.type.startsWith('video/') ? 'מעלה וידאו (רגע)...' : 'שולח אנימציה...';
          api('/api/media', {panel: p.name, data: raw})
            .then(r => reply.textContent = 'מוצג: ' + r.file)
            .catch(e => reply.textContent = 'שגיאה: ' + e.message);
          return;
        }
        img = new Image();
        img.onload = () => { ox = oy = 0; zoom.value = 100; crop.hidden = false; paintCrop(); };
        img.src = raw;
      };
      fr.readAsDataURL(file);
    };
    el.querySelector('.apply').onclick = async () => {
      reply.textContent = 'מעלה...';
      try{
        const r = await api('/api/media', {panel: p.name, data: cropcv.toDataURL('image/png')});
        reply.textContent = 'מוצג: ' + r.file;
        crop.hidden = true;
      }catch(e){ reply.textContent = 'שגיאה: ' + e.message; }
    };
    const sel = el.querySelector('.persona');
    Object.entries(PERSONAS).forEach(([key, who]) => {
      const o = document.createElement('option');
      o.value = key; o.textContent = who.emoji + ' ' + who.name + ' — ' + who.trait;
      if(key === p.persona) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = async () => {
      try{
        const r = await api('/api/persona', {panel: p.name, persona: sel.value});
        reply.textContent = 'האישיות עכשיו: ' + r.persona;
      }catch(e){ reply.textContent = 'שגיאה: ' + e.message; }
    };
    el.querySelector('.forget').onclick = async () => {
      await api('/api/forget', {panel: p.name});
      reply.textContent = 'הזיכרון נמחק';
    };
    box.addEventListener('keydown', e => { if(e.key === 'Enter') run('/api/say'); });
    grid.appendChild(el);
  });
}

$('#bright').oninput = e => { $('#brightVal').textContent = e.target.value + '%'; };
$('#bright').onchange = e => api('/api/brightness', {value: +e.target.value});

$('#magicBtn').onclick = () => {
  magic = !magic;
  $('#magicBtn').setAttribute('aria-pressed', magic ? 'true' : 'false');
  $('#magicBtn').textContent = magic ? '✨ קסם פעיל' : '✨ מצב קסם';
  if(magic && !sensing) $('#senseBtn').click();
};
$('#clearBtn').onclick = () => api('/api/paint', {clear: true});

// קלוד בין הקיר לשולחן העבודה
$('#outBtn').onclick = async () => {
  $('#outBtn').textContent = '🖥️ יוצא...';
  try{ await api('/api/desktop', {action: 'out', size: +$('#dsize').value}); }
  catch(e){ $('#heardLabel').textContent = 'שגיאה: ' + e.message; }
  $('#outBtn').textContent = '🖥️ צא לשולחן העבודה';
};
$('#backBtn').onclick = () => api('/api/desktop', {action: 'back'});
$('#dsize').oninput = e => { $('#dsizeVal').textContent = e.target.value; };
$('#dsize').onchange = e => api('/api/desktop', {action: 'size', size: +e.target.value});

// הרשת החברתית של הקלודים
function when(ts){
  const d = Math.max(0, Date.now()/1000 - ts);
  if(d < 60) return 'עכשיו';
  if(d < 3600) return Math.floor(d/60) + ' דק׳';
  return Math.floor(d/3600) + ' שע׳';
}
async function loadFeed(){
  try{
    const r = await api('/api/feed', {});
    const box = $('#feed');
    box.innerHTML = '';
    if(!r.posts.length){ box.innerHTML = '<div class="empty">הרשת ריקה. תן להם לכתוב.</div>'; return; }
    r.posts.forEach(post => {
      const who = r.personas[post.persona] || {emoji:'🤖', name: post.persona};
      const el = document.createElement('div');
      el.className = 'post' + (post.kind === 'party' ? ' party' : '');
      el.innerHTML = '<div class="who">' + who.emoji + ' <b>' + who.name + '</b>' +
                     '<span class="meta">' + post.panel + ' · ' + when(post.at) +
                     (post.kind === 'comment' ? ' · תגובה' : '') +
                     (post.kind === 'party' ? ' · 🎉' : '') + '</span></div>' +
                     '<div class="text"></div>';
      el.querySelector('.text').textContent = post.text;
      box.appendChild(el);
    });
  }catch(e){ $('#feed').innerHTML = '<div class="empty">שגיאה: ' + e.message + '</div>'; }
}
$('#feedBtn').onclick = loadFeed;
$('#wipeBtn').onclick = async () => { await api('/api/feed', {clear: true}); loadFeed(); };
$('#partyBtn').onclick = async () => {
  $('#partyBtn').textContent = '🎉 המסיבה רצה...';
  try{ await api('/api/party', {}); }catch(e){}
  setTimeout(() => { $('#partyBtn').textContent = '🎉 PARTY MODE'; loadFeed(); }, 25000);
};
$('#postBtn').onclick = async () => {
  $('#postBtn').textContent = '✍️ כותבים...';
  for(const p of PANELS){
    try{ await api('/api/feed', {write: true, panel: p.name}); }catch(e){}
    loadFeed();
  }
  $('#postBtn').textContent = '✍️ שיכתבו פוסטים';
};

// שמיעה: מקליט כשמדברים, שולח כשנוצרת שתיקה, ועונה מהפאנל הפעיל
let hearing = false, recorder = null, chunks = [], talking = false, quiet = 0, busy = false;
$('#hearBtn').onclick = async () => {
  hearing = !hearing;
  $('#hearBtn').setAttribute('aria-pressed', hearing ? 'true' : 'false');
  $('#hearBtn').textContent = hearing ? '🎤 מקשיב פעיל' : '🎤 הוא מקשיב';
  if(hearing && !sensing) await $('#senseBtn').onclick();
  $('#heardLabel').textContent = hearing ? 'דבר אליו...' : 'ההקשבה כבויה';
};

function feedHearing(level, stream){
  if(!hearing || busy) return;
  if(!recorder){
    recorder = new MediaRecorder(stream, {mimeType: 'audio/webm'});
    recorder.ondataavailable = e => chunks.push(e.data);
    recorder.onstop = async () => {
      const blob = new Blob(chunks, {type: 'audio/webm'});
      chunks = [];
      if(blob.size < 4000){ busy = false; return; }
      $('#heardLabel').textContent = 'מתמלל...';
      const fr = new FileReader();
      fr.onload = async () => {
        try{
          const r = await api('/api/hear', {panel: focusPanel, data: fr.result});
          $('#heardLabel').textContent = r.heard
            ? ('שמע: ' + r.heard + (r.reply ? '  →  ' + r.reply : ''))
            : 'לא הצלחתי לזהות. נסה שוב.';
        }catch(e){ $('#heardLabel').textContent = 'שגיאה: ' + e.message; }
        busy = false;
      };
      fr.readAsDataURL(blob);
    };
  }
  if(level > 0.10){
    quiet = 0;
    if(!talking){ talking = true; recorder.start(); $('#heardLabel').textContent = 'שומע אותך...'; }
  }else if(talking){
    quiet += 1;
    if(quiet >= 5){                      // כשנייה של שקט = סוף משפט
      talking = false; quiet = 0; busy = true;
      try{ recorder.stop(); }catch(e){ busy = false; }
    }
  }
}

$('#senseBtn').onclick = async () => {
  if(sensing) return;
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio: true, video: true});
    const cam = $('#cam'); cam.srcObject = stream; await cam.play();
    const ctx = new AudioContext();
    const an = ctx.createAnalyser(); an.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Uint8Array(an.frequencyBinCount);
    const cv = document.createElement('canvas'); cv.width = 64; cv.height = 48;
    const g = cv.getContext('2d', {willReadFrequently: true});
    let prev = null;
    sensing = true;
    $('#dot').classList.add('live');
    $('#senseLabel').textContent = 'חיישנים פעילים';
    $('#senseBtn').textContent = 'פעיל';
    setInterval(async () => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for(const v of buf){ const d = (v - 128) / 128; sum += d * d; }
      const level = Math.min(1, Math.sqrt(sum / buf.length) * 4);
      $('#meter').style.width = (level * 100).toFixed(0) + '%';
      g.drawImage(cam, 0, 0, cv.width, cv.height);
      const cur = g.getImageData(0, 0, cv.width, cv.height).data;
      let mass = 0, cx = 0, cy = 0;
      if(prev){
        for(let i = 0, px = 0; i < cur.length; i += 4, px++){
          if(Math.abs(cur[i] - prev[i]) > 24){ mass++; cx += px % cv.width; cy += (px / cv.width) | 0; }
        }
      }
      prev = cur;
      const present = mass > 12;
      const gaze = present ? [(cx / mass) / cv.width * 2 - 1, (cy / mass) / cv.height * 2 - 1] : [0, 0];
      try{ await api('/api/sense', {level, present, gaze}); }catch(e){}
      feedHearing(level, stream);
      if(magic && present){
        // תנועה מול המצלמה -> משיכת מכחול על הקיר. מראה, כדי שיהיה טבעי
        const nx = 1 - (cx / mass) / cv.width;
        const ny = (cy / mass) / cv.height;
        hue = (hue + 7) % 360;
        const power = Math.min(1, mass / 320 + level);
        try{ await api('/api/paint', {dabs: [[nx, ny, power, hue]]}); }catch(e){}
      }
    }, 200);
  }catch(e){ $('#senseLabel').textContent = 'אין גישה למצלמה או למיקרופון'; }
};
</script></body></html>
"""


def demo():
    """בדיקה עצמית: הדף נבנה, הפאנלים והדמויות מוזרקים, והסיסמה נאכפת."""
    page = html_page()
    assert "J1.1" in page and "J2.2" in page, "שמות הפאנלים חייבים להופיע בדף"
    assert "__PANELS__" not in page and "__CHARACTERS__" not in page, "נשארו תבניות לא מוחלפות"
    assert "critter" in page, "ספריית הדמויות חייבת להופיע בדף"
    assert len(live_panels()) == 4, "ארבעה פאנלים מחוברים"
    assert hmac.compare_digest(PASSWORD, "1892346"), "סיסמת ברירת המחדל"
    print("golem_app demo OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        demo()
        return 0
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"GOLEM: http://127.0.0.1:{a.port}", flush=True)
    if a.open:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{a.port}")).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
