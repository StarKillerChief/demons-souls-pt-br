"""Original README banner: a sword planted in the ground, souls rising from it through the fog, with the
title set in EB Garamond. Procedural; no game art. Usage: make_banner.py OUT.png"""
import os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'EBGaramond.ttf')
OUT = sys.argv[1]
W, H = 2560, 1000
rng = np.random.default_rng(5)
random.seed(5)
SX, GROUND = 1930, 860                       # sword axis and ground line


def font(size, wght):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def noise(scale, octaves=5):
    acc, amp, tot = np.zeros((H, W), np.float32), 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / 2 ** o))
        small = rng.random((H // s + 2, W // s + 2)).astype(np.float32)
        im = Image.fromarray((small * 255).astype(np.uint8)).resize((W + s, H + s), Image.BICUBIC)
        acc += np.asarray(im, np.float32)[:H, :W] / 255 * amp
        tot += amp
        amp *= 0.5
    return acc / tot


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
# sky: near black, a pale cold light behind the sword
glow = np.exp(-(((xx - SX) / 520) ** 2 + ((yy - 470) / 430) ** 2))
img = np.stack([7 + 60 * glow, 7 + 63 * glow, 9 + 72 * glow], -1)
# fog: low bank over the ground, thin wisps above
f1, f2 = noise(460), noise(150)
low = np.clip((yy - 560) / 380, 0, 1) ** 1.2
f = np.clip(f1 * 1.5 - 0.40, 0, 1) * low * 0.85 + np.clip(f2 - 0.47, 0, 1) * 0.30 * np.clip(xx / W - 0.35, 0, 1)
img += (np.array([96, 100, 110]) - img) * np.clip(f, 0, 0.75)[..., None]

# ground: an uneven dark rise under the sword, fading into the fog
gm = Image.new('L', (W, H), 0)
pts = [(0, H)]
for x in range(0, W + 40, 40):
    hump = 70 * np.exp(-((x - SX) / 420) ** 2)
    pts.append((x, GROUND + 38 - hump + random.uniform(-6, 6)))
pts.append((W, H))
ImageDraw.Draw(gm).polygon(pts, fill=255)
g = np.asarray(gm.filter(ImageFilter.GaussianBlur(3)), np.float32)[..., None] / 255
img = img * (1 - g * 0.9) + np.array([10, 10, 12]) * g * 0.9

# the sword, drawn 4x and scaled down for clean edges
K = 4
sw = Image.new('L', (W * K, H * K), 0)
sd = ImageDraw.Draw(sw)
c = SX * K
sd.polygon([(c - 32 * K, 318 * K), (c + 32 * K, 318 * K), (c + 26 * K, (GROUND + 10) * K), (c - 26 * K, (GROUND + 10) * K)], fill=255)
sd.polygon([(c - 128 * K, 300 * K), (c - 30 * K, 286 * K), (c + 30 * K, 286 * K), (c + 128 * K, 300 * K),
            (c + 122 * K, 322 * K), (c + 30 * K, 318 * K), (c - 30 * K, 318 * K), (c - 122 * K, 322 * K)], fill=255)
sd.ellipse([c - 140 * K, 296 * K, c - 112 * K, 330 * K], fill=255)
sd.ellipse([c + 112 * K, 296 * K, c + 140 * K, 330 * K], fill=255)
sd.rectangle([c - 16 * K, 150 * K, c + 16 * K, 288 * K], fill=255)
for wy in range(162, 284, 18):                                       # grip wrapping
    sd.rectangle([c - 19 * K, wy * K, c + 19 * K, (wy + 7) * K], fill=255)
sd.ellipse([c - 34 * K, 100 * K, c + 34 * K, 160 * K], fill=255)
sw = sw.rotate(-6, resample=Image.BICUBIC, center=(c, GROUND * K))
sword = np.asarray(sw.resize((W, H), Image.LANCZOS), np.float32)[..., None] / 255
img = img * (1 - sword) + np.array([12, 12, 14]) * sword
# rim light on the sword's edges (light comes from behind)
rim = np.clip(sword - np.roll(sword, -3, axis=1), 0, 1) + np.clip(sword - np.roll(sword, 3, axis=0), 0, 1) * 0.6
rim = rim * np.clip(1 - (yy - 300) / 700, 0.25, 1)[..., None]
img += rim * np.array([120, 124, 136])

# darker on the left for the lettering, vignette, grain
img *= (1 - 0.6 * np.clip(1 - (xx / W) / 0.55, 0, 1) ** 1.3)[..., None]
vig = np.clip(1 - (((xx - W / 2) / (W * 0.64)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2), 0, 1) ** 0.6
img *= (0.35 + 0.65 * vig)[..., None]
img = np.clip(img + rng.normal(0, 3.0, (H, W, 1)), 0, 255)
canvas = Image.fromarray(img.astype(np.uint8), 'RGB')

# souls: motes rising from the sword's base, denser and brighter near it, drifting as they climb
motes = Image.new('RGB', (W, H), 0)
md = ImageDraw.Draw(motes)
for _ in range(95):
    t = random.random() ** 0.8
    y = GROUND - 30 - t * 760
    spread = 30 + t * 420
    x = SX + random.gauss(0, spread * 0.5) + t * 120
    r = random.choice([2, 3, 3, 4, 5]) * (1.2 - 0.5 * t)
    a = (1 - 0.6 * t) * random.uniform(0.5, 1)
    md.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * a) for v in (255, 238, 205)))
