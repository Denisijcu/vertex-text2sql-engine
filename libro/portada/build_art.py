"""
build_art.py — Arte de portada de "Vertex-Core SQL", generado por código (sin imágenes de terceros).
Motivo: una rejilla de tablas en perspectiva; una "consulta" ilumina en cian las celdas que recorre.
Salida: arte.png (2000 x 3000, proporción 2:3).
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
W, H = 2000, 3000
BG_TOP, BG_BOT = (6, 11, 19), (11, 24, 38)
CELL = (28, 46, 66)
CELL_EDGE = (44, 68, 94)
CYAN = (34, 211, 238)
AMBER = (245, 158, 11)

rnd = random.Random(42)
img = Image.new("RGB", (W, H))
px = ImageDraw.Draw(img)
for y in range(H):  # degradado vertical
    t = y / H
    px.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))

# --- rejilla de tablas en perspectiva (mitad inferior) ---
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(layer)
horizon, base = 1350, H + 200
rows, cols = 22, 14
vx = W * 0.62  # punto de fuga
def proj(c, r):
    """c en [0,cols], r en [0,rows] -> punto en pantalla (perspectiva simple)."""
    t = (r / rows) ** 1.9
    y = horizon + (base - horizon) * t
    spread = 0.18 + 1.9 * t
    x = vx + (c / cols - 0.5) * W * spread
    return x, y

lit = set()
c = 4; r = rows - 1
while r > 2:  # camino de la "consulta": sube y se desplaza
    lit.add((c, r))
    if rnd.random() < 0.35 and 1 < c < cols - 2:
        c += rnd.choice([-1, 1]); lit.add((c, r))
    r -= 1
hot = {(cc, rr) for cc, rr in lit if rr % 5 == 0}

for rr in range(rows):
    for cc in range(cols):
        p = [proj(cc + 0.08, rr + 0.12), proj(cc + 0.92, rr + 0.12), proj(cc + 0.92, rr + 0.88), proj(cc + 0.08, rr + 0.88)]
        depth = rr / rows
        a = int(40 + 150 * depth)
        if (cc, rr) in lit:
            col = AMBER if (cc, rr) in hot else CYAN
            d.polygon(p, fill=col + (int(60 + 140 * depth),), outline=col + (230,))
        else:
            d.polygon(p, fill=CELL + (a,), outline=CELL_EDGE + (a,))
glow = layer.filter(ImageFilter.GaussianBlur(18))
img = Image.alpha_composite(img.convert("RGBA"), glow)
img = Image.alpha_composite(img, layer)

# --- líneas de datos verticales tenues (mitad superior, derecha) ---
fx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
f = ImageDraw.Draw(fx)
for i in range(46):
    x = rnd.randint(int(W * 0.40), W)
    y0 = rnd.randint(250, 1100)
    ln = rnd.randint(120, 520)
    for k in range(0, ln, 22):
        al = int(90 * (1 - k / ln))
        f.rectangle([x, y0 + k, x + 6, y0 + k + 10], fill=CYAN + (al,))
img = Image.alpha_composite(img, fx.filter(ImageFilter.GaussianBlur(1)))

# --- viñeta oscura arriba a la izquierda, donde va el título ---
vig = Image.new("L", (W, H), 0)
v = ImageDraw.Draw(vig)
for i in range(60):
    rad = 1700 - i * 22
    v.ellipse([-rad * 0.9, -rad * 0.7, rad * 0.9, rad * 0.7], fill=int(4 * i))
vig = vig.filter(ImageFilter.GaussianBlur(80))
dark = Image.new("RGBA", (W, H), BG_TOP + (255,))
img = Image.composite(dark, img, vig.point(lambda p: int(p * 0.85)))

img.convert("RGB").save(HERE / "arte.png")
print("OK arte.png", img.size)
