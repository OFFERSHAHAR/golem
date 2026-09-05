"""
face/spark.py — הניצוץ החי.
מרנדר את הסימן של Claude כיצור: נשימה, הטיה לעבר האדם, פעימה, דיבור.
פלט: תמונת RGB בגודל 128×128, מוכנה לשליחה לקיר.

ריצה עצמאית לבדיקה:
    python -m face.spark --gif out.gif
"""
import math
import random
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

# ---------- גיאומטריה של הסימן ----------
N = 128                      # קנבס
SS = 3                       # supersampling — מצייר ב-384 ומקטין, נותן קצוות חלקים
RAYS = 12
JIT = [0, -2.4, 1.8, -3.2, 0.9, 2.6, -1.4, 3.1, -0.7, 2.0, -2.8, 1.2]   # מעלות
LEN = [1.00, .86, .96, .81, 1.00, .90, .97, .84, 1.00, .87, .94, .83]
WID = [1.00, .82, .94, .78, 1.00, .86, .92, .80, 1.00, .84, .90, .79]
R0, RMAX, WBASE = 6.0, 42.0, 7.5

THEMES = {
    # (רקע, קרן א', קרן ב', ליבה)
    "dark":  ((0, 0, 0),       (232, 112, 58), (184, 83, 42),  (247, 242, 236)),
    "brand": ((217, 118, 90),  (247, 242, 236), (239, 226, 216), (255, 255, 255)),
    "error": ((0, 0, 0),       (140, 74, 46),  (96, 48, 28),   (200, 150, 120)),
}

STATES = ("idle", "listen", "think", "speak", "error")


def _lerp(a, b, t):
    return a + (b - a) * t


def _blend(c1, c2, t):
    return tuple(int(round(_lerp(c1[i], c2[i], t))) for i in range(3))


def _qbez(p0, p1, p2, steps=8):
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


