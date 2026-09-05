"""
face/critter.py - קלוד. מרונדר בסופר-סמפלינג עם פינות מעוגלות, גרדיאנט והילה,
ולא ברשת בלוקים. הפאנל הוא 64x64 בצבע מלא — אין סיבה לבזבז אותו.

expr: neutral | happy | wink | closed | cool | surprised | sad
hat:  none | chef | wizard | cowboy | cape | suit | crown | headphones | party | goggles
"""
import math
import random
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFilter

N = 128                 # מרחב הקואורדינטות
SS = 3                  # סופר-סמפלינג — מצייר ב-384 ומקטין

BODY_TOP = (238, 140, 94)
BODY_BOT = (178, 82, 46)
RIM = (252, 186, 148)
GLOW = (150, 56, 26)
WHITE = (238, 234, 226)
PURPLE = (74, 68, 140)
YELLOW = (244, 202, 78)
BROWN = (136, 90, 52)
RED = (186, 48, 48)
GREY = (86, 86, 98)
CYAN = (78, 190, 200)
BG = (0, 0, 0)

STATES = ("idle", "listen", "think", "speak", "error")
EXPRS = ("neutral", "happy", "wink", "closed", "cool", "surprised", "sad")
HATS = ("none", "chef", "wizard", "cowboy", "cape", "suit",
        "crown", "headphones", "party", "goggles")

# הכול בקואורדינטות של 128
BODY = (16, 32, 112, 90)        # x0 y0 x1 y1
BODY_R = 11
ARM_Y = (56, 74)
ARM_W = 9
LEGS = (28, 45, 83, 100)        # מרכזי הרגליים
LEG_W, LEG_TOP, LEG_BOT = 9, 86, 104
EYE_X = (45, 83)
EYE_Y = 57
EYE_W, EYE_H = 9, 19
MOUTH_Y = 76


def _grad(size, top, bot):
    """גרדיאנט אנכי, מחושב פעם אחת."""
    g = Image.new("RGB", (1, size))
    px = g.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    return g.resize((size, size), Image.BILINEAR)


