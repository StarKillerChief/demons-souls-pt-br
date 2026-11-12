#!/usr/bin/env python3
"""Letters from a free font ("Fontes HD", a new font), drawn into the game's HD font atlases on the player's PC.

    gen_ptbr_freefont.py FONT_DIR [--preview OUT.png]

FONT_DIR  folder with dsfont24 / talkfont24 .tpf + .ccm already made 4x by gen_ptbr_hdfont.py. Every Latin letter,
          digit and punctuation mark the font has is redrawn from a free font, and the Portuguese accented letters are
          added the same way, so each accent is the font designer's own. Kana, kanji and the button icons stay.

  dsfont24 (menus, items, descriptions): TeX Gyre Schola (GUST Font License), the free Century Schoolbook design,
            the same family as the game's letters; a little lighter and with wider spacing, like the game.
  talkfont24 (dialogue, subtitles, cutscenes): the same Schola in its Bold cut, as drawn,
            slightly narrower so every line keeps the length it has with the game's own dialogue font, with a dark
            outline like the game's.

The glyph table keeps the game's own cell height and baseline; only rectangles, widths and advances change.
Needs Pillow (bundled).
"""
import os
import struct
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_ptbr_glyphs as g  # noqa: E402
import gen_ptbr_hdfont as hd  # noqa: E402

K = 4
FONTS_DIR = os.path.join(HERE, 'fonts')
# cap: capital height in game pixels relative to the game's own H; track: extra spacing (game px);
# light: how much the strokes are thinned (0 = as drawn, negative = heavier, in HD px); outline: dark ring width (game px);
# squeeze: horizontal scale of every letter and its advance
FACES = {
    'dsfont24': dict(file='texgyreschola-regular.otf', cap=1.0, track=0.5, light=1, outline=0),
    'talkfont24': dict(file='texgyreschola-bold.otf', cap=0.88, track=0.3, squeeze=0.92, light=0, outline=1),
}
CODES = (list(range(0x21, 0x7F)) + list(range(0xA1, 0x100))
         + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026])
PTBR = set(map(ord, 'ÁÂÃÀÇÉÊÍÓÔÕÚÜáâãàçéêíóôõúüªº'))
GAP = 8             # empty HD pixels around each glyph (the mip levels must not mix neighbours)


def to_img(rows, n):
    return Image.frombytes('L', (n, n), b''.join(bytes(r) for r in rows))


def ink_rows(im):
    bb = im.point(lambda v: 255 if v > 100 else 0).getbbox()
    return bb


class Face:
    def __init__(self, path, cap_hd):
        probe = ImageFont.truetype(path, 400)
        b = probe.getbbox('H', anchor='ls')
        self.size = 400 * cap_hd / (b[3] - b[1])
        self.font = ImageFont.truetype(path, round(self.size))
        self.notdef = self.font.getmask('￿').getbbox(), bytes(self.font.getmask('￿'))

    def has(self, ch):
        m = self.font.getmask(ch)
        return m.getbbox() is not None and (m.getbbox(), bytes(m)) != self.notdef

    def draw(self, ch, base, height):
        """Coverage of ch with its pen origin at x = PADX, baseline at row `base`; returns (img, advance)."""
        adv = self.font.getlength(ch)
        padx = int(self.size)
        im = Image.new('L', (int(adv) + 2 * padx, height), 0)
        ImageDraw.Draw(im).text((padx, base), ch, font=self.font, fill=255, anchor='ls')
        return im, adv, padx


