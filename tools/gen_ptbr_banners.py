#!/usr/bin/env python3
"""Portuguese versions of the big on-screen messages ("YOU DIED" and the rest), made on the player's PC.

    gen_ptbr_banners.py MENU_TPF OUT_TPF [--preview DIR]

MENU_TPF  the game's menu/menu.tpf (plain, already decoded from .dcx)
OUT_TPF   the same file with the five banner textures replaced

The letters are cut from the game's own banner textures, so the result keeps the original lettering and colours.
Letters the originals do not contain are derived: F from E, and the accents are drawn in the same colour.
Nothing from the game is stored in this repository. Needs Pillow (bundled with the installer's Python).
"""
import argparse
import io
import os
import struct
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_ptbr_glyphs as g  # noqa: E402

# texture: [(x0, x1, English it shows, Portuguese)]; x0..x1 is the part of the texture a sprite of menu.drb shows
BANNERS = {
    'Menu14': [(0, 1024, 'THE DEMON WAS DESTROYED', 'DEMÔNIO DESTRUÍDO')],
    'Menu15': [(0, 440, 'YOU DIED', 'VOCÊ MORREU'), (440, 1024, 'YOU REVIVED', 'VOCÊ REVIVEU')],
    'Menu16': [(0, 1024, 'YOU REGAINED LOST SOUL', 'ALMA PERDIDA RECUPERADA')],
    'Menu17': [(0, 1024, 'TARGET WAS DESTROYED', 'ALVO DESTRUÍDO')],
    'Menu18': [(0, 1024, 'BLACK PHANTOM WAS DESTROYED', 'ESPECTRO ESCURO DESTRUÍDO')],
}
INK = 40          # brightness above which a pixel is part of a letter
W, H = 1024, 128


def dds_header(w, h, fourcc, size):
    hdr = b'DDS ' + struct.pack('<7I', 124, 0x81007, h, w, size, 0, 0) + b'\0' * 44
    return hdr + struct.pack('<2I4s5I', 32, 4, fourcc, 0, 0, 0, 0, 0) + struct.pack('<5I', 0x1000, 0, 0, 0, 0)


def decode(tex):
    return Image.open(io.BytesIO(dds_header(W, H, b'DXT1', len(tex)) + tex)).convert('RGB')


def encode(img):
    b = io.BytesIO()
    img.convert('RGBA').save(b, 'DDS', pixel_format='DXT1')
    data = b.getvalue()[128:]
    assert len(data) == W * H // 2, len(data)
    return data


def columns(img, x0, x1):
    """Runs of columns that contain ink, between x0 and x1."""
    px = img.load()
    runs, start = [], None
    for x in range(x0, x1):
        on = any(max(px[x, y]) > INK for y in range(H))
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, x1))
    return runs


def split_touching(img, runs, want):
    """Letters that touch make one run; split the widest run at its faintest column until the count matches."""
    px = img.load()
    runs = list(runs)
    while len(runs) < want:
        i = max(range(len(runs)), key=lambda k: runs[k][1] - runs[k][0])
        a, b = runs[i]
        if b - a < 20:
            break
        lo, hi = a + (b - a) // 4, b - (b - a) // 4
        cut = min(range(lo, hi), key=lambda x: sum(max(px[x, y]) for y in range(H)))
        runs[i:i + 1] = [(a, cut), (cut + 1, b)]
    return runs


def rows_of(img, x0, x1):
    px = img.load()
    ys = [y for y in range(H) if any(max(px[x, y]) > INK for x in range(x0, x1))]
    return ys[0], ys[-1] + 1


def colour_ramp(img, x0, x1, top, bot):
    """The message's brightest colour on each row."""
    px = img.load()
    ramp = []
    for y in range(top, bot):
        best = (0, (255, 255, 255))
        for x in range(x0, x1):
            c = px[x, y]
            if max(c) > best[0]:
                best = (max(c), c)
        ramp.append(best[1])          # the original's own colour and brightness on that row
    return ramp


