"""
face/critter.py - קלוד הפיקסלי: גוף, שתי ידיים, ארבע רגליים, ומגוון הבעות וכובעים.
ממשק: set(state, amp, gaze, emote, expr, hat) ו-render() -> 128x128.

expr: neutral | happy | wink | closed | cool | surprised | sad
hat:  none | chef | wizard | cowboy | cape
"""
import math
import random
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

N, CELL = 128, 8
BODY = (216, 116, 76)
BODY_DIM = (150, 78, 50)
DARK = (92, 44, 26)
WHITE = (238, 234, 226)
PURPLE = (62, 58, 122)
YELLOW = (240, 198, 70)
BROWN = (128, 84, 48)
RED = (176, 44, 44)
BG = (0, 0, 0)

STATES = ("idle", "listen", "think", "speak", "error")
EXPRS = ("neutral", "happy", "wink", "closed", "cool", "surprised", "sad")
HATS = ("none", "chef", "wizard", "cowboy", "cape", "suit",
        "crown", "headphones", "party", "goggles")
GREY = (74, 74, 84)
PINK = (214, 74, 132)
CYAN = (70, 180, 190)

BODY_BOX = (2, 13, 4, 10)      # עמודות, שורות (בתאים)
ARM_COLS = (1, 14)
ARM_ROWS = (7, 8)
LEG_COLS = (3, 5, 10, 12)
LEG_ROWS = (11, 12)
EYE_X = (44, 84)               # בפיקסלים ב-128
EYE_Y = 56
MOUTH_Y = 74


class _Shift:
    """עוטף ImageDraw ומזיז כל ציור ב-dx פיקסלים אופקית."""

    def __init__(self, d, dx):
        self.d, self.dx = d, dx

    def _s(self, box):
        if isinstance(box[0], (tuple, list)):
            return [(x + self.dx, y) for x, y in box]
        return [v + self.dx if i % 2 == 0 else v for i, v in enumerate(box)]

    def rectangle(self, box, **kw):
        self.d.rectangle(self._s(box), **kw)

    def rounded_rectangle(self, box, **kw):
        self.d.rounded_rectangle(self._s(box), **kw)

    def ellipse(self, box, **kw):
        self.d.ellipse(self._s(box), **kw)

    def arc(self, box, *a, **kw):
        self.d.arc(self._s(box), *a, **kw)

    def line(self, pts, **kw):
        self.d.line(self._s(pts), **kw)

    def polygon(self, pts, **kw):
        self.d.polygon(self._s(pts), **kw)


