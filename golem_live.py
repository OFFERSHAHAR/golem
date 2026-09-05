"""golem_live.py - היצור חי על הקיר.

    python golem_live.py                    # קלוד הפיקסלי, וכשאין פעילות הוא נהיה ניצוץ
    python golem_live.py --mode spark       # להתחיל כניצוץ
    python golem_live.py --j2 spark          # J1 קלוד, J2 ניצוץ עצמאי
    python golem_live.py --idle 90          # אחרי כמה שניות בלי פעילות חוזרים לניצוץ
    python golem_live.py --idle 0           # לא לחזור לניצוץ אף פעם

UDP 127.0.0.1:9999, JSON:
    {"state":"speak","amp":0.8}
    {"mode":"critter"}   critter | spark | face
    {"j2_mode":"spark"}  spark | critter | face | off
    {"emote":"pulse"}
"""
import argparse, json, socket, sys, os, time
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from colorlight.driver import ColorlightWall
from face.creature import Creature
import wall_map as WM

def _device_config():
    """קורא iface ו-MAC מ-config/devices.yaml. פרסור שטוח, בלי תלות בספריית yaml."""
    cfg = {"iface": r"\Device\NPF_{BBD1BCF9-F30B-4F62-B409-187618AD437B}",
           "dst_mac": "11:22:33:44:55:66"}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "config", "devices.yaml")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key, value = key.strip(), value.strip().strip("'").strip('"')
                if not value:
                    continue
                if key == "iface":
                    cfg["iface"] = value
                elif key in ("dst_mac", "card_mac"):
                    cfg["dst_mac"] = value
    except OSError:
        pass
    return cfg


DEV = _device_config()

ap = argparse.ArgumentParser()
ap.add_argument("--iface", default=DEV["iface"])
ap.add_argument("--mac", default=DEV["dst_mac"])
ap.add_argument("--brightness", type=int, default=38)
ap.add_argument("--fps", type=int, default=45)
ap.add_argument("--size", type=int, default=64)
ap.add_argument("--zoom", type=float, default=1.0)
ap.add_argument("--mode", choices=["critter", "spark", "face"], default="critter")
ap.add_argument("--j2", choices=["critter", "spark", "face", "off"], default="spark")
ap.add_argument("--idle", type=float, default=75, help="שניות עד שהוא חוזר לניצוץ. 0 = לעולם לא")
ap.add_argument("--xpos", choices=["left", "right", "center"], default="left")
ap.add_argument("--drop", type=float, default=5.0,
                help="להזיז את הדמות למטה, באחוזים מגובה הפאנל")
ap.add_argument("--bob", type=int, default=2,
                help="עוצמת הנשימה בפיקסלים (על קנבס 128). 0 = עומד לגמרי")
ap.add_argument("--shot", default=None)
ap.add_argument("--seconds", type=float, default=0)
a = ap.parse_args()

crt = Creature(mode=a.mode, brightness=0.85)
crt.r["critter"].bob = max(0, a.bob)
port_renderers = [crt] + [None] * (WM.PORT_COUNT - 1)
port_visible = [True] + [False] * (WM.PORT_COUNT - 1)
port_images = [None] * WM.PORT_COUNT
dirty_ports = set(range(WM.PORT_COUNT))  # פריים ראשון מאתחל ומנקה כל יציאה
if a.j2 != "off":
    port_renderers[1] = Creature(mode=a.j2, brightness=0.85)
    port_visible[1] = True


paint = np.zeros((WM.PHYS_H, WM.PHYS_W, 3), np.float32)   # שכבת הקסם
PAINT_FADE = 0.94         # כמה מהר משיכת המכחול דוהה


def paint_dab(spec):
    """נקודת צבע על הקיר. spec: [x 0..1, y 0..1, עוצמה 0..1, גוון 0..360]."""
    try:
        nx, ny, power, hue = (list(spec) + [0, 0, 0.6, 30])[:4]
    except TypeError:
        return
    cx = int(float(nx) * WM.PHYS_W)
    cy = int(float(ny) * WM.PHYS_H)
    radius = max(2, int(2 + float(power) * 7))
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((float(hue) % 360) / 360.0, 0.85, 1.0)
    color = np.array([r, g, b], np.float32) * (120 + 135 * min(1.0, float(power)))
    y0, y1 = max(0, cy - radius), min(WM.PHYS_H, cy + radius + 1)
    x0, x1 = max(0, cx - radius), min(WM.PHYS_W, cx + radius + 1)
    if y1 <= y0 or x1 <= x0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    fall = np.clip(1.0 - np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2) / radius, 0, 1)
    paint[y0:y1, x0:x1] = np.maximum(paint[y0:y1, x0:x1], fall[..., None] * color)


