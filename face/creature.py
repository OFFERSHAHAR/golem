"""
face/creature.py - היצור. מחזיק את שלוש הדמויות ואת המעבר ביניהן.

    c = Creature(mode="critter")
    c.set(state="speak", amp=.8)
    c.morph("spark")      # critter | spark | face — עם התכווצות והתפרצות
    img = c.render()      # 128x128
"""
import time

from PIL import Image

from .spark import Spark
from .minimal import MinimalFace
from .critter import Critter
from .bart import Bart

N = 128
COLLAPSE = 0.20
EXPAND = 0.40
MODES = ("critter", "spark", "face", "bart")


def _ease_out(p):
    return 1 - (1 - max(0.0, min(1.0, p))) ** 3


class Creature:
    def __init__(self, mode="critter", theme="dark", brightness=0.85):
        self.r = {"spark": Spark(theme=theme, brightness=brightness),
                  "face": MinimalFace(brightness=brightness),
                  "critter": Critter(brightness=brightness),
                  "bart": Bart(brightness=brightness)}
        self.mode = mode if mode in MODES else "critter"
        self._target = self.mode
        self._t0 = 0.0
        self._phase = None
        self.state = "idle"

    def set(self, state=None, amp=None, gaze=None, emote=None, expr=None, hat=None):
        if state:
            self.state = state
        for name, r in self.r.items():
            if name == "critter":
                r.set(state=state, amp=amp, gaze=gaze, emote=emote, expr=expr, hat=hat)
            else:
                r.set(state=state, amp=amp, gaze=gaze, emote=emote)

    def morph(self, to=None):
        if to is None:
            to = "spark" if self.mode != "spark" else "critter"
        if to not in MODES:
            return
        if to == self.mode and self._phase is None:
            return
        self._target = to
        self._phase = "collapse"
        self._t0 = time.monotonic()

    @property
    def busy(self):
        return self._phase is not None

    def render(self) -> Image.Image:
        s = 1.0
        if self._phase == "collapse":
            p = (time.monotonic() - self._t0) / COLLAPSE
            if p >= 1:
                self.mode, self._phase = self._target, "expand"
                self._t0 = time.monotonic()
                s = 0.06
            else:
                s = 1 - 0.94 * _ease_out(p)
        elif self._phase == "expand":
            p = (time.monotonic() - self._t0) / EXPAND
            if p >= 1:
                self._phase = None
            else:
                e = _ease_out(p)
                s = 0.06 + 0.94 * e

        r = self.r[self.mode]
        if hasattr(r, "scale"):
            r.scale = 1.0
        img = r.render()

        if s < 0.995:
            k = max(2, int(round(N * s)))
            resample = Image.NEAREST if self.mode == "critter" else Image.LANCZOS
            out = Image.new("RGB", (N, N), (0, 0, 0))
            out.paste(img.resize((k, k), resample), ((N - k) // 2, (N - k) // 2))
            return out
        return img
