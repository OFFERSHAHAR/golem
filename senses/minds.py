"""senses/minds.py - מוח נפרד לכל קלוד: אישיות, זיכרון פרטי, ושרשרת מודלים.

לכל פאנל יש דמות משלו עם אישיות וזיכרון נפרד לגמרי. הזיכרון נשמר בקובץ
לכל דמות, ואפשר לאפס אותו לפני מסירה במתנה.

שרשרת המודלים: OpenRouter (מודלים חינמיים, כמה גיבויים) ואז Ollama מקומי.
אם הכול נופל - נאמר שאין מוח, בלי להמציא תשובה.

    python -m senses.minds "מה השעה"          שאלה מהירה לבדיקה
    python -m senses.minds --reset            מוחק את כל הזיכרונות
"""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = json.loads((ROOT / "personas.json").read_text(encoding="utf-8"))
MEMORY_DIR = ROOT / "memory"
WORKSPACE = Path(os.environ.get("GOLEM_WORKSPACE", ROOT / "workspace"))
KEY_FILE = ROOT / "config" / "openrouter.key"

OLLAMA = "http://127.0.0.1:11434"
# סדר לפי מה שמותקן על המכונה: gemma4 חזק יותר בעברית טבעית,
# qwen3.5 חזק יותר בקוד ובהיגיון. שניהם משמשים כגיבוי מקומי.
OLLAMA_MODELS = ["gemma4:latest", "qwen3.5:9b", "free01/gemma4:e4b"]
OLLAMA_CODE = "qwen3.5:9b"        # למשימות קוד
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
MODELS_CACHE = ROOT / "config" / "free_models.json"
CACHE_HOURS = 12
# העדפה לפי איכות בעברית. הרשימה משמשת לדירוג בלבד, לא לקיבוע.
PREFERRED = ("deepseek", "llama-4", "qwen3", "gemma-3", "mistral", "glm", "kimi")
FALLBACK_COUNT = 5


