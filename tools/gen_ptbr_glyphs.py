#!/usr/bin/env python3
"""Derive accented Latin glyphs from the game's OWN font glyphs (prototype).

Original code (project rule): this tool is committed, its OUTPUT is not.
Reads, from the user's own dump (read-only):  USRDIR/font/na_english/<font>.ccm and <font>.tpf
Writes, to an output folder OUTSIDE the repository:
    <out>/font/na_english/<font>.ccm   (glyph table with extra code groups + glyph records)
    <out>/font/na_english/<font>.tpf   (same bytes as the original, plus new glyph cells in the free band)
    <out>/report_<font>.txt            (capacity, metrics, list of generated characters)
    <out>/preview_<font>_atlas.png, preview_<font>_new.png   (alpha previews, local only)
No glyph bitmap is embedded in this file: every pixel comes from the player's own atlas.

Format facts this relies on (docs/fonts.md): CCM big-endian; header 0x20 bytes; code groups
(first, last, first glyph index) u32 x3 at ogrp; glyph records of 24 bytes at oreg:
f32 u0 v0 u1 v1 (normalised), u16 left-pad, width, advance, texture index. TPF texture: DXT5 with a
full mip chain (no byte swapping of the DXT blocks).

usage: gen_ptbr_glyphs.py <USRDIR> <outdir> [--set ptbr|latin1] [--fonts dsfont24 talkfont24]
                          [--mark-rows 3]
"""
import struct, sys, os, zlib, unicodedata, argparse

TEX = 512
CELL = 26                      # glyph cell height in the atlas (font height field of the CCM)
BAND_Y0 = 392                  # first free row (multiple of 4) below the last used glyph row (391)
PTBR = "áâãàçéêíóôõú" "ÁÂÃÀÇÉÊÍÓÔÕÚ" "üÜ" "ªº"
MARKS = {0: 'ord', 0x300: 'grave', 0x301: 'acute', 0x302: 'circ', 0x303: 'tilde', 0x308: 'diaer', 0x30A: 'ring', 0x327: 'cedilla'}
MARK_SRC = {'grave': 0x60, 'acute': 0xB4, 'tilde': 0x7E, 'diaer': 0xA8, 'ring': 0xB0, 'cedilla': 0x2C}


# ----------------------------------------------------------------------------- PNG (alpha preview)
def write_png(path, w, h, rows):
    """rows: list of bytes, one per line, 8-bit greyscale."""
    raw = b''.join(b'\0' + bytes(r) for r in rows)
    def ch(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
                           + ch(b'IDAT', zlib.compress(raw, 6)) + ch(b'IEND', b''))


# ----------------------------------------------------------------------------- CCM
class Ccm:
    def __init__(self, b):
        self.raw = b
        (self.ver, self.size, self.height, self.tw, self.th, self.unk0e, self.ngrp, self.nglyph,
         self.ogrp, self.oreg) = struct.unpack_from('>IIHHHHHHII', b, 0)
        self.groups = [struct.unpack_from('>III', b, self.ogrp + 12 * i) for i in range(self.ngrp)]
        self.glyph_bytes = b[self.oreg:self.oreg + 24 * self.nglyph]
        self.tail = b[self.oreg + 24 * self.nglyph:]
        assert self.ogrp == 0x20 and self.oreg == 0x20 + 12 * self.ngrp and not self.tail, 'unexpected CCM layout'

    def index(self, cp):
        for a, e, g in self.groups:
            if a <= cp <= e:
                return g + cp - a
        return None

    def glyph(self, i):
        u0, v0, u1, v1 = struct.unpack_from('>ffff', self.glyph_bytes, 24 * i)
        pad, w, adv, tex = struct.unpack_from('>HHHH', self.glyph_bytes, 24 * i + 16)
        return dict(rect=(round(u0 * self.tw), round(v0 * self.th), round(u1 * self.tw), round(v1 * self.th)),
                    pad=pad, w=w, adv=adv, tex=tex)

    def codepoints(self):
        s = set()
        for a, e, g in self.groups:
            s.update(range(a, e + 1))
        return s

    def build(self, new):
        """new: sorted list of (codepoint, rect, pad, w, adv, tex). Returns new CCM bytes."""
        groups = list(self.groups)
        recs = bytearray(self.glyph_bytes)
        gi = self.nglyph
        run = None
        for cp, (x0, y0, x1, y1), pad, w, adv, tex in new:
            recs += struct.pack('>ffffHHHH', x0 / self.tw, y0 / self.th, x1 / self.tw, y1 / self.th, pad, w, adv, tex)
            if run and run[1] + 1 == cp:
                run[1] = cp
            else:
                run = [cp, cp, gi]
                groups.append(run)
            gi += 1
        groups = sorted((tuple(g) for g in groups), key=lambda g: g[0])
        ngrp = len(groups)
        head = bytearray(self.raw[:0x20])
        oreg = 0x20 + 12 * ngrp
        size = oreg + len(recs)
        struct.pack_into('>I', head, 4, size)
        struct.pack_into('>H', head, 0x10, ngrp)
        struct.pack_into('>H', head, 0x12, gi)
        struct.pack_into('>I', head, 0x18, oreg)
        return bytes(head) + b''.join(struct.pack('>III', *g) for g in groups) + bytes(recs)


