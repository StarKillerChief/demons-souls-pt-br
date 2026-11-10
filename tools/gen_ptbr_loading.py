#!/usr/bin/env python3
"""Portuguese loading screens, made on the player's PC from the player's own copy.

    gen_ptbr_loading.py MENU_DIR OUT_DIR [--preview DIR] [--only 00,05]

MENU_DIR  folder with the game's menu/00.tpf ... 16.tpf (plain, already decoded from .dcx)
OUT_DIR   where the changed NN.tpf files are written (same size and layout as the originals)

Each loading screen is one 1024x1024 DXT1 texture with a full mip chain. The upper 1024x720 part is the picture,
with the character's name painted at the top left and "NOW LOADING" next to the emblem at the bottom.
For each one:
  1. find the English lettering: the pixels that are darker (name) or brighter (NOW LOADING) than the
     parchment around them, limited to where the English words, set in the same kind of type, would be;
  2. paint the parchment back over those pixels (smooth background plus the paper's own grain from just beside);
  3. set the Portuguese line in EB Garamond (SIL Open Font License, bundled) at the size, spacing and position
     measured from the English line, coloured the way the original is (the name darkens the paper, the gold
     words lighten it).
Only the 4x4 blocks that changed are replaced in the texture; the small mip levels are rebuilt from the result.
Nothing from the game is stored in this repository: the per-screen data below is the text and nothing else.
Needs Pillow (bundled with the installer's Python).
"""
import argparse
import json
import io
import os
import statistics
import struct
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_ptbr_glyphs as g  # noqa: E402

FONT = os.path.join(HERE, 'fonts', 'EBGaramond.ttf')
SIZE = 1024            # texture side
PIC_H = 720            # the picture part; below it is the rest of the art, untouched

# file -> (English name as painted, Portuguese name as in the translated game text)
SCREENS = {
    '00': ('Ostrava of Boletaria', 'Ostrava de Boletaria'),
    '01': ('Biorr of the Twin Fangs', 'Biorr das Presas Duplas'),
    '02': ('Old King Doran', 'Velho Rei Doran'),
    '03': ('Sage Freke, the Visionary', 'Sábio Freke, o Visionário'),
    '04': ('Yuria, the Witch', 'Yuria, a Bruxa'),
    '05': ('Saint Urbain', 'São Urbain'),
    '06': ('Blacksmith Ed and Boldwin', 'Ferreiro Ed e Boldwin'),
    '07': ('Patches, the Hyena', 'Patches, a Hiena'),
    '08': ('Executioner Miralda', 'Carrasca Miralda'),
    '09': ('Satsuki', 'Satsuki'),
    '10': ('Lord Rydell', 'Lorde Rydell'),
    '11': ('Selen Vinland', 'Selen Vinland'),
    '12': ('Scirvir,  the Wanderer', 'Scirvir, o Viajante'),
    '13': ('Yurt, the Silent Chief', 'Yurt, o Chefe Silencioso'),
    '14': ('Mephistopheles', 'Mefistófeles'),
    '15': ('The Monumental', 'O Monumental'),
    '16': ('Maiden in Black', 'Dama de Preto'),
}
LOADING = ('NOW LOADING', 'CARREGANDO')

# where to look (picture coordinates): name band, and the NOW LOADING band
NAME_AREA = (100, 30, 1000, 140)
LOAD_AREA = (260, 630, 640, 695)
SS = 4                 # supersampling for the type
WEIGHT = 600          # EB Garamond is a variable font (400..800); the game's lettering is a semibold
# type size and extra letter spacing (texture pixels), fitted to the English lines of the cleanest screens
NAME_STYLE = (33.5, 7.4, WEIGHT)
LOAD_STYLE = (23.6, 4.3, 720)    # heavier: at this size the thin bar of E broke up at 600
# NOW LOADING sits in the same place on all 17 screens: first letter, cap top, end of the last letter
LOAD_PLACE = (305, 652, 501)


# ----------------------------------------------------------------------------- texture in / out
def dds_header(w, h, fourcc, size):
    hdr = b'DDS ' + struct.pack('<7I', 124, 0x81007, h, w, size, 0, 0) + b'\0' * 44
    return hdr + struct.pack('<2I4s5I', 32, 4, fourcc, 0, 0, 0, 0, 0) + struct.pack('<5I', 0x1000, 0, 0, 0, 0)