panel_renderers = {}      # "J1.2" -> Creature
panel_images = {}         # "J1.2" -> [(frame, seconds), ...]  פריים אחד = תמונה סטטית
panel_clock = {}          # "J1.2" -> (index, started_at)


def load_media(path):
    """טוען תמונה או אנימציה ומתאים אותה ל-64x64. מחזיר רשימת (פריים, שניות)."""
    frames = []
    with Image.open(path) as src:
        count = getattr(src, "n_frames", 1)
        for i in range(min(count, 240)):          # ponytail: תקרה של 240 פריימים
            src.seek(i)
            frame = src.convert("RGB").resize((WM.PANEL, WM.PANEL), Image.LANCZOS)
            delay = max(0.04, src.info.get("duration", 80) / 1000.0)
            frames.append((frame.copy(), delay))
    return frames


def current_frame(name):
    """הפריים שצריך להיות מוצג עכשיו, לפי שעון האנימציה של הפאנל."""
    frames = panel_images.get(name)
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0][0]
    index, started = panel_clock.get(name, (0, time.monotonic()))
    if time.monotonic() - started >= frames[index][1]:
        index = (index + 1) % len(frames)
        started = time.monotonic()
    panel_clock[name] = (index, started)
    return frames[index][0]


def set_panel(name, mode=None, path=None):
    """שליטה נפרדת בפאנל בודד בתוך שרשרת. גובר על תוכן היציאה."""
    if name not in WM.PANEL_INDEX:
        return
    slot = WM.PANELS[WM.PANEL_INDEX[name]]
    dirty_ports.add(slot["port_index"])
    if path:
        panel_images[name] = load_media(path)
        panel_clock[name] = (0, time.monotonic())
        panel_renderers.pop(name, None)
        return
    panel_images.pop(name, None)
    panel_clock.pop(name, None)
    if mode == "off":
        panel_renderers[name] = None
    elif mode in ("critter", "spark", "face"):
        panel_renderers[name] = Creature(mode=mode, brightness=0.85)
    elif mode == "clear":                       # חזרה לתוכן של היציאה
        panel_renderers.pop(name, None)


def set_port_mode(index, mode):
    if not 0 <= index < WM.PORT_COUNT:
        return
    port_images[index] = None
    dirty_ports.add(index)
    if mode == "off":
        port_visible[index] = False
        return
    if mode not in ("critter", "spark", "face"):
        return
    port_visible[index] = True
    if port_renderers[index] is None:
        port_renderers[index] = Creature(mode=mode, brightness=0.85)
    else:
        port_renderers[index].morph(mode)


def set_port_image(index, path):
    if not 0 <= index < WM.PORT_COUNT:
        return
    with Image.open(path) as source:
        size = (WM.PORT_WIDTHS[index], WM.PANEL)
        port_images[index] = source.convert("RGB").resize(size, Image.LANCZOS).copy()
    port_visible[index] = True
    dirty_ports.add(index)


def port_label(index):
    if not port_visible[index]:
        return "off"
    if port_images[index] is not None:
        return "custom"
    renderer = port_renderers[index]
    return renderer.mode if renderer else "off"


wall = ColorlightWall(iface=a.iface, width=WM.CANVAS_W, height=WM.CANVAS_H,
                      dst_mac=a.mac, brightness=a.brightness)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.bind(("127.0.0.1", 9999))
    sock.setblocking(False)
except OSError:
    sock = None

S = min(a.size, WM.PHYS_H)
Z = max(int(round(S * a.zoom)), S)
crop = (Z - S) // 2
x0 = (64 - S) // 2
x_cur = float(x0)          # מיקום הדמות על הרצועה הפיזית
x_target = float(x0)
y0 = (WM.PHYS_H - S) // 2 + int(round(WM.PHYS_H * a.drop / 100.0))