# ----------------------------------------------------------------------------- TPF + DXT5 (alpha only)
def tpf_entries(d):
    assert d[:4] == b'TPF\0'
    n = struct.unpack('>I', d[8:12])[0]
    out = []
    for i in range(n):
        o = 16 + 32 * i
        off, size = struct.unpack('>II', d[o:o + 8])
        w, h = struct.unpack('>HH', d[o + 12:o + 16])
        noff = struct.unpack('>I', d[o + 24:o + 28])[0]
        out.append(dict(off=off, size=size, fmt=d[o + 8], w=w, h=h, name=d[noff:d.index(b'\0', noff)].decode('ascii', 'replace')))
    return out


def level_layout(w, h):
    """[(w, h, byte offset, byte size)] for a DXT5 mip chain down to 1x1 (one 16-byte block per level < 4)."""
    out, off = [], 0
    while True:
        sz = max(1, w // 4) * max(1, h // 4) * 16
        out.append((w, h, off, sz)); off += sz
        if w == 1 and h == 1:
            return out
        w, h = max(1, w // 2), max(1, h // 2)


def dxt5_alpha_block(blk):
    a0, a1 = blk[0], blk[1]
    pal = [a0, a1] + ([((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)] if a0 > a1
                      else [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255])
    bits = int.from_bytes(blk[2:8], 'little')
    return [pal[(bits >> (3 * i)) & 7] for i in range(16)]


def decode_alpha(data, w, h):
    img = [bytearray(w) for _ in range(h)]
    bw = max(1, w // 4)
    for b in range(max(1, w // 4) * max(1, h // 4)):
        bx, by = (b % bw) * 4, (b // bw) * 4
        al = dxt5_alpha_block(data[b * 16:b * 16 + 8])
        for i in range(16):
            x, y = bx + (i & 3), by + (i >> 2)
            if x < w and y < h:
                img[y][x] = al[i]
    return img


def decode_lum(data, w, h):
    """Grey level (0..255) of the BC1 colour half of every pixel. talkfont24 carries the letter's inner detail in the colour
    channel (bright strokes, dark fill), so a glyph built from the alpha channel alone draws as a solid blob in the game."""
    def c565(v):
        r, g, b = v >> 11 & 31, v >> 5 & 63, v & 31
        return (r * 255 // 31 + g * 255 // 63 + b * 255 // 31) // 3
    img = [bytearray(w) for _ in range(h)]
    bw = max(1, w // 4)
    for b in range(max(1, w // 4) * max(1, h // 4)):
        bx, by = (b % bw) * 4, (b // bw) * 4
        blk = data[b * 16 + 8:b * 16 + 16]
        c0, c1 = struct.unpack_from('<HH', blk, 0)
        a, z = c565(c0), c565(c1)
        pal = [a, z, (2 * a + z) // 3, (a + 2 * z) // 3] if c0 > c1 else [a, z, (a + z) // 2, 0]
        idx = struct.unpack_from('<I', blk, 4)[0]
        for i in range(16):
            x, y = bx + (i & 3), by + (i >> 2)
            if x < w and y < h:
                img[y][x] = pal[(idx >> (2 * i)) & 3]
    return img


EMPTY_COLOR = bytes.fromhex('0100000055555555')


def encode_color_block(lums, alphas):
    """BC1 colour half for a block: c0 = brightest grey among the ink pixels, c1 = 0, per-pixel nearest of the 4 levels."""
    ink = [l for l, a in zip(lums, alphas) if a]
    gmax = max(ink) if ink else 0
    if gmax < 8:
        return EMPTY_COLOR
    r5 = max(1, min(31, int(round(gmax * 31 / 255.0))))
    g6 = max(1, min(63, int(round(gmax * 63 / 255.0))))
    c0 = (r5 << 11) | (g6 << 5) | r5
    top = (r5 * 255 // 31 + g6 * 255 // 63 + r5 * 255 // 31) // 3
    pal = [top, 0, (2 * top) // 3, top // 3]
    bits = 0
    for i, (l, a) in enumerate(zip(lums, alphas)):
        k = min(range(4), key=lambda q: abs(pal[q] - (l if a else 0)))
        bits |= k << (2 * i)
    return struct.pack('<HHI', c0, 0, bits)


def encode_alpha_block(vals):
    lo, hi = min(vals), max(vals)
    if lo == hi:
        a0, a1, idx = hi, lo, [0] * 16
    else:
        a0, a1 = hi, lo
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
        idx = [min(range(8), key=lambda k: abs(pal[k] - v)) for v in vals]
    bits = sum(k << (3 * i) for i, k in enumerate(idx))
    return bytes((a0, a1)) + bits.to_bytes(6, 'little')


def downsample(img, w, h):
    nw, nh = max(1, w // 2), max(1, h // 2)
    out = []
    for y in range(nh):
        r0, r1 = img[min(2 * y, h - 1)], img[min(2 * y + 1, h - 1)]
        out.append(bytearray((r0[min(2 * x, w - 1)] + r0[min(2 * x + 1, w - 1)] + r1[min(2 * x, w - 1)] + r1[min(2 * x + 1, w - 1)] + 2) // 4
                             for x in range(nw)))
    return out, nw, nh


def patch_texture(tex, atlas, lum, region):
    """tex: original DXT5 bytes with mip chain. atlas / lum: new level-0 alpha and grey planes. region: (x0,y0,x1,y1) changed in
    level 0. Only blocks that overlap the region (at each mip level) are re-encoded; everything else stays byte-identical."""
    out = bytearray(tex)
    img, limg, w, h = atlas, lum, TEX, TEX
    for lw, lh, off, sz in level_layout(TEX, TEX):
        if (lw, lh) != (w, h):
            img, _, _ = downsample(img, w, h)
            limg, w, h = downsample(limg, w, h)
        lvl = level_layout(TEX, TEX).index((lw, lh, off, sz))
        x0, y0, x1, y1 = (region[0] >> lvl, region[1] >> lvl, (region[2] + (1 << lvl) - 1) >> lvl, (region[3] + (1 << lvl) - 1) >> lvl)
        bw = max(1, lw // 4)
        for by in range(y0 // 4, (max(y1, y0 + 1) - 1) // 4 + 1):
            for bx in range(x0 // 4, (max(x1, x0 + 1) - 1) // 4 + 1):
                pos = [(min(by * 4 + (i >> 2), lh - 1), min(bx * 4 + (i & 3), lw - 1)) for i in range(16)]
                vals = [img[r][c] for r, c in pos]
                lums = [limg[r][c] for r, c in pos]
                o = off + (by * bw + bx) * 16
                out[o:o + 16] = encode_alpha_block(vals) + encode_color_block(lums, vals)
    return bytes(out)


# ----------------------------------------------------------------------------- glyph bitmaps
def crop(atlas, rect):
    x0, y0, x1, y1 = rect
    return [bytearray(atlas[y][x0:x1]) for y in range(y0, y1)]


def ink_bbox(g):
    rows = [y for y, r in enumerate(g) if any(r)]
    cols = [x for x in range(len(g[0])) if any(r[x] for r in g)]
    return (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1) if rows else None


def trim(g):
    x0, y0, x1, y1 = ink_bbox(g)
    return [bytearray(r[x0:x1]) for r in g[y0:y1]]


def resample_rows(g, dst_h):
    """Area-average vertical resample of a bitmap (list of rows) to dst_h rows."""
    src_h, w = len(g), len(g[0])
    if src_h == dst_h:
        return [bytearray(r) for r in g]
    s = src_h / dst_h
    out = []
    for j in range(dst_h):
        a, b = j * s, (j + 1) * s
        acc = [0.0] * w
        y = int(a)
        while y < b and y < src_h:
            wgt = min(b, y + 1) - max(a, y)
            for x in range(w):
                acc[x] += g[y][x] * wgt
            y += 1
        out.append(bytearray(min(255, int(round(v / s))) for v in acc))
    return out


def blank(w, h=CELL):
    return [bytearray(w) for _ in range(h)]


def blit(dst, src, x, y):
    for j, r in enumerate(src):
        if not 0 <= y + j < len(dst):
            continue
        for i, v in enumerate(r):
            if 0 <= x + i < len(dst[0]) and v:
                dst[y + j][x + i] = max(dst[y + j][x + i], v)


def remove_dot(g):
    """Dotless i/j: find the narrowest row (the neck) just below the dot and blank everything above it, neck included."""
    ys = [y for y, r in enumerate(g) if any(v > 24 for v in r)]
    lo, hi = ys[0] + 1, ys[0] + max(2, (ys[-1] - ys[0]) // 2)
    neck = min(range(lo, hi + 1), key=lambda y: sum(g[y]))
    out = [bytearray(r) for r in g]
    for k in range(0, neck + 1):
        out[k] = bytearray(len(g[0]))
    return out


def measure(ccm, atlas):
    """Vertical metrics measured from the font's own letters: cap top, baseline (last ink row of H), x-height top (o)."""
    def rows(ch):
        bb = ink_bbox(crop(atlas, ccm.glyph(ccm.index(ord(ch)))['rect']))
        return bb[1], bb[3] - 1
    return dict(cap_top=rows('H')[0], baseline=rows('H')[1], x_top=rows('o')[0])


def stroke_weight(g):
    """Approximate pen thickness (px) of a mark glyph: ink area divided by its diagonal length."""
    area = sum(sum(r) for r in g) / 255.0
    return max(1.0, area / max(1.0, (len(g[0]) ** 2 + len(g) ** 2) ** 0.5))


def draw_mark(kind, w, h, thick, ss=6):
    """Anti-aliased tilde / circumflex drawn as a polyline with the font's own stroke weight (supersampled)."""
    import math
    if kind == 'circ':
        pts = [(thick / 2, h - thick / 2), (w / 2.0, thick / 2), (w - thick / 2, h - thick / 2)]
    else:   # tilde: one sine period, rising then falling
        amp = max(0.0, (h - thick) / 2.0)
        pts = [(thick / 2 + (w - thick) * i / 16.0, h / 2.0 - amp * math.sin(2 * math.pi * i / 16.0)) for i in range(17)]
    segs = list(zip(pts, pts[1:]))
    def dist(px, py):
        best = 1e9
        for (x0, y0), (x1, y1) in segs:
            dx, dy = x1 - x0, y1 - y0
            t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(px - x0 - t * dx, py - y0 - t * dy))
        return best
    out = []
    for y in range(h):
        row = bytearray(w)
        for x in range(w):
            hit = sum(1 for j in range(ss) for i in range(ss) if dist(x + (i + .5) / ss, y + (j + .5) / ss) <= thick / 2)
            row[x] = min(255, hit * 255 // (ss * ss) * 1)
        out.append(row)
    return out


class Marks:
    """Accent marks cut from the game's own punctuation glyphs (same stroke weight by construction)."""
    def __init__(self, ccm, atlas):
        self.m = {}
        for name, cp in MARK_SRC.items():
            self.m[name] = trim(crop(atlas, ccm.glyph(ccm.index(cp))['rect']))
        # circumflex = acute (/) next to grave (\) : same strokes, no new artwork
        a, g = self.m['acute'], self.m['grave']
        c = blank(len(a[0]) + len(g[0]), len(a))
        blit(c, a, 0, 0); blit(c, g, len(a[0]), 0)
        self.m['circ'] = c
        self.thick = stroke_weight(self.m['acute'])
        # cedilla: the tail of the comma (drop its round head)
        comma = self.m['cedilla']
        self.m['cedilla'] = comma[max(0, len(comma) - 4):]

    def get(self, name, rows=None):
        g = self.m[name]
        return resample_rows(g, rows) if rows and len(g) > rows else g


def pad1(g):
    w = len(g[0]) + 2
    return [bytearray(w)] + [bytearray(1) + r + bytearray(1) for r in g] + [bytearray(w)]


def dilate(g):
    """Grow ink by one pixel in every direction (3x3 maximum): the dark outline ring of an outlined font."""
    h, w = len(g), len(g[0])
    return [bytearray(max(g[yy][xx] for yy in range(max(0, y - 1), min(h, y + 2))
                          for xx in range(max(0, x - 1), min(w, x + 2))) for x in range(w)) for y in range(h)]


def compose(base_ch, mark, ccm, atlas, marks, met, mark_rows, outline=False, plane='alpha'):
    """Return (cell rows of width = base rect width, base glyph record) for base_ch + mark.

    outline: the font draws every letter as a bright core inside a dark one-pixel ring (talkfont24, the subtitle and
    dialogue face). Drawn marks (tilde, circumflex) then get the same: the core on the colour plane, the core grown by
    one pixel on the alpha plane, so the ring shows dark like the letters' own (play test 2026-11-10: thin grey marks
    with no outline looked faded next to the letters)."""
    bg = ccm.glyph(ccm.index(ord(base_ch)))
    cell = crop(atlas, bg['rect'])
    W = bg['rect'][2] - bg['rect'][0]
    upper = base_ch.isupper()
    if base_ch in 'ij':
        cell = remove_dot(cell)
    if mark == 'ord':        # feminine/masculine ordinal indicator: the letter at ~60% size, raised, with an underline
        bb0 = ink_bbox(cell)
        letter = [bytearray(r[bb0[0]:bb0[2]]) for r in cell[bb0[1]:bb0[3]]]
        sw = max(3, int(round(len(letter[0]) * 0.62))); sh = max(4, int(round(len(letter) * 0.62)))
        cols = resample_rows([bytearray(c) for c in zip(*letter)], sw)          # shrink width (transpose trick)
        letter = [bytearray(r) for r in zip(*cols)]
        letter = resample_rows(letter, sh)
        cell = blank(W)
        top = max(met['cap_top'] + 1, 0)
        blit(cell, letter, (W - sw) // 2, top)
        blit(cell, [bytearray([255] * sw)], (W - sw) // 2, top + sh + 1)
        return cell, bg
    bb = ink_bbox(cell)
    cx = (bb[0] + bb[2]) / 2.0
    if mark == 'cedilla':
        m = marks.get('cedilla')
        blit(cell, m, int(round(cx - len(m[0]) / 2.0)) + 1, met['baseline'])    # hangs under the baseline
        return cell, bg
    inkw = bb[2] - bb[0]
    def get_mark(rows):
        if mark in ('circ', 'tilde'):
            mw = max(5, min(10, int(round(inkw * 0.8))))
            if outline:
                # ring on the sides and below only: the cell has no room above the mark, and the ring below is what
                # keeps it apart from the letter; the core keeps rows - 1 rows so the shape stays a real tilde/caret
                core = draw_mark(mark, mw - 2, max(3, rows - 1), 1.6 if mark == 'tilde' else 1.8)
                core = pad1(core)[1:]
                return dilate(core) if plane == 'alpha' else core
            return draw_mark(mark, mw, rows, min(marks.thick, 1.5 if mark == 'tilde' else 1.7))
        return marks.get(mark, rows)
    if upper:
        # capitals have only 2 empty rows above them: squash the capital to make room (see docs/fonts.md)
        cap_top = mark_rows + 1                                          # mark rows, one empty row, then the capital
        top, bot = bb[1], bb[3]
        if top < cap_top:                                                # not enough headroom: squash the capital
            sq = resample_rows([r for r in cell[top:bot]], bot - cap_top)
            cell = blank(W)
            blit(cell, sq, 0, cap_top)
        m = get_mark(mark_rows)
        y = 0
    else:
        avail = bb[1] - 1                                                # rows above the letter, minus one empty row
        # bold face with little headroom (talkfont24: letter top at row 6): leave TWO empty rows, otherwise the mark
        # merges with the letter when the game scales the text down (in-game blob on a-tilde, 2026-11-06)
        gap = 2 if avail <= 5 else 1
        drawn = mark in ('circ', 'tilde')
        if outline and drawn:
            gap = 1          # the dark ring itself keeps the mark apart from the letter
        m = get_mark(min(avail - (gap - 1), (5 if outline else 4) if drawn else 5))
        y = bb[1] - gap - len(m)                                         # mark bottom sits `gap` empty rows above the letter
    blit(cell, m, int(round(cx - len(m[0]) / 2.0)), y)
    return cell, bg


# ----------------------------------------------------------------------------- driver
def targets(kind, have):
    out = [(0xAA, 'a', 'ord'), (0xBA, 'o', 'ord')] if kind == 'ptbr' and 0xAA not in have else []
    pool = PTBR if kind == 'ptbr' else ''.join(chr(c) for c in range(0xC0, 0x100))
    for ch in pool.replace('ªº', ''):
        d = unicodedata.normalize('NFD', ch)
        if len(d) == 2 and ord(d[1]) in MARKS and ord(ch) not in have and d[0].isascii():
            out.append((ord(ch), d[0], MARKS[ord(d[1])]))
    return sorted(set(out))


def render_line(text, ccm, atlas, scale=1):
    """Lay out text with CCM metrics (pen += advance, glyph at pen + left-pad). Returns rows of alpha."""
    W = sum(ccm.glyph(ccm.index(ord(c)))['adv'] for c in text if ccm.index(ord(c)) is not None) + 8
    img = blank(W + 8, CELL + 4)
    pen = 2
    for c in text:
        i = ccm.index(ord(c))
        if i is None:
            continue
        g = ccm.glyph(i)
        blit(img, crop(atlas, g['rect']), pen + g['pad'], 2)
        pen += g['adv']
    return img


def run(usr, out, kind, fonts, mark_rows):
    os.makedirs(os.path.join(out, 'font', 'na_english'), exist_ok=True)
    for font in fonts:
        base = os.path.join(usr, 'font', 'na_english', font)
        ccm = Ccm(open(base + '.ccm', 'rb').read())
        tpf = open(base + '.tpf', 'rb').read()
        ents = tpf_entries(tpf)
        glyph_tex = ccm.glyph(ccm.index(ord('A')))['tex']
        ent = ents[glyph_tex]      # CCM texture index == TPF entry order (dsfont24: 0 = buttons, 1 = letters)
        tex = tpf[ent['off']:ent['off'] + ent['size']]
        atlas = decode_alpha(tex, TEX, TEX)
        # colour plane (grey), kept non-zero exactly where alpha is non-zero so the same compose() geometry applies to it;
        # a dark ink pixel is stored as 1 and mapped back to 0 when the texture is encoded
        raw_lum = decode_lum(tex, TEX, TEX)
        latlas = [bytearray((max(1, raw_lum[y][x]) if atlas[y][x] else 0) for x in range(TEX)) for y in range(TEX)]
        used_bottom = max(ccm.glyph(i)['rect'][3] for i in range(ccm.nglyph) if ccm.glyph(i)['tex'] == glyph_tex)
        marks = Marks(ccm, atlas)
        marks_l = Marks(ccm, latlas)
        met = measure(ccm, atlas)
        have = ccm.codepoints()
        todo = targets(kind, have)
        new, x, y, rep = [], 0, BAND_Y0, []
        region = [TEX, TEX, 0, 0]
        for cp, b, m in todo:
            outline = font == 'talkfont24'
            cell, bg = compose(b, m, ccm, atlas, marks, met, mark_rows, outline, 'alpha')
            lcell, _ = compose(b, m, ccm, latlas, marks_l, met, mark_rows, outline, 'lum')
            W = len(cell[0])
            if x + W > TEX:
                x, y = 0, y + CELL
            if y + CELL > TEX:
                rep.append('OUT OF SPACE at U+%04X' % cp); break
            for j in range(CELL):
                atlas[y + j][x:x + W] = cell[j]
                latlas[y + j][x:x + W] = lcell[j]
            region = [min(region[0], x), min(region[1], y), max(region[2], x + W), max(region[3], y + CELL)]
            new.append((cp, (x, y, x + W, y + CELL), bg['pad'], bg['w'], bg['adv'], glyph_tex))
            rep.append('U+%04X %s = %s + %s  cell %dx%d at (%d,%d)  pad %d w %d adv %d' % (cp, chr(cp), b, m, W, CELL, x, y, bg['pad'], bg['w'], bg['adv']))
            x += W
        lum_final = [bytearray((0 if (latlas[y][x] <= 1 or not atlas[y][x]) else latlas[y][x]) for x in range(TEX)) for y in range(TEX)]
        newtex = patch_texture(tex, atlas, lum_final, region)
        outtpf = tpf[:ent['off']] + newtex + tpf[ent['off'] + ent['size']:]
        assert len(outtpf) == len(tpf)
        open(os.path.join(out, 'font', 'na_english', font + '.ccm'), 'wb').write(ccm.build(new))
        open(os.path.join(out, 'font', 'na_english', font + '.tpf'), 'wb').write(outtpf)
        free_rows = TEX - used_bottom
        used_after = y + CELL - BAND_Y0 if new else 0
        lines = ['font %s: %d glyphs, %d code groups, atlas %dx%d, last used row %d, free rows %d (= %d cell rows of %d)' % (
                    font, ccm.nglyph, ccm.ngrp, TEX, TEX, used_bottom, free_rows, free_rows // CELL, CELL),
                 'generated %d glyphs, new glyph area rows %d..%d of the band starting at %d, region %s' % (len(new), BAND_Y0, y + CELL, BAND_Y0, region),
                 'measured metrics %s; accented capitals squashed to rows %d..%d when headroom < %d, mark rows %d' % (met, mark_rows + 1, met['baseline'], mark_rows + 1, mark_rows)] + rep
        open(os.path.join(out, 'report_%s.txt' % font), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
        write_png(os.path.join(out, 'preview_%s_atlas.png' % font), TEX, TEX, atlas)
        # local preview lines using the NEW tables (re-read what we just wrote)
        nccm = Ccm(open(os.path.join(out, 'font', 'na_english', font + '.ccm'), 'rb').read())
        samples = ['Ação à Ré, Éfeso ôõ úí Çç 1º 2ª andar', 'ÁÂÃÀÇÉÊÍÓÔÕÚ', 'áâãàçéêíóôõú üÜ',
                   'The quick brown fox jumps over the lazy dog']
        rows = []
        for s in samples:
            rows += render_line(s, nccm, atlas)
        wmax = max(len(r) for r in rows)
        write_png(os.path.join(out, 'preview_%s_lines.png' % font), wmax, len(rows), [bytes(r) + bytes(wmax - len(r)) for r in rows])
        print('\n'.join(lines[:3]))
        print('wrote', len(new), 'glyphs for', font)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('usrdir'); ap.add_argument('outdir')
    ap.add_argument('--set', default='ptbr', choices=['ptbr', 'latin1'])
    ap.add_argument('--fonts', nargs='+', default=['dsfont24', 'talkfont24'])
    ap.add_argument('--mark-rows', type=int, default=3, help='height of marks above capitals')
    a = ap.parse_args()
    run(a.usrdir, a.outdir, a.set, a.fonts, a.mark_rows)
