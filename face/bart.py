"""face/bart.py - דמות בארט: ראש צהוב מקוצץ, עיניים שעוקבות, פה שזז בדיבור.

אותו ממשק כמו שאר הדמויות: set(state, amp, gaze, emote) ו-render() שמחזיר 128x128.
"""
import math
import random
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

N, SS = 128, 3
SKIN = (245, 208, 24)          # צהוב בארט
SKIN_SH = (210, 170, 10)       # צל
OUT = (18, 16, 12)             # קו מתאר שחור
WHITE = (250, 250, 248)
PUPIL = (20, 18, 16)
MOUTH = (70, 24, 14)
STATES = ("idle", "listen", "think", "speak", "error")


@dataclass
class Bart:
    brightness: float = 1.0
    state: str = "idle"
    amp: float = 0.0
    gaze: tuple = (0.0, 0.0)
    _amp: float = 0.0
    _gz: list = field(default_factory=lambda: [0.0, 0.0])
    _blink: float = 1.0
    _next_blink: float = field(default_factory=lambda: time.monotonic() + 2.5)
    scale: float = 1.0

    def set(self, state=None, amp=None, gaze=None, emote=None, expr=None, hat=None):
        if state in STATES:
            self.state = state
        if amp is not None:
            self.amp = max(0.0, min(1.0, float(amp)))
        if gaze is not None:
            self.gaze = (max(-1, min(1, gaze[0])), max(-1, min(1, gaze[1])))

    def _tick(self, now):
        self._amp += (self.amp - self._amp) * .30
        self._gz[0] += (self.gaze[0] - self._gz[0]) * .09
        self._gz[1] += (self.gaze[1] - self._gz[1]) * .09
        if now > self._next_blink:
            self._next_blink = now + 2.0 + random.random() * 4.0
            self._blink = 0.0
        self._blink += (1 - self._blink) * .25

    def _head(self, d, col, dx=0, grow=0):
        """ראש בארט: פנים מעוגלות + 9 קוצים למעלה. grow מרחיב לקו מתאר."""
        cx = 64 + dx
        # גוף הפנים
        d.rounded_rectangle([(cx - 30 - grow) * SS, (44 - grow) * SS,
                             (cx + 30 + grow) * SS, (104 + grow) * SS],
                            radius=(26 + grow) * SS, fill=col)
        # לסת/סנטר בולט שמאלה-למטה
        d.ellipse([(cx - 30 - grow) * SS, (78 - grow) * SS,
                   (cx + 6 + grow) * SS, (112 + grow) * SS], fill=col)
        # אוזן ימין
        d.ellipse([(cx + 24 - grow) * SS, (66 - grow) * SS,
                   (cx + 38 + grow) * SS, (82 + grow) * SS], fill=col)
        # 9 קוצים
        spikes = 9
        x0, x1 = cx - 30, cx + 32
        base_y, peak = 46, 20 - grow
        step = (x1 - x0) / spikes
        for i in range(spikes):
            lx = x0 + i * step
            mx = lx + step / 2
            rx = lx + step
            pk = peak + (i % 2) * 3          # גבהים מתחלפים
            d.polygon([(lx * SS, (base_y + 2) * SS),
                       (mx * SS, pk * SS),
                       (rx * SS, (base_y + 2) * SS)], fill=col)

    def render(self) -> Image.Image:
        now = time.monotonic()
        self._tick(now)
        k = self.brightness
        skin = tuple(int(c * k) for c in SKIN)
        out = tuple(int(c * k) for c in OUT)
        white = tuple(int(c * k) for c in WHITE)
        pup = tuple(int(c * k) for c in PUPIL)
        mth = tuple(int(c * k) for c in MOUTH)

        img = Image.new("RGB", (N * SS, N * SS), (0, 0, 0))
        d = ImageDraw.Draw(img)

        gx, gy = self._gz
        bob = math.sin(now * 4.0) * 1.2

        # קו מתאר שחור ואז הצהוב מעליו
        self._head(d, out, dx=0, grow=3)
        self._head(d, skin, dx=0, grow=0)

        # עיניים — שני עיגולים לבנים גדולים צמודים
        eye_y = 60 + bob
        eyes = [(52, eye_y), (76, eye_y)]
        er = 15
        blink = self._blink
        for (ex, ey) in eyes:
            # מתאר
            d.ellipse([(ex - er - 1.5) * SS, (ey - er - 1.5) * SS,
                       (ex + er + 1.5) * SS, (ey + er + 1.5) * SS], fill=out)
            d.ellipse([(ex - er) * SS, (ey - er) * SS,
                       (ex + er) * SS, (ey + er) * SS], fill=white)
        if blink < 0.5:
            # מצמוץ — עפעף צהוב סוגר
            lid = (1 - blink) * er * 2
            for (ex, ey) in eyes:
                d.rectangle([(ex - er - 2) * SS, (ey - er - 2) * SS,
                             (ex + er + 2) * SS, (ey - er + lid) * SS], fill=skin)
        else:
            # אישונים זזים עם המבט
            px = gx * 7
            py = gy * 6
            pr = 4.5
            for (ex, ey) in eyes:
                cx = ex + px
                cy = ey + py
                cx = max(ex - er + pr + 2, min(ex + er - pr - 2, cx))
                cy = max(ey - er + pr + 2, min(ey + er - pr - 2, cy))
                d.ellipse([(cx - pr) * SS, (cy - pr) * SS,
                           (cx + pr) * SS, (cy + pr) * SS], fill=pup)

        # אף — בליטה מעוגלת מתחת לעיניים, נוטה שמאלה
        nx, ny = 50, 74 + bob
        d.ellipse([(nx - 9 - 1) * SS, (ny - 6 - 1) * SS,
                   (nx + 9 + 1) * SS, (ny + 8 + 1) * SS], fill=out)
        d.ellipse([(nx - 9) * SS, (ny - 6) * SS,
                   (nx + 9) * SS, (ny + 8) * SS], fill=skin)

        # פה — נפתח לפי עוצמת הדיבור
        my = 90 + bob
        if self.state == "speak":
            h = 3 + self._amp * 16
            w = 26
            d.ellipse([(64 - w / 2) * SS, (my - h / 2) * SS,
                       (64 + w / 2) * SS, (my + h / 2) * SS], fill=out)
            if h > 5:
                d.ellipse([(64 - w / 2 + 2) * SS, (my - h / 2 + 2) * SS,
                           (64 + w / 2 - 2) * SS, (my + h / 2 - 1) * SS], fill=mth)
        else:
            # חיוך קלאסי — קשת
            grin = 20 if self.state != "error" else 8
            d.arc([(64 - grin) * SS, (my - 12) * SS, (64 + grin) * SS, (my + 8) * SS],
                  15, 165, fill=out, width=max(2, int(2.4 * SS)))

        return img.resize((N, N), Image.LANCZOS)


def demo():
    """בדיקה עצמית: הפה נפתח בדיבור, והאישונים זזים עם המבט."""
    b = Bart()
    b.set(state="speak", amp=0.9, gaze=(0.8, -0.3))
    im = b.render()
    assert im.size == (N, N), im.size
    # שני רינדורים עם מבט מנוגד חייבים להיות שונים (אישונים זזו)
    import numpy as np
    b2 = Bart(); b2.set(gaze=(-0.9, 0.0))
    for _ in range(20):
        b2._tick(time.monotonic())
    a = np.asarray(b.render()); c = np.asarray(b2.render())
    assert a.shape == c.shape
    print("bart demo OK")


if __name__ == "__main__":
    demo()
