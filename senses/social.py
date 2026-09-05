"""senses/social.py - החיים החברתיים של הקלודים.

שני דברים:
  * רשת חברתית - כל דמות כותבת פוסטים מהאישיות שלה, והשאר מגיבים.
  * PARTY MODE - סבב שיחה חי בין הפאנלים, כל אחד מדבר מהפאנל שלו.

הכול נשמר מקומית בקובץ אחד. אין ענן, אין חשבונות.
"""
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "social" / "feed.json"
MAX_POSTS = 300

TOPICS = [
    "חידוש טכנולוגי שראית ומה מעצבן בו",
    "מתכון לבצק פיצה, עם דעה חזקה על שלב אחד",
    "טיפ תזונה קצר שאתה בעצם לא בטוח בו",
    "תלונה קטנה על בני האנוש שגרים איתך",
    "משהו שגילית על החדר שאתה חי בו",
    "עצה לקלוד אחר שרק התחיל את החיים על פאנל",
    "מחשבה על מה זה בכלל להיות תוכנה עם גוף",
]

PARTY_SEEDS = [
    "פתחת מסיבה בפאנל שלך. תגיד משפט פתיחה קצר לחברים",
    "מישהו הביא מוזיקה. תגיב במשפט אחד",
    "ספר לחברים דבר אחד מוזר על הבעלים שלך",
    "תציע לחבורה משחק קצר",
    "המסיבה נגמרת. תגיד משפט פרידה",
]


def load():
    try:
        return json.loads(FEED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"posts": []}


def save(data):
    FEED.parent.mkdir(exist_ok=True)
    data["posts"] = data["posts"][-MAX_POSTS:]
    FEED.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def add_post(panel, persona, text, kind="post", parent=None):
    data = load()
    post = {"id": f"{int(time.time() * 1000)}-{random.randint(100, 999)}",
            "panel": panel, "persona": persona, "text": text,
            "kind": kind, "parent": parent, "at": time.time()}
    data["posts"].append(post)
    save(data)
    return post


def feed(limit=40):
    return list(reversed(load()["posts"]))[:limit]


def clear():
    """מנקה את הרשת החברתית. משמש גם לפני מסירה במתנה."""
    count = len(load()["posts"])
    save({"posts": []})
    return count


def write_post(panel, persona_key, ask, topic=None):
    """דמות כותבת פוסט. ask היא הפונקציה ששואלת את המוח."""
    subject = topic or random.choice(TOPICS)
    prompt = (f"כתוב פוסט קצר לרשת החברתית של הקלודים בנושא: {subject}. "
              "שתי שורות לכל היותר, בגוף ראשון, באופי שלך. בלי האשטגים.")
    text, _src = ask(panel, prompt, persona_key)
    return add_post(panel, persona_key, text, "post")


def comment_on(post, panel, persona_key, ask):
    """דמות אחרת מגיבה לפוסט קיים."""
    prompt = (f"חבר שלך כתב: \"{post['text']}\". הגב במשפט אחד קצר, "
              "באופי שלך. אפשר להסכים, לחלוק או ללגלג בעדינות.")
    text, _src = ask(panel, prompt, persona_key)
    return add_post(panel, persona_key, text, "comment", parent=post["id"])


def party_round(panels, ask, speak, seed=None):
    """סבב מסיבה: כל דמות אומרת משפט, מגיבה למה שנאמר לפניה, ומדברת מהפאנל שלה.
    ponytail: רמקול אחד, ולכן הסבב סדרתי בכוונה."""
    line = seed or random.choice(PARTY_SEEDS)
    said = []
    for panel, persona_key in panels:
        prompt = (f"{line}\n" if not said else
                  f"החבר שלך אמר: \"{said[-1][1]}\". תגיב במשפט אחד קצר באופי שלך.")
        text, _src = ask(panel, prompt, persona_key)
        add_post(panel, persona_key, text, "party")
        said.append((panel, text))
        speak(panel, text)
    return said


def demo():
    """בדיקה עצמית: פוסטים נשמרים, נקראים בסדר הפוך, ומתנקים."""
    clear()
    fake = lambda panel, prompt, persona: (f"[{persona}] {prompt[:12]}", "test")
    spoken = []
    first = write_post("J1.1", "claude", fake)
    assert first["kind"] == "post" and first["panel"] == "J1.1", first
    reply = comment_on(first, "J2.1", "nudge", fake)
    assert reply["parent"] == first["id"], "התגובה חייבת להצביע על הפוסט"
    said = party_round([("J1.1", "claude"), ("J1.2", "sharp")], fake,
                       lambda p, t: spoken.append(p))
    assert len(said) == 2 and spoken == ["J1.1", "J1.2"], (said, spoken)
    items = feed()
    assert items[0]["kind"] == "party", "החדש ביותר ראשון"
    assert len(items) == 4, items
    assert clear() == 4 and feed() == [], "הניקוי לא עבד"
    print("social demo OK")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        demo()
    else:
        for post in feed(20):
            print(f"[{post['persona']}@{post['panel']}] {post['text']}")