class Letters:
    """Grey letter shapes cut from all banners, so a missing letter can come from another banner."""

    def __init__(self, tex):
        self.by = {}      # letter -> list of (texture name, grey image, gap after it)
        self.gaps = {}    # texture -> (letter gap, word gap)
        for name, parts in BANNERS.items():
            img = tex[name]
            for x0, x1, en, _pt in parts:
                runs = columns(img, x0, x1)
                letters = en.replace(' ', '')
                runs = split_touching(img, runs, len(letters))
                if len(runs) != len(letters):
                    continue           # could not separate the letters: this one only lends its colours
                top, bot = rows_of(img, x0, x1)
                gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
                words = en.split(' ')
                ends = set()
                k = 0
                for wd in words[:-1]:
                    k += len(wd)
                    ends.add(k - 1)
                lg = [gp for i, gp in enumerate(gaps) if i not in ends]
                wg = [gp for i, gp in enumerate(gaps) if i in ends]
                self.gaps[name] = (sorted(lg)[len(lg) // 2], sorted(wg)[len(wg) // 2] if wg else 30)
                for (a, b), ch in zip(runs, letters):
                    grey = img.crop((a, top, b, bot)).convert('L')
                    peak = grey.getextrema()[1] or 1
                    grey = grey.point(lambda v, m=peak: min(255, v * 255 // m))   # every letter at full strength
                    self.by.setdefault(ch, []).append((name, grey))
        f = self.make_f()
        if f:
            self.by['F'] = [f]

    def make_f(self):
        if 'E' not in self.by:
            return None
        name, e = self.by['E'][0]
        f = e.copy()
        w, h = f.size
        d = ImageDraw.Draw(f)
        d.rectangle([int(w * 0.42), int(h * 0.72), w, h], fill=0)   # drop the lower arm
        return name, f

    def get(self, ch, prefer, height):
        options = self.by.get(ch)
        if not options:
            raise SystemExit('no letter %r in the game banners' % ch)
        name, grey = next((o for o in options if o[0] == prefer), options[0])
        if grey.size[1] != height:
            grey = grey.resize((max(1, round(grey.size[0] * height / grey.size[1])), height), Image.LANCZOS)
        return grey


BASE = {'Ê': ('E', 'circ'), 'Ô': ('O', 'circ'), 'Í': ('I', 'acute'), 'Ú': ('U', 'acute'), 'Ã': ('A', 'tilde')}


def accent(kind, w, size):
    m = Image.new('L', (w, size), 0)
    d = ImageDraw.Draw(m)
    t = max(3, size // 4)
    cx = w // 2
    if kind == 'circ':
        d.line([(cx - size, size - 2), (cx, 2), (cx + size, size - 2)], fill=255, width=t, joint='curve')
    elif kind == 'acute':
        d.line([(cx - size // 3, size - 2), (cx + size // 2, 2)], fill=255, width=t)
    return m


def compose(letters, name, text, top, bot, ramp, span):
    """Grey image of the Portuguese line, the letters' height as in the original."""
    height = bot - top
    lg, wg = letters.gaps.get(name, (6, 30))
    acc = max(10, height // 4)
    pieces = []
    for ch in text:
        if ch == ' ':
            pieces.append(('gap', wg))
            continue
        base, kind = BASE.get(ch, (ch, None))
        gl = letters.get(base, name, height)
        if kind:
            full = Image.new('L', (gl.size[0], height + acc + 4), 0)
            full.paste(gl, (0, acc + 4))
            full.paste(accent(kind, gl.size[0], acc), (0, 0))
            gl = full
        pieces.append(('glyph', gl))
    total = sum(p[1] if p[0] == 'gap' else p[1].size[0] + lg for p in pieces) - lg
    out = Image.new('L', (max(total, 1), height + acc + 4), 0)
    x = 0
    for kind, p in pieces:
        if kind == 'gap':
            x += p
            continue
        out.paste(p, (x, out.size[1] - p.size[1]), p)
        x += p.size[0] + lg
    if out.size[0] > span:      # too long for the room: narrow it a little
        out = out.resize((span, out.size[1]), Image.LANCZOS)
    return out, acc + 4


def paint(img, grey, x_center, top, acc, ramp):
    """Colour the grey line with the original's per-row colour and draw it, centred where the original was."""
    w, h = grey.size
    x0 = x_center - w // 2
    y0 = top - acc
    px = img.load()
    gp = grey.load()
    for y in range(h):
        c = ramp[min(max(y - acc, 0), len(ramp) - 1)]
        for x in range(w):
            v = gp[x, y]
            if v and 0 <= x0 + x < W and 0 <= y0 + y < H:
                b = px[x0 + x, y0 + y]
                px[x0 + x, y0 + y] = tuple((cc * v + bb * (255 - v)) // 255 for cc, bb in zip(c, b))


def run(src, dst, preview=None):
    data = bytearray(open(src, 'rb').read())
    ents = {e['name']: e for e in g.tpf_entries(bytes(data))}
    tex = {n: decode(bytes(data[ents[n]['off']:ents[n]['off'] + ents[n]['size']])) for n in BANNERS}
    letters = Letters(tex)
    for name, parts in BANNERS.items():
        orig = tex[name]
        new = orig.copy()
        for x0, x1, _en, pt in parts:
            runs = columns(orig, x0, x1)
            top, bot = rows_of(orig, x0, x1)
            ramp = colour_ramp(orig, x0, x1, top, bot)
            left, right = runs[0][0], runs[-1][1]
            bg = orig.getpixel((x0 + 2, 2))          # the texture's own background, not always black
            ImageDraw.Draw(new).rectangle([x0, 0, x1 - 1, H - 1], fill=bg)
            grey, acc = compose(letters, name, pt, top, bot, ramp, (x1 - x0) - 16)
            paint(new, grey, (left + right) // 2, top, acc, ramp)
        enc = encode(new)
        e = ents[name]
        data[e['off']:e['off'] + e['size']] = enc
        if preview:
            new.save(os.path.join(preview, name + '_ptbr.png'))
    open(dst, 'wb').write(bytes(data))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--preview')
    a = ap.parse_args()
    run(a.src, a.dst, a.preview)
