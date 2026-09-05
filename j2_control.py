"""לוח שליטה מקומי ליציאות J1-J8 של GOLEM."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import socket
import time

from PIL import Image
import wall_map as WM


ROOT = Path(__file__).resolve().parent
FRAME_DIR = ROOT / "data" / "port_frames"
VISION_STATE = ROOT / "vision_state.json"
PORTS = tuple(f"J{i}" for i in range(1, 9))
PORT_SIZES = {port: (WM.PORT_LAYOUT[port]["w"], WM.PORT_LAYOUT[port]["h"])
              for port in PORTS}
MODES = {"critter", "spark", "face", "off"}
TOKEN = secrets.token_urlsafe(24)
PORT_STATE = {port: ("critter" if port == "J1" else "spark" if port == "J2" else "off")
              for port in PORTS}


def udp_send(message):
    data = json.dumps(message).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.sendto(data, ("127.0.0.1", 9999))


def decode_frame(data_url, size=(64, 64)):
    if not isinstance(data_url, str) or not data_url.startswith("data:image/png;base64,"):
        raise ValueError("נדרשת תמונת PNG")
    raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    if len(raw) > 2_000_000:
        raise ValueError("התמונה גדולה מדי")
    with Image.open(io.BytesIO(raw)) as source:
        source.verify()
    with Image.open(io.BytesIO(raw)) as source:
        return source.convert("RGB").resize(size, Image.LANCZOS)


def vision_state():
    offline = {"people": 0, "identity": "offline", "scene": "המצלמה אינה מחוברת."}
    try:
        if time.time() - VISION_STATE.stat().st_mtime > 30:
            return offline
        return json.loads(VISION_STATE.read_text(encoding="utf-8"))
    except Exception:
        return offline


HTML = r'''<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GOLEM · בקרת יציאות</title>
<style>
:root{
  color-scheme:dark;
  --bg:oklch(0.09 0 0);--surface:oklch(0.145 0.012 35);--surface-2:oklch(0.19 0.018 35);
  --ink:oklch(0.96 0.01 55);--muted:oklch(0.72 0.025 45);--line:oklch(0.31 0.025 35);
  --primary:oklch(0.68 0.17 42);--primary-strong:oklch(0.60 0.19 38);--ok:oklch(0.73 0.16 150);
  --warn:oklch(0.78 0.15 82);--focus:oklch(0.82 0.13 210);
}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;min-height:100vh;background:var(--bg);color:var(--ink);font-family:Arial,"Noto Sans Hebrew",sans-serif}
button,input{font:inherit}button{color:inherit}
.shell{width:min(920px,calc(100% - 28px));margin:0 auto;padding:24px 0 40px}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}
.brand{display:flex;align-items:center;gap:12px}.mark{width:42px;height:42px;display:grid;place-items:center;background:var(--primary);color:var(--bg);font-weight:900;font-size:22px;border-radius:10px}
h1{font-size:1.35rem;margin:0 0 4px;letter-spacing:-.02em}.sub{margin:0;color:var(--muted);font-size:.92rem}
.live{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:.88rem}.dot{width:9px;height:9px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 4px oklch(0.73 0.16 150/.12)}
.ports{display:flex;gap:7px;overflow-x:auto;padding:2px 2px 12px;scrollbar-width:thin}
.port{min-width:72px;min-height:54px;padding:7px 10px;border:0;border-radius:10px;background:var(--surface);cursor:pointer;text-align:center;transition:background .18s ease,transform .18s ease}
.port:hover{background:var(--surface-2)}.port:active{transform:translateY(1px)}.port[aria-selected="true"]{background:var(--primary);color:var(--bg);font-weight:800}
.port small{display:block;margin-top:3px;font-size:.68rem;color:var(--muted)}.port[aria-selected="true"] small{color:oklch(0.18 0.03 35)}
.grid{display:grid;grid-template-columns:minmax(270px,.82fr) minmax(320px,1.18fr);gap:14px}
.pane{background:var(--surface);border-radius:14px;padding:18px}.pane h2{font-size:1rem;margin:0 0 14px}
.screen-wrap{display:grid;place-items:center;min-height:310px;background:oklch(0.045 0 0);border-radius:10px;position:relative;overflow:hidden}
#screen{width:256px;height:auto;max-width:80vw;image-rendering:pixelated;background:oklch(0 0 0)}
.screen-label{position:absolute;inset:auto 10px 9px;display:flex;justify-content:space-between;color:var(--muted);font-size:.72rem;pointer-events:none}
.modes{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.mode{min-height:48px;border:0;border-radius:9px;background:var(--surface-2);cursor:pointer;font-weight:700}
.mode:hover{background:oklch(0.25 0.03 35)}.mode.active{background:var(--primary);color:var(--bg)}
.status{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:15px 0 18px;padding:10px 12px;background:oklch(0.11 0.008 35);border-radius:9px;font-size:.82rem}
.badge{font-weight:700;color:var(--ok)}.badge.pending{color:var(--warn)}
.custom{margin-top:18px;padding-top:17px;border-top:1px solid var(--line)}.custom h3{font-size:.92rem;margin:0 0 12px}
.field{display:grid;gap:6px;margin-bottom:10px}.field label{font-size:.76rem;color:var(--muted)}
input[type="text"]{width:100%;min-height:44px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);padding:0 11px}
.row{display:flex;gap:8px;align-items:end}.row .field{flex:1}.color{width:48px;height:44px;padding:4px;background:var(--bg);border:1px solid var(--line);border-radius:8px}
.actions{display:flex;gap:8px;flex-wrap:wrap}.primary,.secondary{min-height:44px;border:0;border-radius:8px;padding:0 14px;cursor:pointer;font-weight:800}
.primary{background:var(--primary);color:var(--bg)}.primary:hover{background:var(--primary-strong);color:white}.secondary{background:var(--surface-2)}
.vision{margin-top:14px;padding:15px 18px;background:var(--surface);border-radius:14px;display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:start}
.eye{font-size:1.25rem;line-height:1}.vision strong{display:block;font-size:.84rem;margin-bottom:4px}.vision p{margin:0;color:var(--muted);font-size:.84rem;line-height:1.55}
.toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:10px 15px;border-radius:8px;font-weight:700;opacity:0;pointer-events:none;transition:opacity .18s ease}.toast.show{opacity:1}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
@media(max-width:720px){.shell{width:min(100% - 18px,620px);padding-top:14px}header{align-items:center}.grid{grid-template-columns:1fr}.screen-wrap{min-height:284px}.pane{padding:14px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style>
</head>
<body>
<main class="shell">
  <header>
    <div class="brand"><div class="mark">G</div><div><h1>בקרת יציאות GOLEM</h1><p class="sub">Colorlight · שליטה נפרדת ב־J1–J8</p></div></div>
    <div class="live"><span class="dot"></span>משדר</div>
  </header>
  <nav class="ports" role="tablist" aria-label="בחירת יציאה"></nav>
  <div class="grid">
    <section class="pane" aria-labelledby="preview-title">
      <h2 id="preview-title">תצוגה מקדימה · <span id="selected-name">J2</span></h2>
      <div class="screen-wrap"><canvas id="screen" width="64" height="64"></canvas><div class="screen-label"><span id="preview-size">64×64</span><span id="preview-mode">ניצוץ</span></div></div>
    </section>
    <section class="pane" aria-labelledby="controls-title">
      <h2 id="controls-title">מה להציג</h2>
      <div class="modes">
        <button class="mode" data-mode="spark">ניצוץ</button><button class="mode" data-mode="critter">דמות קלוד</button>
        <button class="mode" data-mode="face">פנים</button><button class="mode" data-mode="off">כבוי</button>
      </div>
      <div class="status"><span id="mapping-copy">מיפוי פיזי מאומת</span><span class="badge" id="mapping-badge">מוכן</span></div>
      <div class="custom">
        <h3>תוכן מותאם</h3>
        <div class="field"><label for="text">טקסט קצר</label><input id="text" type="text" maxlength="18" value="שלום" autocomplete="off"></div>
        <div class="row"><div class="field"><label for="fg">צבע טקסט</label><input class="color" id="fg" type="color" value="#f08a54"></div><div class="field"><label for="bg">רקע</label><input class="color" id="bg" type="color" value="#000000"></div></div>
        <div class="actions"><button class="secondary" id="test-port">בדוק יציאה</button><button class="secondary" id="draw-text">הצג טקסט</button><label class="secondary" style="display:grid;place-items:center;cursor:pointer">בחר תמונה<input id="image" type="file" accept="image/*" hidden></label><button class="primary" id="push-frame">שלח לפאנל</button></div>
      </div>
    </section>
  </div>
  <section class="vision" aria-live="polite"><div class="eye">◉</div><div><strong>מה קלוד רואה</strong><p id="vision">המצלמה אינה מחוברת.</p></div></section>
</main>
<div class="toast" role="status" aria-live="polite"></div>
<script>
const TOKEN='__TOKEN__', ports=['J1','J2','J3','J4','J5','J6','J7','J8'];
const labels={spark:'ניצוץ',critter:'דמות קלוד',face:'פנים',off:'כבוי',custom:'מותאם'};
const portWidths=__PORT_WIDTHS__;
const testColors={J1:'#e84b4b',J2:'#ee8a32',J3:'#d4c83b',J4:'#52b96b',J5:'#36a9bd',J6:'#4f72d8',J7:'#8a59d1',J8:'#c0529b'};
const modes={J1:'critter',J2:'spark',J3:'off',J4:'off',J5:'off',J6:'off',J7:'off',J8:'off'};
let selected='J2';const nav=document.querySelector('.ports'),canvas=document.querySelector('#screen'),ctx=canvas.getContext('2d');
ctx.imageSmoothingEnabled=false;
function toast(text){const el=document.querySelector('.toast');el.textContent=text;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),1600)}
function renderPorts(){nav.innerHTML='';ports.forEach(port=>{const b=document.createElement('button');b.className='port';b.role='tab';b.ariaSelected=String(port===selected);b.innerHTML=`${port}<small>${labels[modes[port]]}</small>`;b.onclick=()=>{selected=port;renderPorts();syncPanel()};nav.append(b)})}
function drawPreset(mode){const ox=(canvas.width-64)/2;ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,64);if(mode==='spark'){ctx.save();ctx.translate(ox+32,32);ctx.fillStyle='#e9783e';for(let i=0;i<12;i++){ctx.rotate(Math.PI/6);ctx.fillRect(-2,-25,4,18)}ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(0,0,4,0,Math.PI*2);ctx.fill();ctx.restore()}else if(mode==='critter'){ctx.fillStyle='#d96e3b';ctx.fillRect(ox+12,13,40,38);ctx.fillStyle='#fff';ctx.fillRect(ox+20,24,8,8);ctx.fillRect(ox+36,24,8,8);ctx.fillStyle='#17110f';ctx.fillRect(ox+23,26,3,4);ctx.fillRect(ox+39,26,3,4)}else if(mode==='face'){ctx.fillStyle='#fff';ctx.fillRect(ox+16,24,9,4);ctx.fillRect(ox+39,24,9,4);ctx.beginPath();ctx.arc(ox+32,35,13,.2,Math.PI-.2);ctx.strokeStyle='#e9783e';ctx.lineWidth=3;ctx.stroke()}}
function syncPanel(){const width=portWidths[selected];if(canvas.width!==width){canvas.width=width;canvas.height=64;ctx.imageSmoothingEnabled=false}canvas.style.width=width===128?'100%':'256px';document.querySelector('#selected-name').textContent=selected;document.querySelector('#preview-size').textContent=`${width}×64`;document.querySelector('#preview-mode').textContent=labels[modes[selected]];document.querySelectorAll('.mode').forEach(b=>b.classList.toggle('active',b.dataset.mode===modes[selected]));const verified=['J1','J2'].includes(selected),wide=selected==='J4';document.querySelector('#mapping-copy').textContent=verified?'מיפוי פיזי מאומת':wide?'מחובר · שני פאנלים משמאל לימין':'מוכן בתוכנה · דרוש אימות עם פאנל';const badge=document.querySelector('#mapping-badge');badge.textContent=verified?'מאומת':wide?'128×64 לבדיקה':'טרם אומת';badge.classList.toggle('pending',!verified);if(modes[selected]!=='custom')drawPreset(modes[selected])}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-GOLEM-Token':TOKEN},body:JSON.stringify(body)});const out=await r.json();if(!r.ok)throw Error(out.error||'הפקודה נכשלה');return out}
document.querySelectorAll('.mode').forEach(b=>b.onclick=async()=>{try{await post('/api/mode',{port:selected,mode:b.dataset.mode});modes[selected]=b.dataset.mode;renderPorts();syncPanel();toast(`${selected} עודכן`)}catch(e){toast(e.message)}});
function drawText(){const text=document.querySelector('#text').value.trim()||' ';ctx.fillStyle=document.querySelector('#bg').value;ctx.fillRect(0,0,canvas.width,64);ctx.fillStyle=document.querySelector('#fg').value;ctx.textAlign='center';ctx.textBaseline='middle';ctx.direction='rtl';let size=24;do{ctx.font=`800 ${size}px Arial`;size--}while(ctx.measureText(text).width>canvas.width-6&&size>8);ctx.fillText(text,canvas.width/2,32);modes[selected]='custom';renderPorts();syncPanel()}
document.querySelector('#draw-text').onclick=drawText;
document.querySelector('#test-port').onclick=()=>{ctx.fillStyle=testColors[selected];ctx.fillRect(0,0,canvas.width,64);ctx.fillStyle='#fff';ctx.textAlign='center';ctx.textBaseline='middle';ctx.direction='ltr';if(canvas.width===128){ctx.fillStyle='#267a3d';ctx.fillRect(64,0,64,64);ctx.font='900 15px Arial';ctx.fillStyle='#fff';ctx.fillText('J4-L',32,32);ctx.fillText('J4-R',96,32)}else{ctx.font='900 25px Arial';ctx.fillText(selected,32,32)}modes[selected]='custom';renderPorts();syncPanel();document.querySelector('#push-frame').click()};
document.querySelector('#image').onchange=e=>{const file=e.target.files[0];if(!file)return;const img=new Image;img.onload=()=>{ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,64);const scale=Math.min(canvas.width/img.width,64/img.height),w=img.width*scale,h=img.height*scale;ctx.drawImage(img,(canvas.width-w)/2,(64-h)/2,w,h);modes[selected]='custom';renderPorts();syncPanel()};img.src=URL.createObjectURL(file)};
document.querySelector('#push-frame').onclick=async()=>{try{await post('/api/frame',{port:selected,image:canvas.toDataURL('image/png')});modes[selected]='custom';renderPorts();syncPanel();toast(`התמונה נשלחה ל-${selected}`)}catch(e){toast(e.message)}};
async function refresh(){try{const r=await fetch('/api/state');const s=await r.json();Object.assign(modes,s.ports);renderPorts();syncPanel();document.querySelector('#vision').textContent=s.vision.scene||'המצלמה פעילה.'}catch{document.querySelector('.live').lastChild.textContent='לא מחובר'}}
renderPorts();syncPanel();refresh();setInterval(refresh,4000);
</script>
</body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def reply(self, status, payload, content_type="application/json; charset=utf-8"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/":
            widths = json.dumps({port: size[0] for port, size in PORT_SIZES.items()})
            page = HTML.replace("__TOKEN__", TOKEN).replace("__PORT_WIDTHS__", widths).encode("utf-8")
            self.reply(200, page, "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self.reply(200, {"ports": PORT_STATE, "sizes": PORT_SIZES,
                             "vision": vision_state(), "time": time.time()})
        else:
            self.reply(404, {"error": "לא נמצא"})

    def do_POST(self):
        if self.headers.get("X-GOLEM-Token") != TOKEN:
            self.reply(403, {"error": "בקשה לא מורשית"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_500_000:
                raise ValueError("גודל בקשה לא תקין")
            data = json.loads(self.rfile.read(length))
            port = data.get("port")
            if port not in PORTS:
                raise ValueError("יציאה לא תקינה")
            if self.path == "/api/mode":
                mode = data.get("mode")
                if mode not in MODES:
                    raise ValueError("מצב לא תקין")
                udp_send({"port": port, "port_mode": mode})
                PORT_STATE[port] = mode
            elif self.path == "/api/frame":
                image = decode_frame(data.get("image"), PORT_SIZES[port])
                FRAME_DIR.mkdir(parents=True, exist_ok=True)
                path = FRAME_DIR / f"{port}.png"
                image.save(path)
                udp_send({"port": port, "port_image": str(path)})
                PORT_STATE[port] = "custom"
            else:
                self.reply(404, {"error": "לא נמצא"})
                return
            self.reply(200, {"ok": True, "port": port, "mode": PORT_STATE[port]})
        except Exception as error:
            self.reply(400, {"error": str(error)})


def self_test():
    source = Image.new("RGB", (16, 16), (230, 110, 58))
    buffer = io.BytesIO()
    source.save(buffer, "PNG")
    url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    assert decode_frame(url).size == (64, 64)
    assert decode_frame(url, PORT_SIZES["J4"]).size == (128, 64)
    assert PORTS == ("J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8")
    print("controller self-test: ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        print(f"GOLEM control: http://127.0.0.1:{args.port}", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
