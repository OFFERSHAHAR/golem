"""senses/ears.py - אוזניים. מיקרופון פתוח, חיתוך לפי שקט, ותמלול עברית מקומי.

    from senses.ears import Ears
    for text in Ears().listen():
        print(text)
"""
import queue
import sys
import time

import glob
import os
import site

import numpy as np
import sounddevice as sd


def _enable_cuda_dlls():
    """ספריות CUDA מגיעות כחבילות pip. בלי זה ctranslate2 לא מוצא cuDNN בווינדוס."""
    dirs = []
    for sp in site.getsitepackages():
        dirs += glob.glob(os.path.join(sp, "nvidia", "*", "bin"))
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


_enable_cuda_dlls()
from faster_whisper import WhisperModel

SR = 16000
BLOCK = 480                 # 30 מ"ש


class Ears:
    def __init__(self, model="small", device="cpu", compute_type="int8",
                 silence=1.45, min_len=0.5, max_len=18.0, gate=2.8, mic=None):
        self.mic = mic
        print(f"טוען מודל תמלול ({model}, {device})...", flush=True)
        self.model = WhisperModel(model, device=device, compute_type=compute_type)
        self.silence, self.min_len, self.max_len, self.gate = silence, min_len, max_len, gate
        self.q = queue.Queue()
        self.floor = 0.004
        self.muted = False           # נדליק בזמן שהוא מדבר, שלא ישמע את עצמו

    def _cb(self, indata, frames, t, status):
        self.q.put(indata[:, 0].copy())

    def calibrate(self, stream, secs=1.2):
        vals = []
        t0 = time.time()
        while time.time() - t0 < secs:
            try:
                vals.append(float(np.sqrt((self.q.get(timeout=1) ** 2).mean())))
            except queue.Empty:
                break
        if vals:
            self.floor = max(0.002, float(np.median(vals)))
        print(f"רעש רקע: {self.floor:.4f} · סף כניסה: {self.floor * self.gate:.4f}", flush=True)

    def listen(self):
        """גנרטור: מחזיר טקסט לכל משפט שנאמר."""
        with sd.InputStream(samplerate=SR, channels=1, blocksize=BLOCK, device=self.mic,
                            dtype="float32", callback=self._cb) as stream:
            self.calibrate(stream)
            thr = self.floor * self.gate
            buf, rec, quiet, t_start = [], False, 0.0, 0.0
            while True:
                block = self.q.get()
                if self.muted:
                    buf, rec, quiet = [], False, 0.0
                    continue
                rms = float(np.sqrt((block ** 2).mean()))
                if not rec:
                    if rms > thr:
                        rec, buf, quiet, t_start = True, [block], 0.0, time.time()
                else:
                    buf.append(block)
                    quiet = 0.0 if rms > thr * 0.7 else quiet + BLOCK / SR
                    long = time.time() - t_start > self.max_len
                    if quiet >= self.silence or long:
                        audio = np.concatenate(buf)
                        rec, buf = False, []
                        if len(audio) / SR >= self.min_len:
                            text = self.transcribe(audio)
                            if text:
                                yield text

    PROMPT = ("שיחה בעברית עם קלוד, יצור קטן שחי על קיר לד. "
              "עופר מדבר אליו ומבקש ממנו דברים: קוסם, שף, בוקר, גלימה, כתר, אוזניות, מסיבה.")

    def transcribe(self, audio):
        segs, _ = self.model.transcribe(
            audio, language="he", beam_size=5, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=self.PROMPT,
            temperature=0.0, no_speech_threshold=0.5)
        text = " ".join(s.text.strip() for s in segs).strip()
        # ויסקי נוטה להמציא כשאין דיבור אמיתי — מסננים חזרות
        words = text.split()
        if len(words) > 3 and len(set(words)) <= 2:
            return ""
        return text


if __name__ == "__main__":
    e = Ears(model=sys.argv[1] if len(sys.argv) > 1 else "small")
    print("מקשיב. דבר.", flush=True)
    for t in e.listen():
        print(">>", t, flush=True)