@dataclass
class Critter:
    brightness: float = 1.0
    state: str = "idle"
    amp: float = 0.0
    gaze: tuple = (0.0, 0.0)
    expr: str = "neutral"
    hat: str = "none"
    scale: float = 1.0
    bob: int = 2            # עוצמת הנשימה בפיקסלים (ב-128). 0 = עומד לגמרי
    _amp: float = 0.0
    _gz: list = field(default_factory=lambda: [0.0, 0.0])
    _blink_until: float = 0.0
    _next_blink: float = field(default_factory=lambda: time.monotonic() + 2.5)

    def set(self, state=None, amp=None, gaze=None, emote=None, expr=None, hat=None):
        if state in STATES:
            self.state = state
        if amp is not None:
            self.amp = max(0.0, min(1.0, float(amp)))
        if gaze is not None:
            self.gaze = (max(-1, min(1, gaze[0])), max(-1, min(1, gaze[1])))
        if expr in EXPRS:
            self.expr = expr
        if hat in HATS:
            self.hat = hat

    # ---------- אלמנטים ----------
    def _eye(self, d, cx, cy, kind, col):
        w = 4
        if kind == "slit":
            d.rectangle([cx - 4, cy - 8, cx + 3, cy + 7], fill=col)
        elif kind == "chev_r":                       # >
            d.line([(cx - 5, cy - 8), (cx + 4, cy), (cx - 5, cy + 8)], fill=col, width=w)
        elif kind == "chev_l":                       # <
            d.line([(cx + 4, cy - 8), (cx - 5, cy), (cx + 4, cy + 8)], fill=col, width=w)
        elif kind == "line":
            d.rectangle([cx - 8, cy - 2, cx + 7, cy + 2], fill=col)
        elif kind == "arc_up":                       # ^
            d.line([(cx - 8, cy + 5), (cx, cy - 5), (cx + 8, cy + 5)], fill=col, width=w)
        elif kind == "arc_dn":                       # v הפוך, עצוב
            d.line([(cx - 8, cy - 5), (cx, cy + 5), (cx + 8, cy - 5)], fill=col, width=w)
        elif kind == "wide":
            d.ellipse([cx - 7, cy - 9, cx + 6, cy + 8], fill=col)

    def _mouth(self, d, y, col, kind, amp=0.0, dx=0):
        if kind == "none":
            return
        d = _Shift(d, dx)
        if kind == "open":
            h = 4 + amp * 12
            w = 10 + amp * 6
            d.rounded_rectangle([64 - w, y - h / 2, 64 + w, y + h / 2],
                                radius=min(5, h / 2), fill=col)
        elif kind == "small":
            d.rectangle([58, y - 2, 69, y + 2], fill=col)
        elif kind == "smile":
            d.arc([48, y - 14, 80, y + 8], 20, 160, fill=col, width=4)
        elif kind == "chev":                          # פה קטן בצורת <
            d.line([(60, y - 5), (68, y), (60, y + 5)], fill=col, width=3)

    def _hat(self, d, dy, k):
        top = 32 + dy                 # קצה הגוף העליון (dy בפיקסלים)
        if self.hat == "chef":
            d.rounded_rectangle([44, top - 24, 84, top - 6], radius=9,
                                fill=tuple(int(c * k) for c in WHITE))
            d.rectangle([46, top - 8, 82, top - 1], fill=tuple(int(c * k) for c in WHITE))
        elif self.hat == "wizard":
            p = tuple(int(c * k) for c in PURPLE)
            d.polygon([(64, top - 34), (46, top - 6), (82, top - 6)], fill=p)
            d.rectangle([40, top - 8, 88, top - 1], fill=p)
            y = tuple(int(c * k) for c in YELLOW)
            d.rectangle([61, top - 26, 67, top - 20], fill=y)
        elif self.hat == "cowboy":
            b = tuple(int(c * k) for c in BROWN)
            d.ellipse([34, top - 12, 94, top - 1], fill=b)
            d.rounded_rectangle([50, top - 26, 78, top - 8], radius=6, fill=b)
        elif self.hat == "cape":
            r = tuple(int(c * k) for c in RED)
            d.polygon([(20, 34 + dy), (108, 34 + dy),
                       (100, 104 + dy), (28, 104 + dy)], fill=r)
        elif self.hat == "crown":
            y = tuple(int(c * k) for c in YELLOW)
            d.polygon([(44, top - 2), (44, top - 20), (54, top - 10), (64, top - 24),
                       (74, top - 10), (84, top - 20), (84, top - 2)], fill=y)
        elif self.hat == "headphones":
            g = tuple(int(c * k) for c in GREY)
            d.arc([34, top - 20, 94, top + 40], 180, 360, fill=g, width=7)
            d.rounded_rectangle([26, top + 12, 40, top + 36], radius=5, fill=g)
            d.rounded_rectangle([88, top + 12, 102, top + 36], radius=5, fill=g)
        elif self.hat == "party":
            p = tuple(int(c * k) for c in PINK)
            c2 = tuple(int(c * k) for c in CYAN)
            d.polygon([(64, top - 32), (50, top - 2), (78, top - 2)], fill=p)
            d.polygon([(64, top - 20), (57, top - 8), (71, top - 8)], fill=c2)
            d.ellipse([59, top - 38, 69, top - 28], fill=tuple(int(c * k) for c in YELLOW))
        elif self.hat == "goggles":
            c2 = tuple(int(c * k) for c in CYAN)
            g = tuple(int(c * k) for c in GREY)
            ey = EYE_Y + dy
            d.rectangle([24, ey - 4, 104, ey + 2], fill=g)
            d.ellipse([32, ey - 14, 58, ey + 12], outline=c2, width=5)
            d.ellipse([70, ey - 14, 96, ey + 12], outline=c2, width=5)
        elif self.hat == "suit":
            g = tuple(int(c * k) for c in GREY)
            r = tuple(int(c * k) for c in RED)
            y0 = 64 + dy
            d.rectangle([16, y0, 52, 88 + dy], fill=g)     # דש שמאלי
            d.rectangle([76, y0, 112, 88 + dy], fill=g)    # דש ימני
            d.polygon([(58, y0), (70, y0), (67, y0 + 8), (61, y0 + 8)], fill=r)
            d.polygon([(61, y0 + 8), (67, y0 + 8), (69, y0 + 22), (59, y0 + 22)], fill=r)

    # ---------- ציור ----------
    def render(self) -> Image.Image:
        now = time.monotonic()
        self._amp += (self.amp - self._amp) * .3
        self._gz[0] += (self.gaze[0] - self._gz[0]) * .12
        self._gz[1] += (self.gaze[1] - self._gz[1]) * .12
        if now > self._next_blink:
            self._next_blink = now + 2.4 + random.random() * 4.0
            self._blink_until = now + 0.13
        blinking = now < self._blink_until

        img = Image.new("RGB", (N, N), BG)
        d = ImageDraw.Draw(img)
        k = self.brightness
        body = tuple(int(c * k) for c in (BODY_DIM if self.state == "error" else BODY))

        # נשימה — בפיקסלים, לא בתאים. ברירת מחדל 2 פיקסלים ב-128 = פיקסל אחד על הפאנל
        rate = 2.0 if self.state == "speak" else (2.6 if self.state == "think" else 1.0)
        dy = -int(round((math.sin(now * rate * math.pi) * 0.5 + 0.5) * self.bob))

        lean = int(round(self._gz[0] * 5))          # כל הגוף נוטה לכיוונך

        def cell(c0, c1, r0, r1, col):
            d.rectangle([c0 * CELL + lean, r0 * CELL + dy,
                         (c1 + 1) * CELL - 1 + lean, (r1 + 1) * CELL - 1 + dy], fill=col)

        if self.hat == "cape":
            self._hat(d, dy, k)

        c0, c1, r0, r1 = BODY_BOX
        cell(c0, c1, r0, r1, body)
        cell(ARM_COLS[0], ARM_COLS[0], ARM_ROWS[0], ARM_ROWS[1], body)
        cell(ARM_COLS[1], ARM_COLS[1], ARM_ROWS[0], ARM_ROWS[1], body)

        swap = (int(now * 6) % 2) if self.state in ("speak", "listen") else 0
        for i, lc in enumerate(LEG_COLS):
            cell(lc, lc, LEG_ROWS[0], LEG_ROWS[1] - (1 if (swap and i % 2) else 0), body)

        if self.hat not in ("none", "cape"):
            self._hat(d, dy, k)

        # ---- הבעה ----
        gx = lean + int(round(self._gz[0] * 9))     # האישונים זזים יותר מהגוף
        gy = int(round(self._gz[1] * 6))
        ey = EYE_Y + dy + gy
        eyes, mouth = "slit", "none"
        if self.expr == "happy":
            eyes, mouth = "happy", "open"
        elif self.expr == "closed":
            eyes, mouth = "line", "smile"
        elif self.expr == "wink":
            eyes, mouth = "wink", "chev"
        elif self.expr == "cool":
            eyes, mouth = "cool", "small"
        elif self.expr == "surprised":
            eyes, mouth = "wide", "open"
        elif self.expr == "sad":
            eyes, mouth = "sad", "none"

        if self.state == "think" and self.expr == "neutral":
            eyes = "line"
        if self.state == "speak":
            mouth = "open"
        elif self.state == "listen" and mouth == "none":
            mouth = "small"

        if blinking and eyes not in ("cool",):
            eyes = "line"

        if eyes == "cool":
            d.rectangle([32, ey - 7, 96, ey + 5], fill=BG)
            d.rectangle([30, ey - 9, 98, ey - 6], fill=BG)
        elif eyes == "happy":
            self._eye(d, EYE_X[0] + gx, ey, "chev_r", BG)
            self._eye(d, EYE_X[1] + gx, ey, "chev_l", BG)
        elif eyes == "sad":
            self._eye(d, EYE_X[0] + gx, ey, "arc_dn", BG)
            self._eye(d, EYE_X[1] + gx, ey, "arc_dn", BG)
        elif eyes == "wink":
            self._eye(d, EYE_X[0] + gx, ey, "chev_r", BG)
            self._eye(d, EYE_X[1] + gx, ey, "slit", BG)
        else:
            for ex in EYE_X:
                self._eye(d, ex + gx, ey, eyes, BG)

        self._mouth(d, MOUTH_Y + dy, BG, mouth, self._amp, dx=lean)

        if self.scale < 0.995:
            s = max(2, int(round(N * self.scale)))
            out = Image.new("RGB", (N, N), BG)
            out.paste(img.resize((s, s), Image.NEAREST), ((N - s) // 2, (N - s) // 2))
            return out
        return img
