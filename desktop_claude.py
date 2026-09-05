"""desktop_claude.py - קלוד יוצא מהפאנל וחי על שולחן העבודה.

חלון שקוף, תמיד מלמעלה, בלי מסגרת. גוררים אותו עם העכבר, וגלגלת משנה גודל.
מקבל פקודות ב-UDP 9998, אותו חוזה כמו הקיר:

    {"show": true}                 מופיע, נכנס בהליכה מקצה המסך
    {"hide": true}                 יוצא בהליכה וחוזר לפאנל
    {"size": 160}                  גודל בפיקסלים
    {"mode": "critter"}            critter | spark | face
    {"state": "speak", "amp": 0.7} מצב ועוצמת דיבור

    python desktop_claude.py                 מריץ ומחכה לפקודות
    python desktop_claude.py --selftest      בדיקה עצמית בלי לפתוח חלון
"""
import argparse
import json
import os
import queue
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# בחבילה הניידת ספריות tcl יושבות ליד המפרש ולא במקום הרגיל
_tcl = Path(sys.executable).parent / "tcl"
if _tcl.exists():
    os.environ.setdefault("TCL_LIBRARY", str(_tcl / "tcl8.6"))
    os.environ.setdefault("TK_LIBRARY", str(_tcl / "tk8.6"))

from face.creature import Creature

ADDR = ("127.0.0.1", 9998)
CHROMA = "#010203"          # צבע שהופך לשקוף. גוון שלא מופיע בדמות
MIN_SIZE, MAX_SIZE = 64, 512


CHROMA_RGB = (1, 2, 3)
DARK = 24                    # מתחת לזה נחשב רקע ולא חלק מהדמות


def chroma_key(frame):
    """הרקע השחור של הדמות הופך לצבע השקיפות, כדי שהחלון ייראה חתוך."""
    import numpy as np
    arr = np.asarray(frame.convert("RGB"), dtype=np.uint8).copy()
    background = arr.max(axis=2) < DARK
    arr[background] = CHROMA_RGB
    from PIL import Image
    return Image.fromarray(arr)


def walk_path(start, end, steps=26):
    """מסלול כניסה או יציאה, עם האטה בסוף כדי שזה ייראה כמו הליכה."""
    points = []
    for i in range(1, steps + 1):
        p = i / steps
        eased = 1 - (1 - p) ** 3
        points.append(int(start + (end - start) * eased))
    return points


class DesktopClaude:
    def __init__(self, size=160, mode="critter", fps=30):
        import tkinter as tk
        self.tk = tk
        self.size = max(MIN_SIZE, min(MAX_SIZE, size))
        self.fps = fps
        self.creature = Creature(mode=mode, brightness=0.9)
        self.commands = queue.Queue()
        self.visible = False
        self.walk = []
        self.drag = None

        self.root = tk.Tk()
        self.root.overrideredirect(True)                  # בלי מסגרת
        self.root.attributes("-topmost", True)
        self.root.configure(bg=CHROMA)
        self.root.attributes("-transparentcolor", CHROMA)  # רקע שקוף
        self.label = tk.Label(self.root, bg=CHROMA, bd=0, highlightthickness=0)
        self.label.pack()
        self.label.bind("<Button-1>", self._grab)
        self.label.bind("<B1-Motion>", self._move)
        self.label.bind("<MouseWheel>", self._wheel)
        self.label.bind("<Button-3>", lambda e: self.hide())
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.x = self.screen_w - self.size - 40
        self.y = self.screen_h - self.size - 80
        self.root.withdraw()

    # --- אינטראקציה עם העכבר ---
    def _grab(self, event):
        self.drag = (event.x, event.y)

    def _move(self, event):
        if not self.drag:
            return
        self.x = self.root.winfo_x() + event.x - self.drag[0]
        self.y = self.root.winfo_y() + event.y - self.drag[1]
        self.root.geometry(f"+{self.x}+{self.y}")

    def _wheel(self, event):
        self.set_size(self.size + (16 if event.delta > 0 else -16))

    # --- שליטה ---
    def set_size(self, size):
        self.size = max(MIN_SIZE, min(MAX_SIZE, int(size)))

    def show(self):
        if self.visible:
            return
        self.visible = True
        self.root.deiconify()
        self.y = self.screen_h - self.size - 80
        self.walk = walk_path(self.screen_w + self.size, self.x)   # נכנס מהצד

    def hide(self):
        if not self.visible:
            return
        self.walk = walk_path(self.root.winfo_x(), self.screen_w + self.size)
        self.visible = "leaving"

    # --- לולאת הציור ---
    def tick(self):
        while not self.commands.empty():
            self._apply(self.commands.get_nowait())

        if self.walk:
            self.x = self.walk.pop(0)
            if not self.walk and self.visible == "leaving":
                self.visible = False
                self.root.withdraw()

        if self.visible:
            from PIL import ImageTk
            frame = self.creature.render().resize((self.size, self.size))
            self.photo = ImageTk.PhotoImage(chroma_key(frame))   # שמירה מפני איסוף זבל
            self.label.configure(image=self.photo)
            self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        self.root.after(int(1000 / self.fps), self.tick)

    def _apply(self, msg):
        if msg.get("show"):
            self.show()
        if msg.get("hide"):
            self.hide()
        if msg.get("size"):
            self.set_size(msg["size"])
        if msg.get("mode"):
            self.creature.morph(msg["mode"])
        if any(k in msg for k in ("state", "amp", "gaze", "emote", "expr")):
            self.creature.set(state=msg.get("state"), amp=msg.get("amp"),
                              gaze=msg.get("gaze"), emote=msg.get("emote"),
                              expr=msg.get("expr"))

    def listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(ADDR)
        while True:
            try:
                data, _ = sock.recvfrom(65535)
                self.commands.put(json.loads(data.decode()))
            except (ValueError, UnicodeDecodeError):
                continue

    def run(self):
        threading.Thread(target=self.listen, daemon=True).start()
        print(f"קלוד על שולחן העבודה. פקודות ב-UDP {ADDR[1]}", flush=True)
        self.tick()
        self.root.mainloop()


def demo():
    """בדיקה עצמית: מסלול ההליכה מגיע ליעד, והגודל נשאר בתחום."""
    path = walk_path(1000, 200)
    assert path[-1] == 200, path[-1]
    assert len(path) == 26 and path[0] != path[-1], path[:3]
    assert abs(path[1] - path[0]) > abs(path[-1] - path[-2]), "חייבת האטה בסוף"
    for value, expected in ((10, MIN_SIZE), (9999, MAX_SIZE), (180, 180)):
        assert max(MIN_SIZE, min(MAX_SIZE, value)) == expected, value

    # הרקע חייב להפוך לצבע השקיפות, והדמות עצמה חייבת להישאר
    import numpy as np
    from PIL import Image
    test = Image.new("RGB", (4, 4), (0, 0, 0))
    test.putpixel((2, 2), (232, 112, 58))
    keyed = np.asarray(chroma_key(test))
    assert tuple(keyed[0, 0]) == CHROMA_RGB, tuple(keyed[0, 0])
    assert tuple(keyed[2, 2]) == (232, 112, 58), tuple(keyed[2, 2])
    print("desktop demo OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=160)
    ap.add_argument("--mode", default="critter", choices=["critter", "spark", "face"])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        demo()
    else:
        DesktopClaude(size=a.size, mode=a.mode).run()