halo = np.asarray(motes.filter(ImageFilter.GaussianBlur(10)), np.float32)
core = np.asarray(motes.filter(ImageFilter.GaussianBlur(1.3)), np.float32)
base_glow = np.exp(-(((xx - SX) / 150) ** 2 + ((yy - GROUND + 10) / 40) ** 2))[..., None] * np.array([90, 80, 62])
canvas = Image.fromarray(np.clip(np.asarray(canvas, np.float32) + halo * 2.4 + core + base_glow, 0, 255)
                         .astype(np.uint8)).convert('RGBA')

# lettering, with room to breathe
INK, GOLD, DIM = (242, 237, 228), (201, 176, 124), (168, 157, 138)
X = 170


def spaced(draw, xy, s, f, fill, track):
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + track
    return x


layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
ld = ImageDraw.Draw(layer)
end = spaced(ld, (X, 150), "Demon's Souls", font(188, 500), INK + (255,), 2)
gl = layer.filter(ImageFilter.GaussianBlur(20))
canvas = Image.alpha_composite(canvas, Image.merge('RGBA', (*gl.split()[:3], gl.split()[3].point(lambda v: v // 3))))
canvas = Image.alpha_composite(canvas, layer)
d = ImageDraw.Draw(canvas)
ly = 470
cx = (X + end) / 2
d.line([(X + 4, ly), (cx - 30, ly)], fill=(138, 118, 86, 255), width=3)
d.line([(cx + 30, ly), (end - 10, ly)], fill=(138, 118, 86, 255), width=3)
d.polygon([(cx, ly - 15), (cx + 15, ly), (cx, ly + 15), (cx - 15, ly)], fill=(20, 17, 14, 255), outline=GOLD + (255,), width=3)
spaced(d, (X + 2, 540), 'TRADUÇÃO PT-BR', font(72, 560), GOLD + (255,), 16)
spaced(d, (X + 4, 670), 'para Soulbrandt e RPCS3  ·  por Fábio – StarKillerChief', font(50, 430), DIM + (255,), 2)

# Brazil flag (public-domain design), drawn
fx, fy, fw, fh = X + 4, 790, 112, 78
s = 4
flag = Image.new('RGBA', (fw * s, fh * s), (0, 0, 0, 0))
fd = ImageDraw.Draw(flag)
fd.rounded_rectangle([0, 0, fw * s - 1, fh * s - 1], 9 * s, fill=(30, 148, 71, 255))
fd.polygon([(fw * s / 2, 8 * s), (fw * s - 9 * s, fh * s / 2), (fw * s / 2, fh * s - 8 * s), (9 * s, fh * s / 2)], fill=(247, 209, 22, 255))
r = 19 * s
fd.ellipse([fw * s / 2 - r, fh * s / 2 - r, fw * s / 2 + r, fh * s / 2 + r], fill=(38, 53, 127, 255))
fd.arc([fw * s / 2 - r * 2.2, fh * s / 2 - r * 0.55, fw * s / 2 + r * 1.6, fh * s / 2 + r * 3.2], 235, 300, fill=(242, 242, 242, 255), width=4 * s)
canvas.alpha_composite(flag.resize((fw, fh), Image.LANCZOS), (fx, fy))
d.text((fx + fw + 30, fy + 10), 'Português do Brasil  ·  v0.1', font=font(44, 430), fill=(148, 138, 120, 255))

d.rectangle([28, 28, W - 29, H - 29], outline=(92, 81, 66, 255), width=3)
d.rectangle([42, 42, W - 43, H - 43], outline=(45, 39, 31, 255), width=2)
canvas.convert('RGB').save(OUT, optimize=True)
print('saved', OUT)
