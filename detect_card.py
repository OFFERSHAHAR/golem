"""detect_card.py - שולח פריים גילוי 0x0700 ומאזין לתשובת הכרטיס 0x0805."""
import argparse, sys, os, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall, ET_REPLY

ap = argparse.ArgumentParser()
ap.add_argument("--iface", required=True)
ap.add_argument("--seconds", type=int, default=8)
a = ap.parse_args()

from scapy.all import sniff, Ether, Raw

found = []

def on_pkt(p):
    if Ether not in p:
        return
    t = p[Ether].type
    if t in (0x0800, 0x0806, 0x86DD, 0x88CC):
        return
    payload = bytes(p[Raw].load) if Raw in p else b""
    print(f"  <<< ethertype 0x{t:04X}  src={p[Ether].src}  dst={p[Ether].dst}  len={len(payload)}")
    print(f"      {payload[:32].hex(' ')}")
    found.append(p)

th = threading.Thread(target=lambda: sniff(iface=a.iface, prn=on_pkt,
                                           timeout=a.seconds, store=False), daemon=True)
th.start()
time.sleep(1)

wall = ColorlightWall(iface=a.iface, brightness=30)
print("שולח פריימי גילוי 0x0700...")
for _ in range(5):
    wall.detect()
    time.sleep(0.4)
th.join()
wall.sock.close()

if found:
    print(f"\nהכרטיס חי! נתפסו {len(found)} תשובות.")
else:
    print("\nשום תשובה. הכרטיס לא עונה לפריים הגילוי בפורמט הזה.")