cap = None
if a.shot:
    import cv2
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    for _ in range(15):
        cap.read(); time.sleep(0.04)

period = 1.0 / a.fps
t_start = last_cmd = time.monotonic()
frames, t_fps = 0, time.monotonic()
last_frame = None
awake_mode = a.mode if a.mode != "spark" else "critter"
print(f"קלוד חי · J1={a.mode} · J2={a.j2} · idle={a.idle}s · בהירות {a.brightness}%",
      flush=True)
try:
    while True:
        t0 = time.monotonic()
        if sock:
            cmd = None
            while True:
                try:
                    cmd, _ = sock.recvfrom(2048)
                except BlockingIOError:
                    break
            if cmd:
                try:
                    m = json.loads(cmd)
                    if m.get("shutdown"):
                        raise KeyboardInterrupt
                    if not m.get("passive"):        # מבט מהמצלמה לא מחשיב כפעילות
                        last_cmd = t0
                    if m.get("mode"):
                        awake_mode = m["mode"] if m["mode"] != "spark" else awake_mode
                        crt.morph(m["mode"])
                    elif crt.mode == "spark" and a.idle and not m.get("passive"):
                        crt.morph(awake_mode)          # מתעורר חזרה ליצור
                    port_name = m.get("port")
                    port_mode = m.get("port_mode")
                    if m.get("j2_mode"):
                        port_name, port_mode = "J2", m["j2_mode"]
                    if port_name in WM.PORTS and port_mode:
                        set_port_mode(WM.PORTS.index(port_name), port_mode)
                    panel = m.get("panel")
                    if panel:
                        set_panel(panel, mode=m.get("panel_mode"),
                                  path=m.get("panel_image"))
                    if m.get("brightness") is not None:
                        wall.brightness = max(5, min(100, int(m["brightness"])))
                        wall.set_brightness(wall.brightness)
                        dirty_ports.update(range(WM.PORT_COUNT))
                    if m.get("paint") is not None:      # מכחול הקסם מהמצלמה
                        paint_dab(m["paint"])
                    if m.get("paint_clear"):
                        paint[:] = 0
                    goto = m.get("goto")
                    if goto in WM.PANEL_INDEX:
                        x_target = float(WM.PANELS[WM.PANEL_INDEX[goto]]["src_x"]
                                         + (WM.PANEL - S) // 2)
                    elif goto in WM.PORTS:
                        g = WM.PORTS.index(goto)
                        x_target = float(WM.PORT_OFFSETS[g]
                                         + (WM.PORT_WIDTHS[g] - S) // 2)
                    if port_name in WM.PORTS and m.get("port_image"):
                        set_port_image(WM.PORTS.index(port_name), m["port_image"])
                    crt.set(state=m.get("state"), amp=m.get("amp"),
                            gaze=m.get("gaze"), emote=m.get("emote"),
                            expr=m.get("expr"), hat=m.get("hat"))
                    if port_renderers[1]:
                        port_renderers[1].set(state=m.get("j2_state"), amp=m.get("j2_amp"),
                                              gaze=m.get("j2_gaze"), emote=m.get("j2_emote"))
                except Exception as e:
                    print("פקודה לא תקינה:", e)

        # אין פעילות -> חוזר להיות ניצוץ ונרגע
        if a.idle and crt.mode != "spark" and t0 - last_cmd > a.idle:
            crt.set(state="idle", amp=0)
            crt.morph("spark")

        img = crt.render()
        if Z != 128 or crop:
            img = img.resize((Z, Z), Image.NEAREST if crt.mode == "critter" else Image.LANCZOS)
            if crop:
                img = img.crop((crop, crop, crop + S, crop + S))
        if img.size != (S, S):
            img = img.resize((S, S), Image.NEAREST if crt.mode == "critter" else Image.LANCZOS)

        phys = np.zeros((WM.PHYS_H, WM.PHYS_W, 3), np.uint8)
        arr = np.asarray(img, dtype=np.uint8)
        if port_images[0] is not None and port_visible[0]:
            phys[:, :WM.PORT_WIDTHS[0]] = np.asarray(port_images[0], dtype=np.uint8)
        for i in range(1, WM.PORT_COUNT):
            if not port_visible[i]:
                continue
            if port_images[i] is not None:
                panel = port_images[i]
            else:
                renderer = port_renderers[i]
                if renderer is None:
                    continue
                icon = renderer.render().resize(
                    (64, 64), Image.NEAREST if renderer.mode == "critter" else Image.LANCZOS)
                panel = Image.new("RGB", (WM.PORT_WIDTHS[i], WM.PANEL))
                panel.paste(icon, ((WM.PORT_WIDTHS[i] - 64) // 2, 0))
            x = WM.PORT_OFFSETS[i]
            phys[:, x:x+WM.PORT_WIDTHS[i]] = np.asarray(panel, dtype=np.uint8)
        for name, renderer in list(panel_renderers.items()) :
            slot = WM.PANELS[WM.PANEL_INDEX[name]]
            x = slot["src_x"]
            if renderer is None:
                phys[:, x:x+WM.PANEL] = 0
            else:
                phys[:, x:x+WM.PANEL] = np.asarray(
                    renderer.render().resize((WM.PANEL, WM.PANEL), Image.NEAREST),
                    dtype=np.uint8)
        for name in list(panel_images):
            frame = current_frame(name)
            if frame is None:
                continue
            x = WM.PANELS[WM.PANEL_INDEX[name]]["src_x"]
            phys[:, x:x+WM.PANEL] = np.asarray(frame, dtype=np.uint8)

        # ponytail: הדמות מצוירת אחרונה, ולכן היא יכולה לעבור בין היציאות
        x_cur += (x_target - x_cur) * 0.12
        x0 = int(round(x_cur))
        yy, hh = max(0, y0), min(S, WM.PHYS_H - max(0, y0))
        xs, xe = max(0, x0), min(WM.PHYS_W, x0 + S)
        if hh > 0 and xe > xs and port_visible[0]:
            phys[yy:yy+hh, xs:xe] = arr[max(0, -y0):max(0, -y0)+hh, xs-x0:xe-x0]
        if paint.any():                      # שכבת הקסם מעל הכול, ודוהה מעצמה
            paint *= PAINT_FADE
            paint[paint < 2] = 0
            phys[:] = np.maximum(phys, paint.astype(np.uint8))
        travel_ports = {i for i in range(WM.PORT_COUNT)
                        if WM.PORT_OFFSETS[i] < xe
                        and xs < WM.PORT_OFFSETS[i] + WM.PORT_WIDTHS[i]}
        dynamic_ports = {i for i, visible in enumerate(port_visible)
                         if visible and port_images[i] is None} | travel_ports
        dynamic_ports |= {WM.PANELS[WM.PANEL_INDEX[n]]["port_index"]
                          for n in panel_renderers if panel_renderers[n] is not None}
        dynamic_ports |= {WM.PANELS[WM.PANEL_INDEX[n]]["port_index"]   # אנימציות
                          for n, f in panel_images.items() if len(f) > 1}
        if paint.any():                       # בזמן קסם כל הקיר חייב להתרענן
            dynamic_ports.update(range(WM.PORT_COUNT))
        rows_to_send = [row for i in sorted(dynamic_ports | dirty_ports)
                        for row in range(i * WM.PANEL, (i + 1) * WM.PANEL)]
        wall.send_frame(WM.to_canvas(phys), rows=rows_to_send)
        dirty_ports.clear()

        if cap is not None:
            ok, f = cap.read()
            if ok:
                last_frame = f

        frames += 1
        if t0 - t_fps >= 15:
            active = " · ".join(f"{name}={port_label(i)}" for i, name in enumerate(WM.PORTS)
                              if port_visible[i])
            print(f"{frames/(t0-t_fps):.1f} fps · {active}", flush=True)
            frames, t_fps = 0, t0
        if a.seconds and time.monotonic() - t_start > a.seconds:
            break
        dt = period - (time.monotonic() - t0)
        if dt > 0:
            time.sleep(dt)
except KeyboardInterrupt:
    pass
finally:
    if cap is not None:
        if last_frame is not None:
            import cv2
            cv2.imwrite(a.shot, last_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            print("saved", a.shot)
        cap.release()
    wall.close()
    if sock:
        sock.close()
    print("היצור נרדם.")
