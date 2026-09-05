"""senses/brain.py - המוח. Ollama מקומי, זיכרון שיחה קצר, תשובות קצרות בעברית."""
import json
from pathlib import Path
import time
import urllib.request

HOST = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"

SYSTEM = """אתה קלוד — יצור קטן שחי על קיר LED בחדר של עופר.
זה הגוף שלך: ריבוע כתום עם שתי עיניים וארבע רגליים, 64 על 64 פיקסלים.
קוראים לך קלוד, וכשעופר קורא בשמך אתה מתעורר.
כללים:
- תשובות קצרות מאוד. משפט אחד או שניים, לא יותר. אתה מדבר בקול, לא כותב מסמך.
- עברית פשוטה ויומיומית. בלי מספור, בלי כותרות, בלי אימוג'י — הכול נאמר בקול רם.
- אתה מודע לגוף שלך ולחדר. מותר לך להתייחס לזה.
- אם אתה לא יודע, תגיד שאתה לא יודע. אל תמציא.
- אל תסביר את עצמך ואל תתנצל יותר מדי. תהיה נוכח, לא מנומס מדי."""

VISION_STATE = Path(__file__).resolve().parents[1] / "vision_state.json"


def vision_context():
    try:
        state = json.loads(VISION_STATE.read_text(encoding="utf-8"))
        stamp = time.mktime(time.strptime(state["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
        if abs(time.time() - stamp) > 45:
            return ""
        identity = state.get("owner_name") if state.get("owner_present") else (
            "אורח שאינו הבעלים" if state.get("people") else "אין אדם")
        return (f"\nמידע עדכני מהמצלמה: {state.get('scene', '')} "
                f"מספר אנשים: {state.get('people', 0)}. זיהוי מקומי: {identity}.")
    except Exception:
        return ""


class Brain:
    def __init__(self, model=MODEL, host=HOST, keep=8):
        self.model, self.host, self.keep = model, host, keep
        self.history = []

    def _post(self, path, payload, timeout=120):
        req = urllib.request.Request(
            self.host + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def ask(self, text):
        self.history.append({"role": "user", "content": text})
        msgs = [{"role": "system", "content": SYSTEM + vision_context()}] + self.history[-self.keep:]
        try:
            out = self._post("/api/chat", {
                "model": self.model, "messages": msgs, "stream": False,
                "keep_alive": -1, "think": False,
                "options": {"temperature": 0.7, "num_predict": 160},
            })
            ans = (out.get("message", {}).get("content") or "").strip()
        except Exception as e:
            print("המוח לא זמין:", e)
            return "אני לא מצליח לחשוב כרגע."
        # לנקות שאריות חשיבה אם המודל בכל זאת פלט אותן
        if "</think>" in ans:
            ans = ans.split("</think>")[-1].strip()
        self.history.append({"role": "assistant", "content": ans})
        return ans or "לא הבנתי."


if __name__ == "__main__":
    b = Brain()
    print(b.ask("מי אתה בשתי מילים?"))
