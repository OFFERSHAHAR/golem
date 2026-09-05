"""מיפוי יציאות HUB75 של 5A-75B/5A-75E, כפי שנמדד פיזית על הקיר.

הכלל שנמדד (04.09.2026, בדיקות probe_rows.py):
  * כל יציאה Jn מקבלת רצועה של 64 שורות בקנבס: שורות (n-1)*64 עד (n-1)*64+63.
  * בתוך הרצועה, השרשרת נקראת מימין לשמאל: הפאנל הראשון בשרשרת מקבל את
    עמודות 128..191, הפאנל השני את 64..127, וכן הלאה כל 64 שמאלה.
  * עמודות 0..63 ו-192..255 אינן מגיעות לאף פאנל.
"""
import numpy as np

X_OFF = 128            # עמודת ההתחלה של הפאנל הראשון בשרשרת
PANEL = 64
PORTS = tuple(f"J{i}" for i in range(1, 9))
PORT_COUNT = len(PORTS)
PORT_WIDTHS = (128, 128, 64, 64, 64, 64, 64, 64)
PORT_OFFSETS = tuple(sum(PORT_WIDTHS[:i]) for i in range(PORT_COUNT))

CANVAS_W, CANVAS_H = 256, PANEL * PORT_COUNT
PHYS_W, PHYS_H = sum(PORT_WIDTHS), PANEL
PORT_LAYOUT = {name: {"x": X_OFF, "y": i * PANEL, "w": PORT_WIDTHS[i],
                      "h": PANEL, "src_x": PORT_OFFSETS[i]}
               for i, name in enumerate(PORTS)}


# רשימת הפאנלים הפיזיים: כל אחד ניתן לכתובת בנפרד, "J1.1", "J1.2", ...
PANELS = tuple(
    {"name": f"{PORTS[i]}.{k+1}", "port": PORTS[i], "port_index": i, "chain": k,
     "src_x": PORT_OFFSETS[i] + k * PANEL, "y": i * PANEL}
    for i in range(PORT_COUNT) for k in range(PORT_WIDTHS[i] // PANEL)
)
PANEL_INDEX = {p["name"]: n for n, p in enumerate(PANELS)}


def canvas_x(panel_index):
    """עמודת הקנבס של הפאנל ה-k בשרשרת (0 = הראשון)."""
    return X_OFF - panel_index * PANEL


def to_canvas(phys):
    """phys: (PHYS_H, PHYS_W, 3) uint8 -> קנבס לשליחה לכרטיס."""
    assert phys.shape == (PHYS_H, PHYS_W, 3), phys.shape
    c = np.zeros((CANVAS_H, CANVAS_W, 3), np.uint8)
    for i, width in enumerate(PORT_WIDTHS):
        y, src = i * PANEL, PORT_OFFSETS[i]
        for k in range(width // PANEL):                 # פאנל בתוך השרשרת
            x = canvas_x(k)
            if 0 <= x <= CANVAS_W - PANEL:
                c[y:y+PANEL, x:x+PANEL] = phys[:, src + k*PANEL: src + (k+1)*PANEL]
    return c


def demo():
    """בדיקה עצמית: כל פאנל בשרשרת נוחת בעמודה הנכונה, בסדר הפוך."""
    phys = np.zeros((PHYS_H, PHYS_W, 3), np.uint8)
    phys[:, 0:PANEL] = 10          # פאנל ראשון של J1
    phys[:, PANEL:2*PANEL] = 20    # פאנל שני של J1
    c = to_canvas(phys)
    assert c[0, 128, 0] == 10, "הפאנל הראשון חייב לשבת ב-128"
    assert c[0, 64, 0] == 20, "הפאנל השני חייב לשבת ב-64"
    assert c[0, 0, 0] == 0 and c[0, 192, 0] == 0, "0..63 ו-192..255 נשארים ריקים"
    assert c[PANEL, 128, 0] == 0, "רצועת J2 לא מושפעת מ-J1"
    print("wall_map demo OK")


if __name__ == "__main__":
    demo()
