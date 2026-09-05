"""preview_face.py - השוואת איכות: הרנדר החדש, בגודל האמיתי 64 ומוגדל."""
import sys, os, time
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from face.critter import Critter

c = Critter()
combos = [("neutral", "none"), ("happy", "none"), ("wink", "none"), ("cool", "none"),
          ("surprised", "none"), ("neutral", "wizard"), ("neutral", "chef"),
          ("happy", "crown"), ("neutral", "headphones"), ("cool", "suit"),
          ("neutral", "goggles"), ("happy", "party")]
cells = []
t0 = time.time()
frames = 0
for expr, hat in combos:
    c.set(state="idle", expr=expr, hat=hat, gaze=(0, 0))
    for _ in range(6):
        img = c.render(); frames += 1
    cells.append(img)
print(f"{frames/(time.time()-t0):.1f} fps ברנדר")

cols = 6
rows = (len(cells) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 140, rows * 300), (18, 18, 22))
for i, img in enumerate(cells):
    x, y = (i % cols) * 140 + 6, (i // cols) * 300 + 10
    sheet.paste(img, (x, y))
    sheet.paste(img.resize((64, 64), Image.LANCZOS).resize((128, 128), Image.NEAREST),
                (x, y + 145))
sheet.save("critter_sheet.png")
print("wrote critter_sheet.png")
