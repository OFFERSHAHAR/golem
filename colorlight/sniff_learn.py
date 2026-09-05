"""
colorlight/sniff_learn.py — הכלי שמסיר את כל אי-הוודאות מהפרויקט.

מריצים אותו, נותנים ל-LEDVISION להציג תמונה 5 שניות, והוא מדפיס בדיוק
מה הכרטיס מקבל: איזה MAC, אילו סוגי פריימים, מה המבנה של כל שורה.
משם ממלאים את הקבועים ב-driver.py ואפשר לזרוק את LEDVISION.

    python -m colorlight.sniff_learn --iface "Ethernet 2" --seconds 5
"""
import argparse
import collections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True, help='שם הממשק. הרץ driver.py כדי לראות רשימה')
    ap.add_argument("--seconds", type=int, default=5)
    ap.add_argument("--pcap", default="colorlight/capture_reference.pcap")
    args = ap.parse_args()

    from scapy.all import sniff, wrpcap, Ether, Raw

    print(f"מקליט {args.seconds} שניות על {args.iface} — עכשיו תן ל-LEDVISION להציג תמונה…")
    pkts = sniff(iface=args.iface, timeout=args.seconds, store=True)
    wrpcap(args.pcap, pkts)

    types = collections.Counter()
    dsts = collections.Counter()
    sample = {}
    for p in pkts:
        if Ether not in p:
            continue
        t = p[Ether].type
        types[t] += 1
        dsts[p[Ether].dst] += 1
        if t not in sample and Raw in p:
            sample[t] = bytes(p[Raw].load)

    print(f"\nנתפסו {len(pkts)} פריימים · נשמר ב-{args.pcap}\n")
    print("--- כתובות יעד ---")
    for mac, n in dsts.most_common(5):
        print(f"  {mac}   {n}")
    print("\n--- סוגי פריימים ---")
    for t, n in sorted(types.items()):
        row = "  ← נתוני שורה" if 0x5500 <= t <= 0x55FF else ""
        print(f"  0x{t:04X}   {n:>6} פריימים{row}")
        s = sample.get(t)
        if s:
            print(f"      אורך {len(s)}  |  16 בתים ראשונים: {s[:16].hex(' ')}")

    rows = sorted(t for t in types if 0x5500 <= t <= 0x55FF)
    if rows:
        print(f"\nטווח שורות: 0x{rows[0]:04X} … 0x{rows[-1]:04X}  ({len(rows)} שורות)")
        print("→ אם מספר השורות שווה לגובה הקיר, המבנה שב-driver.py נכון עקרונית.")
    print("\nהצעד הבא: להעתיק את ה-MAC למעלה אל dst_mac ב-config/devices.yaml,")
    print("ולהשוות את 16 הבתים הראשונים של פריים שורה למבנה ב-driver.send_frame.")


if __name__ == "__main__":
    main()