def levels():
    out, off, w = [], 0, SIZE
    while True:
        n = max(1, w // 4) ** 2 * 8
        out.append((w, off, n))
        off += n
        if w == 1:
            return out
        w //= 2


def decode(tex):
    n = levels()[0][2]
    return Image.open(io.BytesIO(dds_header(SIZE, SIZE, b'DXT1', n) + tex[:n])).convert('RGB')


def encode(img):
    b = io.BytesIO()
    img.convert('RGBA').save(b, 'DDS', pixel_format='DXT1')
    return b.getvalue()[128:]


def write_texture(tex, new, region):
    """tex: original bytes (all levels). new: changed level-0 image. region: (x0,y0,x1,y1) that changed."""
    tex = bytearray(tex)
    w0, off0, n0 = levels()[0]
    enc = encode(new)
    assert len(enc) == n0, len(enc)
    bw = SIZE // 4
    x0, y0, x1, y1 = region
    for by in range(max(0, y0 // 4), min(bw, (y1 + 3) // 4)):
        for bx in range(max(0, x0 // 4), min(bw, (x1 + 3) // 4)):
            k = (by * bw + bx) * 8
            tex[off0 + k:off0 + k + 8] = enc[k:k + 8]
    img = new
    for w, off, n in levels()[1:]:
        if w < 4:
            break                       # the 2x2 and 1x1 levels: a colour average nobody sees; keep them
        img = img.resize((w, w), Image.BOX)
        e = encode(img)
        assert len(e) == n, (w, len(e), n)
        tex[off:off + n] = e
    return bytes(tex)


# ----------------------------------------------------------------------------- type


def font(px, weight=WEIGHT):
    f = ImageFont.truetype(FONT, px)
    try:
        f.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass                          # FreeType without variations: regular weight
    return f


def set_line(text, px, track, weight=WEIGHT):
    """Coverage image (L, supersampled SS times) of a line, and where its baseline is. track: extra space per letter."""
    f = font(px * SS, weight)
    asc, desc = f.getmetrics()
    w = int(sum(f.getlength(c) + track * SS for c in text)) + 4 * SS
    im = Image.new('L', (w, asc + desc + 4 * SS), 0)
    d = ImageDraw.Draw(im)
    x = 0.0
    for c in text:
        d.text((x, 0), c, font=f, fill=255)
        x += f.getlength(c) + track * SS
    return im, asc


def shrink(im):
    return im.resize((max(1, im.size[0] // SS), max(1, im.size[1] // SS)), Image.LANCZOS)


def ink_box(cov, thr=60):
    return cov.point(lambda v: 255 if v > thr else 0).getbbox()


def fit_size(text, height):
    """Font size whose ink from the top of the tallest letter to the bottom of the lowest equals `height`."""
    lo, hi = 6.0, 80.0
    for _ in range(30):
        mid = (lo + hi) / 2
        b = ink_box(shrink(set_line(text, mid, 0)[0]))
        if b[3] - b[1] < height:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fit_track(text, px, width):
    lo, hi = -2.0, 30.0
    for _ in range(30):
        mid = (lo + hi) / 2
        b = ink_box(shrink(set_line(text, px, mid)[0]))
        if b[2] - b[0] < width:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ----------------------------------------------------------------------------- finding the English line
def lum(im):
    return im.convert('L')


def letter_mask(pic, area, dark):
    """L image (area-sized): how strongly each pixel differs from the paper around it, in the letters' direction."""
    crop = lum(pic.crop(area))
    bg = crop.filter(ImageFilter.MedianFilter(11))
    diff = ImageChops.subtract(bg, crop) if dark else ImageChops.subtract(crop, bg)
    return diff, bg


def band(mask, x0, x1, thr):
    """Rows (top, bottom) of the line of letters, found where the line starts (the left part of the area).
    The paper's grain gives a few stray pixels per row; the letters give many more."""
    px = mask.load()
    w, h = mask.size
    rows = [sum(1 for x in range(x0, min(x1, w)) if px[x, y] > thr) for y in range(h)]
    peak = max(rows)
    if peak < 20:
        return None
    level = max(5, peak // 14)
    best = rows.index(peak)
    top = bot = best
    while top - 1 >= 0 and (rows[top - 1] >= level or (top - 2 >= 0 and rows[top - 2] >= level)):
        top -= 1
    while bot + 1 < h and (rows[bot + 1] >= level or (bot + 2 < h and rows[bot + 2] >= level)):
        bot += 1
    return top, bot + 1, rows


def first_col(mask, top, bot, thr):
    """First column of the line: ink in it and in at least two of the next three (a lone speck of grain is not a letter)."""
    px = mask.load()
    cols = [sum(1 for y in range(top, bot) if px[x, y] > thr) >= 3 for x in range(mask.size[0])]
    for x in range(len(cols) - 3):
        if cols[x] and sum(cols[x + 1:x + 4]) >= 2:
            return x
    return None


def words_extent(mask, top, bot, left, thr, max_gap):
    """Right edge of the run of letters that starts at `left`, allowing gaps up to max_gap (between words)."""
    px = mask.load()
    right, gap = left, 0
    for x in range(left, mask.size[0]):
        if sum(1 for y in range(top, bot) if px[x, y] > thr) >= 2:
            right, gap = x + 1, 0
        else:
            gap += 1
            if gap > max_gap:
                break
    return right


class Line:
    """One English line in the picture, and the type settings that reproduce it.

    style: (font size, letter spacing). All the screens use one style for the name and one for NOW LOADING
    (fitted once; measuring it per screen was less reliable than measuring the position).
    fixed: (left, cap top, right) for a line that sits in the same place on every screen (NOW LOADING); otherwise
    the position is found in the picture."""

    def __init__(self, pic, area, text, dark, thr, style, fixed=None):
        self.area, self.dark, self.text, self.thr = area, dark, text, thr
        self.diff, self.bg = letter_mask(pic, area, dark)
        self.px, self.track, self.weight = style
        cov, _ = set_line(text, self.px, self.track, self.weight)
        self.cov = cov = shrink(cov)
        ib = ink_box(cov)
        width = ib[2] - ib[0]
        if fixed:
            left, cap_top, self.right = fixed
            self.left = left
            self.ox, self.oy = left - ib[0], cap_top - ib[1]
            top, bot = cap_top, self.oy + ib[3]
        else:
            b = band(self.diff, 0, 300, thr)
            if not b:
                raise ValueError('no lettering found')
            btop, bbot, rows = b
            left = first_col(self.diff, btop, bbot, thr)
            if left is None:
                raise ValueError('no lettering found')
            # baseline: the row with the most ink, at the bottom of the letters, in both the picture and our setting
            base_pic = max(range(btop, bbot), key=lambda y: (rows[y], y))
            cp = cov.load()
            crow = [sum(1 for x in range(cov.size[0]) if cp[x, y] > 60) for y in range(cov.size[1])]
            base_set = max(range(len(crow)), key=lambda y: (crow[y], y))
            self.left = area[0] + left
            self.ox = self.left - ib[0]
            self.oy = area[1] + base_pic - base_set
            # from the first letter to where the English words set in our type end, plus a margin
            self.right = self.left + int(width * 1.08) + 8
            # ascenders and descenders reach past the band of most ink: take the set English letters' extent too
            top = min(area[1] + btop, self.oy + ib[1])
            bot = max(area[1] + bbot, self.oy + ib[3])
        self.top, self.bot = int(top), int(bot)

    def erase_mask(self):
        """Picture-sized mask (L): the letter pixels inside the English line's box."""
        box = (int(self.left) - 6, self.top - 4, int(self.right) + 6, self.bot + 4)
        x0, y0 = self.area[:2]
        found = self.diff.crop((box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0))
        found = found.point(lambda v: 255 if v > self.thr // 3 else 0)
        m = Image.new('L', (SIZE, SIZE), 0)
        m.paste(found, box[:2])
        return m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))

    def colour(self, pic, mask):
        """How the original letters change the paper: a factor per channel (dark) or an added colour (light)."""
        x0, y0, x1, y1 = self.area
        crop = pic.crop(self.area)
        bgc = crop.filter(ImageFilter.MedianFilter(11))
        p, b, m, dd = crop.load(), bgc.load(), mask.load(), self.diff.load()
        vals = []
        for y in range(y1 - y0):
            for x in range(x1 - x0):
                if m[x + x0, y + y0] > 200 and dd[x, y] > self.thr * 2:
                    vals.append((p[x, y], b[x, y]))
        if not vals:
            return (0.35, 0.3, 0.25) if self.dark else (120, 115, 70)

        def q(xs, f):
            xs = sorted(xs)
            return xs[int(len(xs) * f)]
        # the letters' cores, not their soft edges: the darkest / brightest quarter
        if self.dark:
            k = [q([min(1.0, pv[c] / max(1, bv[c])) for pv, bv in vals], 0.25) for c in range(3)]
            mean = sum(k) / 3
            # keep the tint near grey: where the paper is almost white in one channel the ratio runs away
            return tuple(min(mean + 0.1, max(mean - 0.1, max(0.2, v))) for v in k)
        return tuple(q([max(0, pv[c] - bv[c]) for pv, bv in vals], 0.75) for c in range(3))


# ----------------------------------------------------------------------------- painting
def repaint(pic, mask, area, grain_dy):
    """Paint the paper back where mask is set: smooth background + grain copied from grain_dy rows away."""
    x0, y0, x1, y1 = area
    pad = 12
    box = (max(0, x0 - pad), max(0, y0 - pad), min(SIZE, x1 + pad), min(PIC_H, y1 + pad))
    crop = pic.crop(box)
    m = mask.crop(box)
    w, h = crop.size
    # smooth background that ignores the letters: normalised blur (blur of known pixels / blur of the known mask),
    # from fine to coarse, each pass filling what the finer ones could not reach
    hole = m.point(lambda v: 255 if v > 10 else 0)
    known = ImageChops.invert(hole)
    fill = crop.copy()
    hp = hole.load()
    todo = [(x, y) for y in range(h) for x in range(w) if hp[x, y]]
    premul = ImageChops.multiply(crop, known.convert('RGB'))
    fp = fill.load()
    for r in (2, 4, 8, 16, 32):
        if not todo:
            break
        np_ = premul.filter(ImageFilter.GaussianBlur(r)).load()
        dp = known.filter(ImageFilter.GaussianBlur(r)).load()
        rest = []
        for x, y in todo:
            d = dp[x, y]
            if d > 40:
                n = np_[x, y]
                fp[x, y] = (min(255, n[0] * 255 // d), min(255, n[1] * 255 // d), min(255, n[2] * 255 // d))
            else:
                rest.append((x, y))
        todo = rest
    # paper grain: the fine detail of rows just outside the line
    sy = max(0, min(PIC_H - h, box[1] + grain_dy))
    near = pic.crop((box[0], sy, box[2], sy + h))
    detail = ImageChops.subtract(near, near.filter(ImageFilter.GaussianBlur(3)), 1, 128)
    filled = ImageChops.add(fill.filter(ImageFilter.GaussianBlur(1)), detail, 1, -128)
    pic.paste(Image.composite(filled, crop, m), box[:2])
    return box


def draw_dark(pic, line, text, factor):
    cov, _ = set_line(text, line.px, line.track, line.weight)
    cov = shrink(cov)
    x, y = int(round(line.ox)), int(round(line.oy))
    region = pic.crop((x, y, x + cov.size[0], y + cov.size[1]))
    p, c = region.load(), cov.load()
    for yy in range(cov.size[1]):
        for xx in range(cov.size[0]):
            a = c[xx, yy] / 255.0
            if a:
                p[xx, yy] = tuple(int(p[xx, yy][k] * (1 - a * (1 - factor[k]))) for k in range(3))
    pic.paste(region, (x, y))
    return (x, y, x + cov.size[0], y + cov.size[1])


def draw_light(pic, line, text, add):
    cov, _ = set_line(text, line.px, line.track, line.weight)
    cov = shrink(cov)
    x, y = int(round(line.ox)), int(round(line.oy))     # starts where NOW LOADING started
    glow = cov.filter(ImageFilter.GaussianBlur(3))
    region = pic.crop((x - 8, y - 8, x + cov.size[0] + 8, y + cov.size[1] + 8))
    p = region.load()
    full = Image.new('L', region.size, 0)
    full.paste(cov, (8, 8))
    fg = Image.new('L', region.size, 0)
    fg.paste(glow, (8, 8))
    c, gl = full.load(), fg.load()
    for yy in range(region.size[1]):
        for xx in range(region.size[0]):
            a = c[xx, yy] / 255.0 + 0.35 * gl[xx, yy] / 255.0
            if a:
                p[xx, yy] = tuple(min(255, int(p[xx, yy][k] + a * add[k])) for k in range(3))
    pic.paste(region, (x - 8, y - 8))
    return (x - 8, y - 8, x + cov.size[0] + 8, y + cov.size[1] + 8)


def union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def make(img, en, pt):
    """img: decoded level 0. Returns (new image, changed region, notes)."""
    pic = img.copy()
    notes = []
    name = Line(pic, NAME_AREA, en, True, 30, NAME_STYLE)
    load = Line(pic, LOAD_AREA, LOADING[0], False, 30, LOAD_STYLE, LOAD_PLACE)
    m1, m2 = name.erase_mask(), load.erase_mask()
    k1, k2 = name.colour(pic, m1), load.colour(pic, m2)
    r1 = repaint(pic, m1, m1.getbbox() or NAME_AREA, (name.cov.size[1] + 6))
    r2 = repaint(pic, m2, m2.getbbox() or LOAD_AREA, -(load.cov.size[1] + 6))
    region = union(r1, r2)
    if pt != en:
        region = union(region, draw_dark(pic, name, pt, k1))
    else:
        pic.paste(img.crop(r1), r1[:2])      # same name in both languages: keep the original lettering
    region = union(region, draw_light(pic, load, LOADING[1], k2))
    notes.append('name %.1fpx track %.2f colour %s; loading %.1fpx track %.2f colour %s' % (
        name.px, name.track, tuple(round(v, 2) for v in k1), load.px, load.track, tuple(int(v) for v in k2)))
    return pic, region, notes


def run(src_dir, out_dir, preview=None, only=None):
    os.makedirs(out_dir, exist_ok=True)
    done = 0
    for key, (en, pt) in SCREENS.items():
        if only and key not in only:
            continue
        path = os.path.join(src_dir, key + '.tpf')
        if not os.path.exists(path):
            print('  %s.tpf not found, skipped' % key)
            continue
        data = bytearray(open(path, 'rb').read())
        ents = g.tpf_entries(bytes(data))
        if len(ents) != 1 or (ents[0]['w'], ents[0]['h'], ents[0]['fmt']) != (SIZE, SIZE, 0) \
                or ents[0]['size'] != sum(n for _, _, n in levels()):
            print('  %s.tpf is not the usual loading screen (another mod?), left as it is' % key)
            continue
        e = ents[0]
        tex = bytes(data[e['off']:e['off'] + e['size']])
        img = decode(tex)
        try:
            new, region, notes = make(img, en, pt)
        except ValueError as ex:
            print('  %s: %s, left as it is' % (key, ex))
            continue
        data[e['off']:e['off'] + e['size']] = write_texture(tex, new, region)
        open(os.path.join(out_dir, key + '.tpf'), 'wb').write(bytes(data))
        done += 1
        print('     %s %s' % (key, pt), flush=True)
        if os.environ.get('PTBR_PROGRESS'):
            print('@@' + json.dumps(dict(step='loading', n=done, total=len(SCREENS), screen=key), ensure_ascii=False),
                  flush=True)
        if preview:
            new.crop((0, 0, SIZE, PIC_H)).save(os.path.join(preview, key + '_ptbr.png'))
            print('  %s %s' % (key, notes[0]))
    return done


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--preview')
    ap.add_argument('--only')
    a = ap.parse_args()
    n = run(a.src, a.dst, a.preview, a.only.split(',') if a.only else None)
    print('   loading screens translated: %d of %d' % (n, len(SCREENS)))
