"""גילוי כרטיס הקולורלייט להתקנה במחשב חדש.

מנסה קודם גילוי אוטומטי (פריים 0x0700 ותשובת 0x0805). אם הכרטיס לא עונה,
עובר לשיטה הידנית: מדליק את הקיר בלבן על כל כרטיס רשת בתורו ושואל איפה נדלק.
התוצאה נשמרת ב-config/devices.yaml.

    python setup_wall.py            התקנה
    python setup_wall.py --list     רק להציג כרטיסי רשת
"""
import argparse, threading, time
from pathlib import Path

import numpy as np

from colorlight.driver import ColorlightWall, ET_REPLY, DST_MAC
import wall_map as WM

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "devices.yaml"
SKIP = ("loopback", "bluetooth", "vmware", "virtualbox", "wan miniport", "wi-fi direct")


def interfaces():
    from scapy.all import get_working_ifaces
    out = []
    for i in get_working_ifaces():
        label = f"{getattr(i, 'description', '')} {getattr(i, 'name', '')}".lower()
        if any(s in label for s in SKIP):
            continue
        out.append(i)
    return out


def label(iface):
    return getattr(iface, "description", None) or str(iface.name)


def probe(iface, seconds=3.0):
    """גילוי אוטומטי. מחזיר MAC אם הכרטיס ענה, אחרת None."""
    from scapy.all import sniff, Ether
    hit = []

    def on_pkt(p):
        if Ether in p and p[Ether].type == ET_REPLY:
            hit.append(p[Ether].src)

    th = threading.Thread(
        target=lambda: sniff(iface=iface, prn=on_pkt, timeout=seconds, store=False),
        daemon=True)
    th.start()
    time.sleep(0.6)
    try:
        wall = ColorlightWall(iface=iface, brightness=30)
    except Exception:
        return None
    try:
        for _ in range(4):
            wall.detect()
            time.sleep(0.3)
            if hit:
                break
    finally:
        try:
            wall.sock.close()
        except Exception:
            pass
    th.join()
    return hit[0] if hit else None


def flash(iface, seconds=3.0):
    """מדליק את הקיר בלבן על הממשק הזה."""
    try:
        wall = ColorlightWall(iface=iface, width=WM.CANVAS_W, height=WM.CANVAS_H,
                              brightness=45)
    except Exception:
        return False
    frame = np.full((WM.CANVAS_H, WM.CANVAS_W, 3), 255, np.uint8)
    try:
        t0 = time.monotonic()
        while time.monotonic() - t0 < seconds:
            wall.send_frame(frame)
            time.sleep(0.05)
    except Exception:
        return False
    finally:
        try:
            wall.sock.close()
        except Exception:
            pass
    return True


def walk(ifs, seconds):
    """מדליק כל ממשק בתורו ושואל את המשתמש איפה הקיר נדלק."""
    print()
    print("עכשיו כל כרטיס רשת יידלק בתורו למשך כמה שניות.")
    print("תסתכל על הקיר וזכור באיזה מספר הוא נדלק.")
    print()
    for n, i in enumerate(ifs, 1):
        print(f"  [{n}] {label(i)} - מדליק...", flush=True)
        flash(i.name, seconds)
    while True:
        ans = input(f"באיזה מספר הקיר נדלק? (1-{len(ifs)}, 0 אם אף אחד): ").strip()
        if ans.isdigit() and 0 <= int(ans) <= len(ifs):
            return int(ans)
        print("מספר לא תקין.")


def write_config(iface_name, mac):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(
        "# נכתב אוטומטית על ידי setup_wall.py\n"
        f"iface: '{iface_name}'\n"
        f"card_mac: '{mac}'\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--auto-only", action="store_true", help="בלי שאלות למשתמש")
    a = ap.parse_args()

    ifs = interfaces()
    if a.list:
        for i in ifs:
            print(f"{label(i)}\n    {i.name}")
        return 0
    if not ifs:
        print("לא נמצא אף כרטיס רשת מתאים. ודא ש-Npcap מותקן.")
        return 2

    print(f"סורק {len(ifs)} כרטיסי רשת...")
    for i in ifs:
        print(f"  בודק: {label(i)}")
        mac = probe(i.name, a.seconds)
        if mac:
            write_config(str(i.name), mac)
            print(f"נמצא אוטומטית: {label(i)}  MAC {mac}")
            print(f"נשמר ב: {CONFIG}")
            return 0

    if a.auto_only:
        print("גילוי אוטומטי נכשל.")
        return 1

    choice = walk(ifs, a.seconds)
    if choice:
        chosen = ifs[choice - 1]
        write_config(str(chosen.name), DST_MAC)
        print(f"נקבע: {label(chosen)}")
        print(f"נשמר ב: {CONFIG}")
        return 0

    print("הקיר לא נדלק על אף כרטיס רשת. בדוק:")
    print("  1. הכרטיס מחובר לחשמל ונוריות הרשת דולקות")
    print("  2. כבל הרשת מחובר ישירות מהמחשב לכרטיס")
    print("  3. Npcap מותקן במצב תאימות WinPcap")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
