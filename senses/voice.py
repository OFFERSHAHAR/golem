"""senses/voice.py - הקול. edge-tts בעברית, ומעטפת האודיו האמיתית מניעה את הפה."""
import asyncio
import io
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
import edge_tts

VOICE = "he-IL-AvriNeural"      # גברי. חלופה נשית: he-IL-HilaNeural


async def _stream(text, voice, rate, pitch):
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return buf


def synth(text, voice=VOICE, rate="+8%", pitch="+0Hz"):
    buf = asyncio.run(_stream(text, voice, rate, pitch))
    data, sr = sf.read(buf, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr


def synth_offline(text):
    """מנוע הדיבור המובנה של Windows. עובד בלי אינטרנט ובלי התקנה.
    ponytail: יוצא ל-PowerShell במקום להוסיף תלות ב-pywin32."""
    import subprocess, tempfile, os
    tmp = tempfile.gettempdir()
    wav = os.path.join(tmp, "golem_tts.wav")
    txt = os.path.join(tmp, "golem_tts.txt")
    ps1 = os.path.join(tmp, "golem_tts.ps1")
    # הטקסט עובר בקובץ UTF-8, לא בשורת הפקודה, אחרת העברית משתבשת
    with open(txt, "w", encoding="utf-8-sig") as fh:
        fh.write(text)
    script = (
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$he = $s.GetInstalledVoices() | Where-Object {"
        " $_.VoiceInfo.Culture.Name -like 'he*' -and $_.Enabled } | Select-Object -First 1\n"
        "if ($he) { $s.SelectVoice($he.VoiceInfo.Name) }\n"
        f"$t = Get-Content -Raw -Encoding UTF8 '{txt}'\n"
        f"$s.SetOutputToWaveFile('{wav}')\n"
        "$s.Speak($t)\n"
        "$s.Dispose()\n"
    )
    with open(ps1, "w", encoding="utf-8-sig") as fh:
        fh.write(script)
    # pwsh 7 רואה קולות שהגרסה הישנה לא רואה, למשל Microsoft Asaf בעברית
    last = None
    for shell in ("pwsh", "powershell"):
        try:
            subprocess.run([shell, "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-File", ps1],
                           check=True, capture_output=True, timeout=90)
        except (OSError, subprocess.SubprocessError) as exc:
            last = exc
            continue
        if os.path.getsize(wav) > 1000:      # 46 בתים = כותרת ריקה
            break
    else:
        raise RuntimeError(f"מנוע הדיבור המקומי לא ייצר קול: {last}")
    data, sr = sf.read(wav, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr


def say(text, on_amp=None, voice=VOICE, rate="+8%"):
    """מנגן ומדווח עוצמה בזמן אמת ל-on_amp(0..1). חוסם עד סוף הדיבור.
    מנסה קודם edge-tts (איכותי, דורש רשת), ונופל למנוע המקומי של Windows."""
    try:
        data, sr = synth(text, voice, rate)
    except Exception as e:
        print("TTS מקוון נכשל, עובר למנוע המקומי:", e)
        try:
            data, sr = synth_offline(text)
        except Exception as e2:
            print("גם המנוע המקומי נכשל:", e2)
            if on_amp:
                on_amp(0.0)
            return False

    win = int(sr * 0.045)
    peak = float(np.abs(data).max()) or 1.0
    sd.play(data, sr)
    t0, dur = time.time(), len(data) / sr
    while True:
        el = time.time() - t0
        if el >= dur:
            break
        seg = data[int(el * sr):int(el * sr) + win]
        if on_amp is not None and len(seg):
            rms = float(np.sqrt((seg ** 2).mean()))
            on_amp(min(1.0, (rms / peak) * 3.2))
        time.sleep(0.045)
    sd.wait()
    if on_amp:
        on_amp(0.0)
    return True


if __name__ == "__main__":
    import sys
    txt = " ".join(sys.argv[1:]) or "שלום, אני גולם. אני חי על הקיר."
    print("מדבר:", txt)
    say(txt)
    print("ok")


def demo():
    """בדיקה עצמית למנוע המקומי: חייב להחזיר אודיו אמיתי, לא כותרת ריקה."""
    data, sr = synth_offline("בדיקה")
    assert sr > 8000, f"קצב דגימה לא סביר: {sr}"
    assert len(data) > 1000, "מנוע הדיבור המקומי החזיר קובץ ריק"
    print(f"voice demo OK  {len(data)/sr:.2f}s")
