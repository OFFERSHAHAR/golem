"""
colorlight/driver.py - שולח פריימים גולמיים בשכבה 2 ישירות ל-5A-75E/75B.

  0x0700            פריים גילוי (270 בתים)
  0x0aXX            בהירות, XX = ערך הבהירות. 63 בתים.
  0x0107            פריים תצוגה/latch. 98 בתים. בית 21 בהירות, 22=0x05, 24-26 כיול RGB
  0x5500+(שורה>>8)  נתוני שורה: כותרת 7 בתים ואז BGR
                    [0] שורה [1..2] אופסט פיקסל [3..4] כמות [5]=0x08 [6]=0x80
שורה ארוכה מפוצלת לכמה חבילות לפי האופסט, שלא לחרוג מ-MTU.
"""
import numpy as np

ET_DETECT = 0x0700
ET_REPLY = 0x0805
ET_BRIGHT = 0x0A00
ET_DISPLAY = 0x0107
ET_ROW = 0x5500

DST_MAC = "11:22:33:44:55:66"
SRC_MAC = "22:22:33:44:55:66"
BCAST = "ff:ff:ff:ff:ff:ff"
CHUNK = 480          # פיקסלים לחבילה. 480*3+7 = 1447 בתים


class ColorlightWall:
    def __init__(self, iface, width=128, height=128,
                 dst_mac=DST_MAC, src_mac=SRC_MAC, brightness=40, bgr=True):
        from scapy.all import conf, Ether, Raw
        self._Ether, self._Raw = Ether, Raw
        self.sock = conf.L2socket(iface=iface)
        self.w, self.h = width, height
        self.dst, self.src = dst_mac, src_mac
        self.bgr = bgr
        self.brightness = max(0, min(100, int(brightness)))
        self.set_brightness(self.brightness)

    def set_brightness(self, pct):
        self.brightness = max(0, min(100, int(pct)))
        v = int(self.brightness * 255 / 100)
        self._send(ET_BRIGHT + v, bytes([v, v, 0xFF]) + b"\x00" * 60)

    def display(self):
        v = int(self.brightness * 255 / 100)
        p = bytearray(98)
        p[21] = v
        p[22] = 0x05
        p[24] = p[25] = p[26] = 0xFF
        self._send(ET_DISPLAY, bytes(p))

    def detect(self):
        self._send(ET_DETECT, b"\x00" * 270, dst=BCAST)

    def send_frame(self, rgb, rows=None):
        """שולח פריים מלא, או רק שורות נבחרות כשחלק מהיציאות כבויות."""
        assert rgb.shape == (self.h, self.w, 3), f"expected {(self.h, self.w, 3)}, got {rgb.shape}"
        data = np.ascontiguousarray(rgb, dtype=np.uint8)
        if self.bgr:
            data = data[:, :, ::-1]
        et_base = ET_ROW
        for y in range(self.h) if rows is None else rows:
            if not 0 <= y < self.h:
                continue
            row = data[y]
            off = 0
            while off < self.w:
                n = min(CHUNK, self.w - off)
                hdr = bytes([y & 0xFF,
                             (off >> 8) & 0xFF, off & 0xFF,
                             (n >> 8) & 0xFF, n & 0xFF,
                             0x08, 0x80])
                self._send(et_base + (y >> 8), hdr + row[off:off+n].tobytes())
                off += n
        self.display()

    def blank(self):
        self.send_frame(np.zeros((self.h, self.w, 3), np.uint8))

    def _send(self, ethertype, payload, dst=None):
        pkt = self._Ether(dst=dst or self.dst, src=self.src, type=ethertype) / self._Raw(payload)
        self.sock.send(pkt)

    def close(self):
        try:
            self.blank()
        finally:
            self.sock.close()


def list_interfaces():
    from scapy.all import get_if_list, get_if_hwaddr
    for i in get_if_list():
        try:
            print(f"{i}\t{get_if_hwaddr(i)}")
        except Exception:
            print(i)


if __name__ == "__main__":
    list_interfaces()
