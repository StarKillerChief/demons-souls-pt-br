#!/usr/bin/env python3
"""Build the movie subtitle pictures on the player's PC, from the player's own game files.

    make_movie_subs.py --game GAMEDIR --subs TEXTDIR --out OUTDIR

GAMEDIR  the folder holding PS3_GAME, with the PT-BR pack already installed (the font must have the accents)
TEXTDIR  folder of <movie>.json files: {"movie": name, "hash": hex, "lines": [{"first": n, "end": n, "text": s}]}
OUTDIR   receives <hash>.subs and one .rgba picture per line, read by avcodec_shim.cpp

The letters come from the game's dsfont24 and the frame from the game's menu texture (Menu03), so nothing from the
game is stored in this repository. Standard library only.
"""
import argparse
import glob
import importlib.util
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO_W, VIDEO_H = 1280, 720
INK = (214, 190, 146)
FILL_ALPHA = 0.72
BOTTOM_MARGIN = 28
TRACKING = 1
PAD_X, PAD_Y = 44, 26

# Where the frame is in Menu03 (x0, y0, x1, y1), and the parts of it.
FRAME = (761, 4, 1018, 141)
INNER = (780, 17, 999, 128)
CORNER_W, CORNER_H = 70, 26


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, '..', name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


g = load('gen_ptbr_glyphs')
dcx = load('dcx_tool')


def read_game_file(usr, rel):
    p = os.path.join(usr, rel)
    if os.path.isfile(p + '.dcx'):
        return dcx.decode(open(p + '.dcx', 'rb').read())
    return open(p, 'rb').read()


def decode_dxt5(data, w, region):
    """RGBA rows of `region` from a DXT5 texture."""
    x0, y0, x1, y1 = region
    rows = [bytearray((x1 - x0) * 4) for _ in range(y1 - y0)]
    for by in range(y0 // 4, (y1 + 3) // 4):
        for bx in range(x0 // 4, (x1 + 3) // 4):
            b = data[(by * (w // 4) + bx) * 16:(by * (w // 4) + bx) * 16 + 16]
            al = g.dxt5_alpha_block(b[:8])
            c0, c1 = struct.unpack('<HH', b[8:12])

            def rgb(c):
                return ((c >> 11) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31)
            p0, p1 = rgb(c0), rgb(c1)
            pal = [p0, p1, tuple((2 * p + q) // 3 for p, q in zip(p0, p1)), tuple((p + 2 * q) // 3 for p, q in zip(p0, p1))]
            bits = struct.unpack('<I', b[12:16])[0]
            for i in range(16):
                x, y = bx * 4 + (i & 3), by * 4 + (i >> 2)
                if x0 <= x < x1 and y0 <= y < y1:
                    o = (x - x0) * 4
                    rows[y - y0][o:o + 4] = bytes(pal[(bits >> (2 * i)) & 3]) + bytes([al[i]])
    return rows


class Art:
    def __init__(self, usr):
        ccm = g.Ccm(read_game_file(usr, 'font/na_english/dsfont24.ccm'))
        tpf = read_game_file(usr, 'font/na_english/dsfont24.tpf')
        ent = g.tpf_entries(tpf)[ccm.glyph(ccm.index(ord('A')))['tex']]
        self.ccm, self.atlas = ccm, g.decode_alpha(tpf[ent['off']:ent['off'] + ent['size']], g.TEX, g.TEX)
        menu = read_game_file(usr, 'menu/menu.tpf')
        tex = next(e for e in g.tpf_entries(menu) if e['name'] == 'Menu03')
        self.tex_rows = decode_dxt5(menu[tex['off']:tex['off'] + tex['size']], tex['w'], FRAME)

    def tex(self, x, y):
        """Frame pixel at Menu03 coordinates. Inside the frame, the fill is made see-through."""
        r, gr, b, a = self.tex_rows[y - FRAME[1]][(x - FRAME[0]) * 4:(x - FRAME[0]) * 4 + 4]
        if INNER[0] <= x < INNER[2] and INNER[1] <= y < INNER[3]:
            a = int(a * FILL_ALPHA)
        return r, gr, b, a

    def text_width(self, s):
        w = 0
        for c in s:
            i = self.ccm.index(ord(c))
            if i is None:
                raise SystemExit('the font has no letter %r (is the PT-BR pack installed?)' % c)
            w += self.ccm.glyph(i)['adv'] + TRACKING
        return w


def frame_source(pos, size, corner, mid_from, mid_to, frame_from, frame_to):
    """Nine-slice: which source coordinate an output coordinate comes from."""
    if pos < corner:
        return frame_from + pos
    if pos >= size - corner:
        return frame_to - (size - pos)
    return mid_from + (pos - corner) * (mid_to - mid_from) // max(1, size - 2 * corner)


def make_sprite(art, lines):
    th = g.CELL * len(lines)
    w = max(art.text_width(s) for s in lines) + 2 * PAD_X
    w = max(w, 2 * CORNER_W + 40) & ~1
    h = max(th + 2 * PAD_Y, 2 * CORNER_H + 8) & ~1
    px = bytearray(w * h * 4)
    for y in range(h):
        sy = frame_source(y, h, CORNER_H, 60, 80, FRAME[1], FRAME[3])
        for x in range(w):
            sx = frame_source(x, w, CORNER_W, 850, 900, FRAME[0], FRAME[2])
            px[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes(art.tex(sx, sy))
    ty = (h - th) // 2
    for n, s in enumerate(lines):
        pen = (w - art.text_width(s)) // 2
        for c in s:
            gl = art.ccm.glyph(art.ccm.index(ord(c)))
            cell = g.crop(art.atlas, gl['rect'])
            for yy, row in enumerate(cell):
                for xx, a in enumerate(row):
                    if a:
                        X, Y = pen + gl['pad'] + xx, ty + n * g.CELL + yy
                        if 0 <= X < w and 0 <= Y < h:
                            o = (Y * w + X) * 4
                            ba = px[o + 3] / 255
                            aa = a / 255
                            out = aa + ba * (1 - aa)
                            for k in range(3):
                                px[o + k] = int((INK[k] * aa + px[o + k] * ba * (1 - aa)) / out)
                            px[o + 3] = int(out * 255)
            pen += gl['adv'] + TRACKING
    return w, h, bytes(px)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--game', required=True)
    ap.add_argument('--subs', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    usr = os.path.join(a.game, 'PS3_GAME', 'USRDIR')
    os.makedirs(a.out, exist_ok=True)
    art = Art(usr)
    for path in sorted(glob.glob(os.path.join(a.subs, '*.json'))):
        j = json.load(open(path, encoding='utf-8'))
        out = []
        for i, l in enumerate(j['lines']):
            w, h, px = make_sprite(art, l['text'].split('\n'))
            name = '%s_%03d.rgba' % (j['hash'], i)
            open(os.path.join(a.out, name), 'wb').write(px)
            out.append('%d %d %d %d %d %d %s\n' % (l['first'], l['end'], (VIDEO_W - w) // 2, VIDEO_H - h - BOTTOM_MARGIN,
                                                   w, h, name))
        open(os.path.join(a.out, j['hash'] + '.subs'), 'w', newline='\n').writelines(out)
        print('%s: %d lines' % (j['movie'], len(out)))


if __name__ == '__main__':
    main()
