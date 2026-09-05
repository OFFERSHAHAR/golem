"""senses/hearing.py - תמלול מקומי. faster-whisper, בלי אינטרנט ובלי ענן.

המודל נטען פעם אחת בלבד ונשאר בזיכרון, אחרת כל משפט עולה כמה שניות של טעינה.

    python -m senses.hearing file.wav      תמלול קובץ
    python -m senses.hearing --selftest    בדיקה עצמית מקצה לקצה
"""
import os
import threading

MODEL_NAME = os.environ.get("GOLEM_STT_MODEL", "small")
LANGUAGE = "he"
_model = None
_lock = threading.Lock()


def model():
    """טוען את המודל פעם אחת. הקריאה הראשונה מורידה אותו ולוקחת זמן."""
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            try:                                  # GPU אם יש, אחרת CPU
                _model = WhisperModel(MODEL_NAME, device="cuda", compute_type="int8_float16")
            except Exception:
                _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def _run(path):
    segments, _info = model().transcribe(str(path), language=LANGUAGE,
                                         vad_filter=True, beam_size=1)
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe(path):
    """מחזיר את הטקסט שנשמע בקובץ. מחרוזת ריקה אם לא נשמע כלום.
    אם ה-GPU חסר ספריות CUDA, עובר ל-CPU פעם אחת ונשאר שם."""
    global _model
    try:
        return _run(path)
    except RuntimeError as exc:
        if "cublas" not in str(exc).lower() and "cuda" not in str(exc).lower():
            raise
        print("GPU לא זמין לתמלול, עובר ל-CPU:", exc, flush=True)
        from faster_whisper import WhisperModel
        with _lock:
            _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
        return _run(path)


def demo():
    """בדיקה עצמית: מייצרים דיבור עברי, ובודקים שהוא חוזר כטקסט."""
    import tempfile
    from pathlib import Path
    import soundfile as sf
    from senses import voice

    sentence = "שלום קלוד מה שלומך"
    data, rate = voice.synth_offline(sentence)
    wav = Path(tempfile.gettempdir()) / "golem_hear_test.wav"
    sf.write(wav, data, rate)
    heard = transcribe(wav)
    print("נאמר: ", sentence)
    print("נשמע: ", heard)
    assert heard, "התמלול חזר ריק"
    assert any(word in heard for word in ("שלום", "קלוד", "שלומ")), heard
    print("hearing demo OK")


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--selftest":
        demo()
    elif args:
        print(transcribe(args[0]))
    else:
        print(__doc__)
