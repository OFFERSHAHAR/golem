"""mic_check.py - בודק איזה מיקרופון באמת שומע אותך. דבר ברצף בזמן שזה רץ."""
import sys, time
import numpy as np
import sounddevice as sd

CANDS = [int(x) for x in sys.argv[1:]] or [1, 2, 3, 4, 5]
SECS = 4.0

print("דבר ברציפות עכשיו...\n", flush=True)
for dev in CANDS:
    try:
        info = sd.query_devices(dev)
    except Exception as e:
        print(f"{dev}: לא קיים"); continue
    if info["max_input_channels"] < 1:
        continue
    peaks = []
    try:
        with sd.InputStream(device=dev, channels=1, samplerate=16000,
                            blocksize=480, dtype="float32") as st:
            t0 = time.time()
            while time.time() - t0 < SECS:
                blk, _ = st.read(480)
                peaks.append(float(np.abs(blk).max()))
    except Exception as e:
        print(f"{dev:3d}  {info['name'][:42]:44s} שגיאה: {e}")
        continue
    peak = max(peaks) if peaks else 0
    rms = float(np.mean(peaks)) if peaks else 0
    bar = "#" * int(min(40, peak * 80))
    verdict = "שומע!" if peak > 0.03 else ("חלש" if peak > 0.008 else "שקט")
    print(f"{dev:3d}  {info['name'][:42]:44s} peak={peak:.4f} avg={rms:.4f} {verdict:6s} {bar}", flush=True)
print("\nבחר את זה עם peak הכי גבוה.")
