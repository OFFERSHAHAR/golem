"""parade.py - מצעד: מריץ על הקיר את כל ההבעות וכל התחפושות, אחת אחרי השנייה.

    python parade.py            # 3.5 שניות לכל אחת
    python parade.py --hold 6   # לאט יותר
    python parade.py --loop     # בלולאה עד Ctrl+C
"""
import argparse, json, socket, time

ADDR = ("127.0.0.1", 9999)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

SHOW = [
    ("neutral", "none", "רגיל"),
    ("happy", "none", "שמח"),
    ("wink", "none", "קורץ"),
    ("closed", "none", "עיניים עצומות"),
    ("cool", "none", "משקפי שמש"),
    ("surprised", "none", "מופתע"),
    ("sad", "none", "עצוב"),
    ("neutral", "chef", "שף"),
    ("happy", "wizard", "קוסם"),
    ("neutral", "cowboy", "בוקר"),
    ("happy", "cape", "גיבור על"),
    ("cool", "suit", "חליפה ועניבה"),
]


def send(**kw):
    sock.sendto(json.dumps(kw).encode(), ADDR)


ap = argparse.ArgumentParser()
ap.add_argument("--hold", type=float, default=3.5)
ap.add_argument("--loop", action="store_true")
a = ap.parse_args()

send(mode="critter", state="idle")
try:
    while True:
        for expr, hat, name in SHOW:
            print(f"  {name}   (expr={expr}, hat={hat})", flush=True)
            send(expr=expr, hat=hat, state="idle")
            time.sleep(a.hold)
        if not a.loop:
            break
finally:
    send(expr="neutral", hat="none", state="idle")
    print("סוף המצעד.")
