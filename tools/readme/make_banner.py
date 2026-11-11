"""Original README banner for demons-souls-pt-br: procedural fog, distant towers, drifting soul motes,
EB Garamond lettering and a drawn Brazil flag. No game art. Output 2x for crisp display."""
import math, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = __import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'fonts', 'EBGaramond.ttf')
OUT = sys.argv[1]
W, H = 2560, 860
rng = np.random.default_rng(7)
random.seed(7)


def font(size, wght):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def noise(scale, octaves=5):
    acc = np.zeros((H, W), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / 2 ** o))
        small = rng.random((H // s + 2, W // s + 2)).astype(np.float32)
        im = Image.fromarray((small * 255).astype(np.uint8)).resize((W + s, H + s), Image.BICUBIC)
        acc += np.asarray(im, np.float32)[:H, :W] / 255 * amp
        tot += amp
        amp *= 0.5
    return acc / tot


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
# base: warm black with a cold light behind the towers (right)
d = np.sqrt(((xx - W * 0.74) / (W * 0.55)) ** 2 + ((yy - H * 0.46) / (H * 0.9)) ** 2)
light = np.clip(1 - d, 0, 1) ** 1.6
moon = np.exp(-(((xx - W * 0.80) ** 2 + (yy - H * 0.30) ** 2) / (2 * (H * 0.22) ** 2)))
base = np.stack([8 + 44 * light + 70 * moon, 7 + 46 * light + 74 * moon, 7 + 50 * light + 84 * moon], -1)

# distant towers (procedural silhouettes), two layers in fog
def towers(seed, x0, x1, ymin, ymax, count):
    r = random.Random(seed)
    m = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(m)
    x = x0
    while x < x1:
        w = r.randint(*count)
        top = r.randint(ymin, ymax)
        dr.rectangle([x, top, x + w, H], fill=255)
        if r.random() < 0.6:                                   # pointed roof
            dr.polygon([(x - 6, top), (x + w + 6, top), (x + w / 2, top - r.randint(60, 190))], fill=255)
            if r.random() < 0.5:
                dr.line([(x + w / 2, top - 200), (x + w / 2, top - 120)], fill=255, width=4)
        if r.random() < 0.35:                                  # battlement
            for bx in range(x, x + w, 22):
                dr.rectangle([bx, top - 18, bx + 11, top], fill=255)
        x += w + r.randint(-10, 70)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255

far = towers(3, int(W * 0.48), W, int(H * 0.30), int(H * 0.58), (40, 110))
near = towers(11, int(W * 0.56), W, int(H * 0.48), int(H * 0.72), (70, 170))
fog = noise(420)
fog2 = noise(160)
img = base.copy()
rise = np.clip((yy / H - 0.45) / 0.5, 0, 1)[..., None]
farc = np.array([30, 33, 40]) * (1 - rise) + np.array([70, 74, 82]) * rise
nearc = np.array([8, 8, 10]) * (1 - rise) + np.array([48, 50, 56]) * rise
img = img * (1 - far[..., None] * 0.7) + farc * far[..., None] * 0.7
img = img * (1 - near[..., None] * 0.92) + nearc * near[..., None] * 0.92
# rolling fog, thicker low and right
band = np.clip((yy / H - 0.35) * 1.6, 0, 1) * np.clip((xx / W - 0.25) * 1.6, 0, 1)
f = np.clip(fog * 1.6 - 0.45, 0, 1) * band * 0.9 + np.clip(fog2 - 0.42, 0, 1) * 0.35 * band
img = img + (np.array([110, 114, 124]) - img) * np.clip(f, 0, 0.8)[..., None]
# left darkening for the lettering and vignette
left = np.clip(1 - (xx / W) / 0.55, 0, 1) ** 1.4
img *= (1 - 0.55 * left)[..., None]
vig = np.clip(1 - (((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.78)) ** 2), 0, 1) ** 0.6
img *= (0.35 + 0.65 * vig)[..., None]
grain = rng.normal(0, 3.2, (H, W, 1))
img = np.clip(img + grain, 0, 255)
canvas = Image.fromarray(img.astype(np.uint8), 'RGB')

# soul motes: soft glowing points drifting upward from the fog
glow = Image.new('RGB', (W, H), 0)
gd = ImageDraw.Draw(glow)
for _ in range(70):
    x = random.uniform(W * 0.42, W * 0.98)
    y = random.uniform(H * 0.15, H * 0.92)
    r = random.choice([2, 2, 3, 3, 4, 6])
    a = random.uniform(0.35, 1)
    c = tuple(int(v * a) for v in (235, 240, 255))
    gd.ellipse([x - r, y - r, x + r, y + r], fill=c)
halo = glow.filter(ImageFilter.GaussianBlur(9))
core = glow.filter(ImageFilter.GaussianBlur(1.2))
canvas = Image.fromarray(np.clip(np.asarray(canvas, np.float32) + np.asarray(halo, np.float32) * 2.2
                                 + np.asarray(core, np.float32) * 0.9, 0, 255).astype(np.uint8))

# lettering
INK = (242, 237, 228)
GOLD = (201, 176, 124)
DIM = (170, 158, 138)
X = 150
layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
ld = ImageDraw.Draw(layer)


def spaced(draw, xy, s, f, fill, track):
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + track
    return x


title = font(196, 500)
end = spaced(ld, (X, 150), "Demon's Souls", title, INK + (255,), 3)
# soft glow behind the title
g = layer.filter(ImageFilter.GaussianBlur(18))
canvas = Image.alpha_composite(canvas.convert('RGBA'), Image.merge('RGBA', (*g.split()[:3], g.split()[3].point(lambda v: v // 3))))
canvas = Image.alpha_composite(canvas, layer)
d = ImageDraw.Draw(canvas)
# ornament: line - diamond - line
ly = 452
d.line([(X + 4, ly), (end - 30, ly)], fill=(138, 118, 86, 255), width=3)
cx = (X + end) / 2
d.polygon([(cx, ly - 14), (cx + 14, ly), (cx, ly + 14), (cx - 14, ly)], fill=(20, 17, 14, 255), outline=(201, 176, 124, 255), width=3)
spaced(d, (X + 2, 492), 'TRADUÇÃO PT-BR', font(76, 560), GOLD + (255,), 22)
spaced(d, (X + 4, 610), 'para Soulbrandt e RPCS3  ·  feita por fãs', font(52, 430), DIM + (255,), 4)

# Brazil flag (public-domain design), drawn small next to the subtitle line
fx, fy, fw, fh = X + 4, 712, 120, 84
flag = Image.new('RGBA', (fw * 4, fh * 4), (0, 0, 0, 0))
fd = ImageDraw.Draw(flag)
s = 4
fd.rounded_rectangle([0, 0, fw * s - 1, fh * s - 1], 10 * s, fill=(30, 148, 71, 255))
fd.polygon([(fw * s / 2, 9 * s), (fw * s - 10 * s, fh * s / 2), (fw * s / 2, fh * s - 9 * s), (10 * s, fh * s / 2)], fill=(247, 209, 22, 255))
r = 21 * s
fd.ellipse([fw * s / 2 - r, fh * s / 2 - r, fw * s / 2 + r, fh * s / 2 + r], fill=(38, 53, 127, 255))
fd.arc([fw * s / 2 - r * 2.2, fh * s / 2 - r * 0.55, fw * s / 2 + r * 1.6, fh * s / 2 + r * 3.2], 235, 300, fill=(242, 242, 242, 255), width=4 * s)
flag = flag.resize((fw, fh), Image.LANCZOS)
canvas.alpha_composite(flag, (fx, fy))
d.text((fx + fw + 26, fy + 8), 'Português do Brasil · v0.1', font=font(46, 430), fill=(150, 140, 122, 255))

# thin double frame like the game's menus
d.rectangle([28, 28, W - 29, H - 29], outline=(92, 81, 66, 255), width=3)
d.rectangle([42, 42, W - 43, H - 43], outline=(45, 39, 31, 255), width=2)
canvas.convert('RGB').save(OUT, optimize=True)
print('saved', OUT)