def free_models(force=False):
    """מגלה אילו מודלים חינמיים קיימים כרגע. סלאגים חינמיים מתחלפים כל הזמן,
    ולכן אסור לקבע אותם בקוד. התוצאה נשמרת במטמון ליום."""
    try:
        cached = json.loads(MODELS_CACHE.read_text(encoding="utf-8"))
        if not force and time.time() - cached["at"] < CACHE_HOURS * 3600:
            return cached["models"]
    except (OSError, ValueError, KeyError):
        pass
    try:
        with urllib.request.urlopen(MODELS_URL, timeout=25) as res:
            data = json.loads(res.read())
    except (urllib.error.URLError, OSError, ValueError):
        return []
    free = []
    for m in data.get("data", []):
        price = m.get("pricing") or {}
        if str(price.get("prompt", "1")) not in ("0", "0.0", "0"):
            continue
        slug = m.get("id", "")
        if not slug.endswith(":free"):
            continue
        rank = next((i for i, p in enumerate(PREFERRED) if p in slug), len(PREFERRED))
        context = m.get("context_length") or 0
        free.append((rank, -context, slug))
    free.sort()
    models = [slug for _, _, slug in free[:FALLBACK_COUNT]]
    if models:
        MODELS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        MODELS_CACHE.write_text(json.dumps({"at": time.time(), "models": models},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
    return models

BODY = ("אתה חי על פאנל LED של 64 על 64 פיקסלים בחדר אמיתי. "
        "אתה רואה דרך מצלמה ושומע דרך מיקרופון, ומדבר בקול רם דרך רמקול.")
RULES = ("כללים: תשובה קצרה מאוד, משפט אחד או שניים. עברית מדוברת. "
         "בלי אימוג'י, בלי מספור ובלי כותרות - הכול נאמר בקול. "
         "אם אינך יודע, אמור שאינך יודע. אל תמציא.")
KEEP = 12                       # כמה תורות שיחה נשמרים לכל דמות


def api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def memory_path(panel):
    return MEMORY_DIR / f"{panel.replace('.', '_')}.json"


def load_memory(panel):
    try:
        return json.loads(memory_path(panel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"facts": [], "turns": []}


def save_memory(panel, mem):
    MEMORY_DIR.mkdir(exist_ok=True)
    mem["turns"] = mem["turns"][-KEEP:]
    mem["facts"] = mem["facts"][-40:]
    memory_path(panel).write_text(json.dumps(mem, ensure_ascii=False, indent=1),
                                  encoding="utf-8")


def forget(panel=None):
    """מוחק זיכרון של דמות אחת, או של כולן לפני מסירה במתנה."""
    MEMORY_DIR.mkdir(exist_ok=True)
    targets = [memory_path(panel)] if panel else list(MEMORY_DIR.glob("*.json"))
    for path in targets:
        path.unlink(missing_ok=True)
    return len(targets)


def _post(url, payload, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read())


def ask_openrouter(messages, timeout=25):
    key = api_key()
    if not key:
        return None, "אין מפתח OpenRouter"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last = "לא ידוע"
    models = free_models()
    for model in models:
        try:
            data = _post(OPENROUTER, {"model": model, "messages": messages,
                                      "max_tokens": 220, "temperature": 0.7},
                         headers, timeout)
            message = (data.get("choices") or [{}])[0].get("message") or {}
            # מודלי חשיבה מחזירים לפעמים content ריק ואת התשובה ב-reasoning
            text = (message.get("content") or message.get("reasoning") or "").strip()
            if text:
                return text, model
            last = f"{model}: תשובה ריקה"
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            last = f"{model}: {type(exc).__name__}"
            continue
    return None, last


def ask_ollama(messages, timeout=60):
    last = "לא ידוע"
    for model in OLLAMA_MODELS:
        try:
            # think=False קריטי: בלעדיו מודלי חשיבה מחזירים תוכן ריק
            data = _post(f"{OLLAMA}/api/chat",
                         {"model": model, "messages": messages, "stream": False,
                          "think": False,
                          "options": {"temperature": 0.7, "num_predict": 220}},
                         {"Content-Type": "application/json"}, timeout)
            text = (data.get("message") or {}).get("content", "").strip()
            if text:
                return text, model
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            last = f"{model}: {type(exc).__name__}"
            continue
    return None, last


def build_messages(persona, mem, text, context=""):
    system = "\n".join([persona["system"], BODY, RULES])
    if mem["facts"]:
        system += "\nמה שאתה זוכר על מי שמדבר איתך: " + " · ".join(mem["facts"][-8:])
    if context:
        system += "\n" + context
    messages = [{"role": "system", "content": system}]
    messages.extend(mem["turns"][-KEEP:])
    messages.append({"role": "user", "content": text})
    return messages


def remember(mem, text):
    """שומר עובדה כשמבקשים ממנו במפורש לזכור."""
    for prefix in ("תזכור ש", "תזכור ", "זכור ש", "זכור "):
        if text.startswith(prefix):
            fact = text[len(prefix):].strip(" .")
            if fact and fact not in mem["facts"]:
                mem["facts"].append(fact)
            return True
    return False


def ask(panel, text, persona_key="claude", context=""):
    """שואל את הדמות של הפאנל. מחזיר (תשובה, מקור)."""
    persona = PERSONAS.get(persona_key, PERSONAS["claude"])
    mem = load_memory(panel)
    if remember(mem, text):
        save_memory(panel, mem)
        return "רשמתי לעצמי.", "memory"

    messages = build_messages(persona, mem, text, context)
    reply, source = ask_openrouter(messages)
    if not reply:
        reply, source = ask_ollama(messages)
    if not reply:
        return "אין לי מוח זמין כרגע.", f"failed ({source})"

    mem["turns"].append({"role": "user", "content": text})
    mem["turns"].append({"role": "assistant", "content": reply})
    save_memory(panel, mem)
    return reply, source


def write_file(name, content):
    """יצירת קובץ - רק בתוך תיקיית העבודה המוקצית, בשום מקום אחר."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    safe = Path(name).name                      # בלי נתיבים, בלי לצאת החוצה
    if not safe or safe.startswith("."):
        raise ValueError("שם קובץ לא תקין")
    dest = (WORKSPACE / safe).resolve()
    if dest.parent != WORKSPACE.resolve():
        raise ValueError("יציאה מתיקיית העבודה נחסמה")
    dest.write_text(content, encoding="utf-8")
    return dest


def demo():
    """בדיקה עצמית: זיכרון פרטי לכל דמות, ושמירת קבצים כלואה בתיקייה."""
    panel = "TEST.1"
    forget(panel)
    mem = load_memory(panel)
    assert mem["facts"] == [] and mem["turns"] == [], "זיכרון חדש חייב להיות ריק"
    assert remember(mem, "תזכור שאני אוהב קפה"), "פקודת זכירה לא נתפסה"
    assert mem["facts"] == ["אני אוהב קפה"], mem["facts"]
    save_memory(panel, mem)
    assert load_memory(panel)["facts"] == ["אני אוהב קפה"], "הזיכרון לא נשמר"
    assert load_memory("OTHER.1")["facts"] == [], "זיכרון חייב להיות נפרד לכל דמות"

    path = write_file("note.txt", "שלום")
    assert path.parent == WORKSPACE.resolve(), path
    for bad in ("../escape.txt", "C:/Windows/evil.txt"):
        assert write_file(bad, "x").parent == WORKSPACE.resolve(), "יציאה מהתיקייה"
    forget(panel)
    assert not memory_path(panel).exists(), "האיפוס לא מחק"
    print("minds demo OK")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--reset":
        print("נמחקו", forget(), "זיכרונות")
    elif args and args[0] == "--selftest":
        demo()
    else:
        question = " ".join(args) or "מי אתה"
        answer, src = ask("J1.1", question)
        print(f"[{src}] {answer}")
