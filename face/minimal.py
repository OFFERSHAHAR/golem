"""
face/minimal.py - קונספט 02 מתוך FACE_CONCEPTS: שתי עיניים וקשת.
אותו ממשק כמו Spark: set(state, amp, gaze, emote) ו-render() שמחזיר 128x128.
"""
import math
import random
import time
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

N, SS = 128, 3
OR = (232, 112, 58)
OR_DIM = (184, 83, 42)
CREAM = (242, 237, 228)
DEEP = (122, 49, 22)
BG = (0, 0, 0)
STATES = ("idle", "listen", "think", "speak", "error")


def _rr(d, x, y, w, h, r, fill):
    r = max(0.0, min(r, w / 2, h / 2))
    d.rounded_rectangle([x * SS, y * SS, (x + w) * SS, (y + h) * SS],
                        radius=r * SS, fill=fill)


@dataclass
class MinimalFace:
    brightness: float = 1.0
    state: str = "idle"
    amp: float = 0.0
    gaze: tuple = (0.0, 0.0)
    _amp: float = 0.0
    _gz: list = field(default_factory=lambda: [0.0, 0.0])
    _blink: float = 1.0
    _next_blink: float = field(default_factory=lambda: time.monotonic() + 2.5)
    scale: float = 1.0            # לשימוש אנימציית המעבר

    def set(self, state=None, amp=None, gaze=None, emote=None):
        if state in STATES:
            self.state = state
        if amp is not None:
            self.amp = max(0.0, min(1.0, float(amp)))
        if gaze is not None:
            self.gaze = (max(-1, min(1, gaze[0])), max(-1, min(1, gaze[1])))

    def _tick(self, now):
        self._amp += (self.amp - self._amp) * .28
        self._gz[0] += (self.gaze[0] - self._gz[0]) * .08
        self._gz[1] += (self.gaze[1] - self._gz[1]) * .08
        if now > self._next_blink:
            self._next_blink = now + 2.2 + random.random() * 4.2
            self._blink = 0.0
        self._blink += (1 - self._blink) * .22

    def render(self) -> Image.Image:
        now = time.monotonic()
        self._tick(now)
        k = self.brightness
        orange = tuple(int(c * k) for c in (OR_DIM if self.state == "error" else OR))
        cream = tuple(int(c * k) for c in CREAM)
        deep = tuple(int(c * k) for c in DEEP)

        img = Image.new("RGB", (N * SS, N * SS), BG)
        d = ImageDraw.Draw(img)

        S = max(.02, self.scale)
        gx, gy = self._gz
        bob = math.sin(now * 5.7) * 1.5
        opn = 1.12 if self.state == "listen" else 1.0
        eh = max(4.0, 30 * self._blink * opn) * S
        ew = 30 * S

        for ex_base in (30, 68):
            ex = 64 + (ex_base + 15 - 64) * S - ew / 2
            ey = 64 + (44 + 15 - 64) * S - eh / 2 + bob
            _rr(d, ex, ey, ew, eh, min(11 * S, eh / 2), orange)
            if eh > 10 * S:
                px = ex + ew / 2 + gx * 7 * S - 4.5 * S
                py = ey + eh / 2 + gy * 5 * S - 4.5 * S
                _rr(d, px, py, 9 * S, 9 * S, 3.5 * S, cream)
                if self.state == "think":
                    _rr(d, px + S, py - 2.5 * S, 3 * S, 3 * S, 1.2 * S, deep)

        my = 64 + (94 - 64) * S + bob
        if self.state == "speak":
            h = (3 + self._amp * 15) * S
            w = (20 + self._amp * 9) * S
            d.ellipse([(64 - w / 2) * SS, (my + 2 - h / 2 - 2 * S) * SS,
                       (64 + w / 2) * SS, (my + 2 + h / 2 + 2 * S) * SS], fill=orange)
            if h > 4 * S:
                d.ellipse([(64 - w / 2 + 4 * S) * SS, (my + 3 - max(.5, h / 2 - 1.5 * S)) * SS,
                           (64 + w / 2 - 4 * S) * SS, (my + 3 + max(.5, h / 2 - 1.5 * S)) * SS],
                          fill=deep)
        elif self.state == "think":
            d.line([(52 * SS if S > .9 else (64 - 12 * S) * SS), (my + 2) * SS,
                    (76 * SS if S > .9 else (64 + 12 * S) * SS), (my - 1) * SS],
                   fill=orange, width=int(4 * S * SS), joint="curve")
        else:
            r = 18 * S
            box = [(64 - r) * SS, (my - 10 - r) * SS, (64 + r) * SS, (my - 10 + r) * SS]
            d.arc(box, 52, 128, fill=orange, width=max(1, int(5.5 * S * SS)))

        if self.state == "listen" and S > .8:
            for i in range(3):
                a = .10 + self._amp * .55 - i * .05
                if a > 0:
                    col = tuple(int(c * a * k) for c in OR)
                    d.rectangle([(46 + i * 18) * SS, 116 * SS,
                                 (56 + i * 18) * SS, 119 * SS], fill=col)

        return img.resize((N, N), Image.LANCZOS)
