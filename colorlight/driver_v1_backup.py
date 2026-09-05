"""
colorlight/driver.py — שולח פריימים גולמיים בשכבה 2 ישירות ל-5A-75E.
בלי כרטיס שליחה, בלי LEDVISION.

Windows: צריך Npcap מותקן במצב "WinPcap API compatible".
    pip install scapy

⚠️ הקבועים בסעיף PROTOCOL הם נקודת פתיחה מפוענחת מ-5A-75B.
   לפני שסומכים עליהם — להריץ colorlight/sniff_learn.py ולאמת מול הלכידה האמיתית שלך.
"""
import struct
import numpy as np

# ---------------- PROTOCOL ----------------
ET_PING = 0x0107      # גילוי / latch — מסיים פריים ומורה לכרטיס להציג
ET_CONF = 0x0AFF      # בהירות והגדרות תצוגה
ET_ROW = 0x5500       # + מספר השורה → נתוני פיקסלים של שורה אחת
BCAST = "ff:ff:ff:ff:ff:ff"


class ColorlightWall:
    def __init__(self, iface, width=128, height=128,
                 dst_mac="11:22:33:44:55:66", brightness=40):
        from scapy.all import conf, Ether, Raw  # ייבוא עצל — מאפשר preview בלי scapy
        self._Ether, self._Raw = Ether, Raw
        self.sock = conf.L2socket(iface=iface)
        self.w, self.h, self.dst = width, height, dst_mac
        self.set_brightness(brightness)

    # ---------- שליטה ----------
    def set_brightness(self, pct: int):
        """0–100. להתחיל ב-25–40. רקע כתום מלא ב-100% מסנוור ומכפיל זרם."""
        pct = max(0, min(100, int(pct)))
        payload = bytes([pct, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]) + b"\x00" * 90
        self._send(ET_CONF, payload)

    def probe(self):
        """פריים גילוי. הרץ עם sniff_learn כדי לתפוס את התשובה ואת ה-MAC האמיתי."""
        self._send(ET_PING, b"\x00" * 98, dst=BCAST)

    # ---------- תמונה ----------
    def send_frame(self, rgb: np.ndarray):
        """rgb: מערך (h, w, 3) uint8. שולח שורה-שורה ואז latch."""
        assert rgb.shape == (self.h, self.w, 3), f"expected {(self.h, self.w, 3)}, got {rgb.shape}"
        rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
        for y in range(self.h):
            hdr = struct.pack(">HHHBB", y, 0, self.w, 0x08, 0x88)
            self._send(ET_ROW + y, hdr + rgb[y].tobytes())
        self._send(ET_PING, b"\x00" * 98)          # latch — הצג את מה שנשלח

    def blank(self):
        self.send_frame(np.zeros((self.h, self.w, 3), np.uint8))

    # ---------- פנימי ----------
    def _send(self, ethertype, payload, dst=None):
        pkt = self._Ether(dst=dst or self.dst, type=ethertype) / self._Raw(payload)
        self.sock.send(pkt)

    def close(self):
        try:
            self.blank()
        finally:
            self.sock.close()


def list_interfaces():
    """מדפיס את שמות הממשקים כפי ש-scapy רואה אותם — משם לוקחים את ה-iface."""
    from scapy.all import get_if_list, get_if_hwaddr
    for i in get_if_list():
        try:
            print(f"{i}\t{get_if_hwaddr(i)}")
        except Exception:
            print(i)


if __name__ == "__main__":
    list_interfaces()