@dataclass
class Spark:
    theme: str = "dark"
    brightness: float = 0.8          # 0..1 — מכפיל צבע, לא PWM של הכרטיס
    state: str = "idle"
    amp: float = 0.0                 # 0..1 — מעטפת האודיו בזמן דיבור
    gaze: tuple = (0.0, 0.0)         # -1..1 — מיקום האדם ביחס למרכז הפריים
    _gz: list = field(default_factory=lambda: [0.0, 0.0])
    _amp: float = 0.0
    _emote: str = "wake"
    _emote_t0: float = field(default_factory=lambda: time.monotonic())
    _next_pulse: float = field(default_factory=lambda: time.monotonic() + 3.0)

    # ---------- API ----------
    def set(self, state=None, amp=None, gaze=None, emote=None):
        if state in STATES:
            self.state = state
        if amp is not None:
            self.amp = max(0.0, min(1.0, float(amp)))
        if gaze is not None:
            self.gaze = (max(-1, min(1, gaze[0])), max(-1, min(1, gaze[1])))
        if emote:
            self.trigger(emote)

    def trigger(self, emote):
        """wake · pulse · yes · no · alert"""
        self._emote, self._emote_t0 = emote, time.monotonic()

    # ---------- לוגיקה ----------
    def _envelope(self, now):
        """מחזיר scale, dx, dy, glow לפי המחווה הפעילה."""
        scale, dx, dy, glow = 1.0, 0.0, 0.0, 1.0
        e = now - self._emote_t0
        m = self._emote
        if m == "pulse":
            if e < .07:
                scale = 1 - (e / .07) * .82
            elif e < .26:
                scale = .18 + .82 * _ease((e - .07) / .19) * 1.12
            else:
                self._emote = None
        elif m == "wake":
            if e < .9:
                scale, glow = .05 + _ease(e / .9) * 1.06, .3 + e
            else:
                self._emote = None
        elif m == "yes":
            if e < .52:
                scale = 1 - .22 * abs(math.sin(e / .13 * math.pi))
            else:
                self._emote = None
        elif m == "no":
            if e < .56:
                dx = math.sin(e * 14) * 6 * (1 - e / .56)
            else:
                self._emote = None
        elif m == "alert":
            if e < .7:
                p = e / .7
                scale = 1 + .30 * math.sin(p * math.pi * 3) * (1 - p)
                glow = 1 + .8 * (1 - p)
            else:
                self._emote = None
        return max(.05, scale), dx, dy, glow

    def _tick(self, now):
        # החלקה — אף פעם לא לקפוץ ישר לערך היעד
        self._amp += (self.amp - self._amp) * .28
        self._gz[0] += (self.gaze[0] - self._gz[0]) * .07
        self._gz[1] += (self.gaze[1] - self._gz[1]) * .07
        # פעימה תקופתית — הכלל שמונע מהתמונה להיראות קפואה
        if self._emote is None and now > self._next_pulse:
            self._next_pulse = now + 3.0 + random.random() * 4.0
            self.trigger("pulse")

    # ---------- ציור ----------
    def render(self) -> Image.Image:
        now = time.monotonic()
        self._tick(now)
        scale, dx, dy, glow = self._envelope(now)

        theme = "error" if self.state == "error" else self.theme
        bg, cA, cB, core = THEMES[theme]
        k = self.brightness
        bg, cA, cB, core = [tuple(int(c * k) for c in col) for col in (bg, cA, cB, core)]

        img = Image.new("RGB", (N * SS, N * SS), bg)
        d = ImageDraw.Draw(img)

        gx, gy = self._gz
        gmag = min(1.0, math.hypot(gx, gy))
        gang = math.atan2(gy, gx)
        cx, cy = 64 + gx * 8 + dx, 64 + gy * 7 + dy
        breathe = 1 + .04 * math.sin(now * 4.33)
        rot = now * .38 if self.state == "think" else 0.0

        for i in range(RAYS):
            a = math.radians(i * 30 + JIT[i]) - math.pi / 2 + rot
            L = RMAX * LEN[i] * breathe * scale
            L *= 1 + .18 * gmag * max(0.0, math.cos(a - gang))      # הטיה לעברך
            if self.state == "speak":
                L *= 1 + .45 * self._amp * (.6 + .4 * math.sin(i * 1.7 + now * 11))
            elif self.state == "listen":
                L *= 1 + .11 * math.sin(i * 2.1 - now * 3.8) + .18 * self._amp
            elif self.state == "think":
                L *= 1 + .16 * math.sin(i * .9 - now * 3.3)
            elif self.state == "error":
                L *= .35 if i == 4 else .70
            w = WBASE * WID[i] * max(.35, scale)
            self._ray(d, cx, cy, a, max(R0 + 2, L), w, cA)

        # ליבה — נקודה חמה קטנה עם הילה, לא כדור. מתמזגת אל צבע הקרן ולא אל הרקע
        cr = max(1.5, (4.4 + self._amp * 1.8) * min(1.35, scale * glow))
        steps = 7
        for s in range(steps, 0, -1):
            t = s / steps
            col = _blend(core, cA, min(1.0, t ** 1.4))
            r = cr * (0.55 + 0.85 * t)
            d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS], fill=col)

        if self.state == "listen":
            ph = (now % .9) / .9
            r = 20 + ph * 44
            col = _blend(bg, core, max(0.0, (1 - ph) * (.18 + self._amp * .5)))
            d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS],
                      outline=col, width=max(1, SS))

        return img.resize((N, N), Image.LANCZOS)

    def _ray(self, d, cx, cy, ang, length, w, col):
        nx, ny = math.cos(ang), math.sin(ang)
        px, py = -ny, nx
        wi, wo = w * .15, w * .5
        tip = max(R0 + 1, length - wo)
        mid = R0 + (tip - R0) * .5
        p_in_l = (cx + nx * R0 + px * wi, cy + ny * R0 + py * wi)
        p_in_r = (cx + nx * R0 - px * wi, cy + ny * R0 - py * wi)
        p_tip_l = (cx + nx * tip + px * wo, cy + ny * tip + py * wo)
        p_tip_r = (cx + nx * tip - px * wo, cy + ny * tip - py * wo)
        c_l = (cx + nx * mid + px * wo * .98, cy + ny * mid + py * wo * .98)
        c_r = (cx + nx * mid - px * wo * .98, cy + ny * mid - py * wo * .98)

        pts = _qbez(p_in_l, c_l, p_tip_l)
        # כיפה מעוגלת בקצה
        tcx, tcy = cx + nx * tip, cy + ny * tip
        a0 = ang + math.pi / 2
        for s in range(1, 11):
            a = a0 - math.pi * (s / 10)
            pts.append((tcx + math.cos(a) * wo, tcy + math.sin(a) * wo))
        pts += _qbez(p_tip_r, c_r, p_in_r)
        d.polygon([(x * SS, y * SS) for x, y in pts], fill=col)


def _ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gif", default="spark_preview.gif")
    ap.add_argument("--theme", default="dark")
    args = ap.parse_args()

    s = Spark(theme=args.theme)
    frames, plan = [], [("idle", 40), ("listen", 40), ("think", 40), ("speak", 60)]
    for st, n in plan:
        s.state = st
        for i in range(n):
            if st == "speak":
                s.amp = abs(math.sin(i * .5)) * .9
            elif st == "listen":
                s.amp = .2 + .2 * math.sin(i * .3)
            s.gaze = (math.sin(i * .06) * .8, math.cos(i * .05) * .4)
            frames.append(s.render().resize((384, 384), Image.NEAREST))
            time.sleep(1 / 60)
    frames[0].save(args.gif, save_all=True, append_images=frames[1:], duration=33, loop=0)
    print("wrote", args.gif, len(frames), "frames")