def lighten(im, level):
    """Thinner strokes: blur, then a higher threshold (level 1 = slight, 2 = more); a negative level is heavier."""
    if not level:
        return im
    if level < 0:                                   # heavier: grow the strokes by -level HD pixels each side
        return im.filter(ImageFilter.MaxFilter(2 * -level + 1))
    if level == 2:
        im = im.filter(ImageFilter.MinFilter(3))
        level = 1
    lo = {1: 110}[level]
    return im.filter(ImageFilter.GaussianBlur(1.5)).point(lambda v: 0 if v < lo else min(255, (v - lo) * 255 // 60))


def run(font_dir, preview=None):
    sheets = []
    for font, spec in FACES.items():
        ccm_path, tpf_path = (os.path.join(font_dir, font + e) for e in ('.ccm', '.tpf'))
        ccm = g.Ccm(open(ccm_path, 'rb').read())
        d = open(tpf_path, 'rb').read()
        tex_i = ccm.glyph(ccm.index(ord('A')))['tex']
        ent = g.tpf_entries(d)[tex_i]
        T = ent['w']
        if T != K * ccm.tw:
            raise SystemExit('%s: needs the HD atlas (%d), found %d' % (font, K * ccm.tw, T))
        tex = d[ent['off']:ent['off'] + ent['size']]
        alpha = to_img(g.decode_alpha(tex, T, T), T)
        grey = to_img(g.decode_lum(tex, T, T), T)
        ccm.tw = ccm.th = T                       # rects in HD pixels; the header keeps the game size (build copies it)
        gl_H = ccm.glyph(ccm.index(ord('H')))
        x0, y0, x1, y1 = gl_H['rect']
        CH = y1 - y0
        hb = ink_rows(alpha.crop(gl_H['rect']))
        cap_top, base = hb[1], hb[3]               # rows inside the cell
        print("   %s: cell %d, cap top %d, baseline %d" % (font, CH, cap_top, base))
        core_lum = sorted(grey.crop(gl_H['rect']).getdata())[-max(1, (x1 - x0) * CH // 20)]
        face = Face(os.path.join(FONTS_DIR, spec['file']), (base - cap_top) * spec['cap'])
        ring = spec['outline'] * K
        have = ccm.codepoints()
        todo = [c for c in CODES if (c in have or c in PTBR) and face.has(chr(c))]
        repl = set(todo)
        # free the old cells of replaced glyphs (unless a kept glyph shares the rectangle)
        kept_rects, old_rects = set(), set()
        for cp in have:
            gi = ccm.glyph(ccm.index(cp))
            if gi['tex'] != tex_i or gi['rect'][2] <= gi['rect'][0]:
                continue
            (old_rects if cp in repl else kept_rects).add(gi['rect'])
        for r in old_rects - kept_rects:
            alpha.paste(0, r)
            grey.paste(0, r)
        occ = Image.new('L', (T, T), 0)
        for r in kept_rects:
            occ.paste(255, (max(0, r[0] - GAP), max(0, r[1] - GAP), min(T, r[2] + GAP), min(T, r[3] + GAP)))
        occ = ImageChops.lighter(occ, alpha.point(lambda v: 255 if v else 0))   # anything still drawn stays
        # draw every glyph
        cells = []
        for cp in todo:
            M = CH // 2                         # room above the cell: an accent may start above it
            im, adv, padx = face.draw(chr(cp), base + M, CH + M)
            sx = spec.get('squeeze', 1.0)
            if sx != 1.0:                       # a little narrower, so lines keep the game's own length
                im = im.resize((max(1, round(im.width * sx)), im.height), Image.LANCZOS)
                padx, adv = round(padx * sx), adv * sx
            im = lighten(im, spec['light'])
            bb = ink_rows(im)
            ftop = M + base - round((base - cap_top) * spec['cap'])     # top of this face's capitals
            if bb and bb[1] < M + 1 + ring and bb[1] < ftop:
                # accented capitals are taller than the cell: the accent zone a little lower (80%), then the whole
                # letter a little smaller around its baseline, so the accent keeps its full shape
                zone = im.crop((0, bb[1], im.width, ftop))
                nz = max(1, round(zone.height * 0.8))
                big = Image.new('L', (im.width, nz + im.height - ftop), 0)
                big.paste(zone.resize((im.width, nz), Image.LANCZOS), (0, 0))
                big.paste(im.crop((0, ftop, im.width, im.height)), (0, nz))
                top2 = ftop - nz                                 # where big's row 0 sits
                bl = M + base
                f = min(1.0, (bl - M - 1 - ring) / (bl - top2))
                small = big.resize((max(1, round(big.width * f)), max(1, round(big.height * f))), Image.LANCZOS)
                im = Image.new('L', im.size, 0)
                im.paste(small, (round(padx - padx * f), round(bl - (bl - top2) * f)))
                adv *= f                                       # the narrower letter keeps its own spacing
            im = im.crop((0, M, im.width, M + CH))
            core = im
            if ring:
                outer = core.filter(ImageFilter.MaxFilter(2 * ring + 1))
            else:
                outer = core
            bb = outer.getbbox()
            if not bb:
                continue
            ix0, ix1 = bb[0] - padx, bb[2] - padx
            pad = max(0, ix0 // K)
            w = max(1, -(-(ix1 - pad * K) // K))
            W = w * K
            a = outer.crop((padx + pad * K, 0, padx + pad * K + W, CH))
            if ring:
                lum = core.crop((padx + pad * K, 0, padx + pad * K + W, CH)).point(lambda v: v * core_lum // 255)
            else:
                lum = a.point(lambda v: core_lum if v else 0)
            step = round(adv / K + spec['track'])
            cells.append((cp, a, lum, pad, w, step))
        # pack: shelves of the cell height, left to right, skipping what is taken
        placed, y, x = [], 0, 0
        for cp, a, lum, pad, w, step in sorted(cells, key=lambda c: -c[1].width):
            W = a.width
            while True:
                if y + CH > T:
                    raise SystemExit('%s: out of atlas space at U+%04X' % (font, cp))
                if x + W > T:
                    x, y = 0, y + CH + GAP
                    continue
                busy = occ.crop((x, y, x + W, y + CH)).getbbox()
                if busy:
                    x = x + busy[2] + 1
                    continue
                break
            alpha.paste(a, (x, y))
            grey.paste(lum, (x, y))
            occ.paste(255, (max(0, x - GAP), max(0, y - GAP), min(T, x + W + GAP), min(T, y + CH + GAP)))
            placed.append((cp, (x, y, x + W, y + CH), pad, w, step, tex_i))
            x += W + GAP
        # glyph table: replaced code points get their new records (the old records stay unused)
        new = sorted(p for p in placed if p[0] not in have)
        recs = bytearray(ccm.glyph_bytes)
        for cp, (rx0, ry0, rx1, ry1), pad, w, step, tx in placed:
            if cp in have:
                i = ccm.index(cp)
                struct.pack_into('>ffffHHHH', recs, 24 * i, rx0 / T, ry0 / T, rx1 / T, ry1 / T, pad, w, step, tx)
        ccm.glyph_bytes = bytes(recs)
        sp = ccm.index(0x20)
        if sp is not None:
            gsp = ccm.glyph(sp)
            space = round(face.font.getlength(' ') * spec.get('squeeze', 1.0) / K + spec['track'])
            struct.pack_into('>HHH', recs, 24 * sp + 16, gsp['pad'], gsp['w'], space)
            ccm.glyph_bytes = bytes(recs)
        out_ccm = ccm.build([(cp, r, pad, w, step, tx) for cp, r, pad, w, step, tx in new])
        data = hd.encode_chain(alpha, grey)
        open(tpf_path + '.tmp', 'wb').write(hd.rebuild_tpf(d, tex_i, T, T, data))
        open(ccm_path + '.tmp', 'wb').write(out_ccm)
        os.replace(tpf_path + '.tmp', tpf_path)
        os.replace(ccm_path + '.tmp', ccm_path)
        print('   %s: %d letters from %s (%d new)' % (font, len(placed), spec['file'], len(new)), flush=True)
        if preview:
            sheets.append(preview_lines(g.Ccm(out_ccm), alpha, grey, T))
    if preview and sheets:
        Wd = max(s.width for s in sheets)
        out = Image.new('RGB', (Wd, sum(s.height for s in sheets)), (34, 30, 26))
        yy = 0
        for s in sheets:
            out.paste(s, (0, yy))
            yy += s.height
        out.save(preview)


def preview_lines(ccm, alpha, grey, T, lines=('Que a chama te guie, matador de demônios.',
                                               'Você não está só. Ação, coração, lâmina, ímã… “sim”',
                                               'ÁGUA ÂNIMO ÇÃO ÉÊ ÍÓÔÕ Ú à ç ü 1º 2ª')):
    """Lines set with the new table at game size x2 (pen += advance, glyph at pen + pad), grey on dark."""
    ccm.tw = ccm.th = T
    H = 26 * 2
    rows = []
    for s in lines:
        im = Image.new('RGBA', (1400, H + 6), (34, 30, 26, 255))
        pen = 6
        for c in s:
            i = ccm.index(ord(c))
            if i is None:
                pen += 10
                continue
            gi = ccm.glyph(i)
            r = gi['rect']
            if r[2] > r[0]:
                a = alpha.crop(r).resize((gi['w'] * 2, H), Image.LANCZOS)
                lum = grey.crop(r).resize((gi['w'] * 2, H), Image.LANCZOS)
                im.paste(Image.merge('RGBA', (lum, lum, lum, a)), (pen + gi['pad'] * 2, 3),
                         Image.merge('RGBA', (lum, lum, lum, a)))
            pen += gi['adv'] * 2
        rows.append(im)
    out = Image.new('RGB', (1400, sum(r.height for r in rows)), (34, 30, 26))
    for i, r in enumerate(rows):
        out.paste(r.convert('RGB'), (0, i * r.height))
    return out


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('font_dir')
    ap.add_argument('--preview')
    a = ap.parse_args()
    run(a.font_dir, a.preview)