@dataclass
class Critter:
    brightness: float = 1.0
    state: str = "idle"
    amp: float = 0.0
    gaze: tuple = (0.0, 0.0)
    expr: str = "neutral"
    hat: str = "none"
    scale: float = 1.0
    bob: float = 2.0
    _amp: float = 0.0
    _gz: list = field(default_factory=lambda: [0.0, 0.0])
    _blink: float = 1.0
    _next_blink: float = field(default_factory=lambda: time.monotonic() + 2.5)
    _grad: object = None

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

    # ---------- כלים ----------
    def _rr(self, d, box, r, fill):
        d.rounded_rectangle([v * SS for v in box], radius=r * SS, fill=fill)

    def _col(self, c):
        return tuple(int(v * self.brightness) for v in c)

    # ---------- צורת הגוף ----------
    def _silhouette(self, dx, dy, swap):
        """מסכה של כל הגוף: פלג, ידיים ורגליים, עם פינות מעוגלות."""
        m = Image.new("L", (N * SS, N * SS), 0)
        d = ImageDraw.Draw(m)
        x0, y0, x1, y1 = BODY
        self._rr(d, (x0 + dx, y0 + dy, x1 + dx, y1 + dy), BODY_R, 255)
        # ידיים
        self._rr(d, (x0 - ARM_W + dx, ARM_Y[0] + dy, x0 + 4 + dx, ARM_Y[1] + dy), 4, 255)
        self._rr(d, (x1 - 4 + dx, ARM_Y[0] + dy, x1 + ARM_W + dx, ARM_Y[1] + dy), 4, 255)
        # רגליים
        for i, cx in enumerate(LEGS):
            bot = LEG_BOT - (3 if (swap and i % 2) else 0)
            self._rr(d, (cx - LEG_W / 2 + dx, LEG_TOP + dy,
                         cx + LEG_W / 2 + dx, bot + dy), 4, 255)
        return m

    # ---------- כובעים ----------
    def _hat(self, d, dx, dy):
        top = BODY[1] + dy
        h = self.hat
        if h == "chef":
            c = self._col(WHITE)
            self._rr(d, (44 + dx, top - 26, 84 + dx, top - 6), 10, c)
            self._rr(d, (46 + dx, top - 10, 82 + dx, top + 1), 3, c)
        elif h == "wizard":
            p, y = self._col(PURPLE), self._col(YELLOW)
            d.polygon([((64 + dx) * SS, (top - 38) * SS), ((45 + dx) * SS, (top - 5) * SS),
                       ((83 + dx) * SS, (top - 5) * SS)], fill=p)
            self._rr(d, (39 + dx, top - 9, 89 + dx, top + 1), 4, p)
            self._rr(d, (60 + dx, top - 28, 68 + dx, top - 20), 3, y)
        elif h == "cowboy":
            b = self._col(BROWN)
            d.ellipse([(32 + dx) * SS, (top - 13) * SS, (96 + dx) * SS, (top + 2) * SS], fill=b)
            self._rr(d, (49 + dx, top - 28, 79 + dx, top - 7), 8, b)
        elif h == "crown":
            y = self._col(YELLOW)
            d.polygon([(v * SS) for p in
                       [(43 + dx, top + 1), (43 + dx, top - 22), (54 + dx, top - 11),
                        (64 + dx, top - 27), (74 + dx, top - 11), (85 + dx, top - 22),
                        (85 + dx, top + 1)] for v in p], fill=y)
        elif h == "headphones":
            g = self._col(GREY)
            d.arc([(32 + dx) * SS, (top - 22) * SS, (96 + dx) * SS, (top + 42) * SS],
                  180, 360, fill=g, width=6 * SS)
            self._rr(d, (24 + dx, top + 10, 40 + dx, top + 38), 6, g)
            self._rr(d, (88 + dx, top + 10, 104 + dx, top + 38), 6, g)
        elif h == "party":
            p, c2, y = self._col((222, 82, 140)), self._col(CYAN), self._col(YELLOW)
            d.polygon([((64 + dx) * SS, (top - 36) * SS), ((49 + dx) * SS, (top - 2) * SS),
                       ((79 + dx) * SS, (top - 2) * SS)], fill=p)
            d.polygon([((64 + dx) * SS, (top - 22) * SS), ((56 + dx) * SS, (top - 8) * SS),
                       ((72 + dx) * SS, (top - 8) * SS)], fill=c2)
            d.ellipse([(58 + dx) * SS, (top - 43) * SS, (70 + dx) * SS, (top - 31) * SS], fill=y)

    def _clothes(self, d, dx, dy):
        """מה שמצויר על הגוף עצמו ולא מעליו."""
        if self.hat == "suit":
            g, r = self._col(GREY), self._col(RED)
            y0 = 62 + dy
            self._rr(d, (16 + dx, y0, 50 + dx, 90 + dy), 6, g)
            self._rr(d, (78 + dx, y0, 112 + dx, 90 + dy), 6, g)
            d.polygon([((57 + dx) * SS, y0 * SS), ((71 + dx) * SS, y0 * SS),
                       ((67 + dx) * SS, (y0 + 9) * SS), ((61 + dx) * SS, (y0 + 9) * SS)], fill=r)
            d.polygon([((61 + dx) * SS, (y0 + 9) * SS), ((67 + dx) * SS, (y0 + 9) * SS),
                       ((70 + dx) * SS, (y0 + 24) * SS), ((58 + dx) * SS, (y0 + 24) * SS)], fill=r)
        elif self.hat == "goggles":
            c2, g = self._col(CYAN), self._col(GREY)
            ey = EYE_Y + dy
            self._rr(d, (22 + dx, ey - 4, 106 + dx, ey + 3), 3, g)
            for cx in EYE_X:
                d.ellipse([(cx - 15 + dx) * SS, (ey - 15) * SS,
                           (cx + 15 + dx) * SS, (ey + 15) * SS], outline=c2, width=4 * SS)

    # ---------- עיניים ופה ----------
    def _eye(self, d, cx, cy, kind, blink):
        h = EYE_H * blink
        if kind == "slit":
            self._rr(d, (cx - EYE_W / 2, cy - h / 2, cx + EYE_W / 2, cy + h / 2),
                     EYE_W / 2, BG)
        elif kind in ("chev_r", "chev_l"):
            s = 1 if kind == "chev_r" else -1
            d.line([((cx - 6 * s) * SS, (cy - 9) * SS), ((cx + 5 * s) * SS, cy * SS),
                    ((cx - 6 * s) * SS, (cy + 9) * SS)], fill=BG, width=5 * SS, joint="curve")
        elif kind == "line":
            self._rr(d, (cx - 9, cy - 2.5, cx + 9, cy + 2.5), 2.5, BG)
        elif kind == "arc_dn":
            d.line([((cx - 9) * SS, (cy - 6) * SS), (cx * SS, (cy + 5) * SS),
                    ((cx + 9) * SS, (cy - 6) * SS)], fill=BG, width=5 * SS, joint="curve")
        elif kind == "wide":
            r = 9
            d.ellipse([(cx - r) * SS, (cy - r * 1.05) * SS,
                       (cx + r) * SS, (cy + r * 1.05) * SS], fill=BG)

    def _mouth(self, d, y, kind, dx):
        if kind == "none":
            return
        a = self._amp
        if kind == "open":
            w, h = 12 + a * 8, 4 + a * 14
            self._rr(d, (64 + dx - w, y - h / 2, 64 + dx + w, y + h / 2), min(6, h / 2), BG)
        elif kind == "small":
            self._rr(d, (57 + dx, y - 2.5, 71 + dx, y + 2.5), 2.5, BG)
        elif kind == "smile":
            d.arc([(46 + dx) * SS, (y - 17) * SS, (82 + dx) * SS, (y + 9) * SS],
                  20, 160, fill=BG, width=4 * SS)
        elif kind == "chev":
            d.line([((59 + dx) * SS, (y - 6) * SS), ((68 + dx) * SS, y * SS),
                    ((59 + dx) * SS, (y + 6) * SS)], fill=BG, width=4 * SS, joint="curve")

    # ---------- ציור ----------
    def render(self) -> Image.Image:
        now = time.monotonic()
        self._amp += (self.amp - self._amp) * .3
        self._gz[0] += (self.gaze[0] - self._gz[0]) * .14
        self._gz[1] += (self.gaze[1] - self._gz[1]) * .14
        if now > self._next_blink:
            self._next_blink = now + 2.3 + random.random() * 4.0
            self._blink = 0.0
        self._blink += (1 - self._blink) * .24
        blink = max(0.12, self._blink)

        if self._grad is None:
            self._grad = _grad(N * SS, BODY_TOP, BODY_BOT)
        grad = self._grad
        if self.brightness < 0.999 or self.state == "error":
            f = self.brightness * (0.6 if self.state == "error" else 1.0)
            grad = grad.point(lambda v: int(v * f))

        rate = 2.0 if self.state == "speak" else (2.6 if self.state == "think" else 1.0)
        dy = -(math.sin(now * rate * math.pi) * 0.5 + 0.5) * self.bob
        dx = self._gz[0] * 5.0
        swap = (int(now * 6) % 2) if self.state in ("speak", "listen") else 0

        mask = self._silhouette(dx, dy, swap)

        img = Image.new("RGB", (N * SS, N * SS), BG)
        # הילה חמה מסביב — נותנת לו נפח על רקע שחור
        halo = mask.filter(ImageFilter.GaussianBlur(9 * SS // 2)).point(lambda v: int(v * 0.42))
        img.paste(Image.new("RGB", img.size, self._col(GLOW)), (0, 0), halo)
        img.paste(grad, (0, 0), mask)

        d = ImageDraw.Draw(img)
        # קו אור עדין בקצה העליון
        x0, y0, x1, _ = BODY
        d.arc([(x0 + dx) * SS, (y0 + dy) * SS, (x1 + dx) * SS, (y0 + dy + 2 * BODY_R) * SS],
              200, 340, fill=self._col(RIM), width=2 * SS)

        self._clothes(d, dx, dy)
        if self.hat not in ("none", "suit", "goggles"):
            self._hat(d, dx, dy)

        gx = dx + self._gz[0] * 9
        gy = self._gz[1] * 6
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
        if blink < 0.5 and eyes not in ("cool",):
            eyes = "line"

        if eyes == "cool":
            self._rr(d, (28 + gx, ey - 8, 100 + gx, ey + 5), 4, BG)
        elif eyes == "happy":
            self._eye(d, EYE_X[0] + gx, ey, "chev_r", blink)
            self._eye(d, EYE_X[1] + gx, ey, "chev_l", blink)
        elif eyes == "sad":
            for cx in EYE_X:
                self._eye(d, cx + gx, ey, "arc_dn", blink)
        elif eyes == "wink":
            self._eye(d, EYE_X[0] + gx, ey, "chev_r", blink)
            self._eye(d, EYE_X[1] + gx, ey, "slit", blink)
        else:
            for cx in EYE_X:
                self._eye(d, cx + gx, ey, eyes, blink)

        self._mouth(d, MOUTH_Y + dy, mouth, dx)
        if self.hat == "goggles":
            self._clothes(d, dx, dy)

        out = img.resize((N, N), Image.LANCZOS)
        if self.scale < 0.995:
            s = max(2, int(round(N * self.scale)))
            canvas = Image.new("RGB", (N, N), BG)
            canvas.paste(out.resize((s, s), Image.LANCZOS), ((N - s) // 2, (N - s) // 2))
            return canvas
        return out
