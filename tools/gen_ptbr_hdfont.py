#!/usr/bin/env python3
"""HD version of the game's own fonts (with the Portuguese accents), made on the player's PC.

    gen_ptbr_hdfont.py FONT_DIR

FONT_DIR  folder with <font>.tpf files as written by gen_ptbr_glyphs.py (the game's own 512x512 letters plus our
          accented letters). Each letters texture is replaced, in place, by a 4x (2048x2048) version.

How: each plane of the atlas (coverage = alpha, and the grey letter body = colour) is enlarged 4x with bicubic
interpolation and then given a contrast curve around the letter edge, so the outline comes out crisp with a thin
anti-aliased rim (the way an outline font would be drawn at that size) instead of a blur. The glyph table (CCM)
stores normalised coordinates, so it stays as it is: the game simply samples a sharper texture.
The look follows the community HD font (SonofUgly's High Resolution Font and its DeS_ButtonGlyphs update), but
nothing from that mod is used: every pixel comes from the player's own copy. Needs Pillow (bundled).
"""
import io
import os
import struct
import sys

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_ptbr_glyphs as g  # noqa: E402

K = 4
FONTS = ('dsfont24', 'talkfont24')
EDGE = (0.30, 0.70)        # coverage band turned into the anti-aliased rim
# smoothing (HD pixels) before the edge curve: it turns the 512 atlas' pixel steps into straight and round edges.
# dsfont24 has thin serif strokes that vanish with more; talkfont24's heavy letters take more.
SMOOTH = {'dsfont24': 1.2, 'talkfont24': 1.5}
# talkfont24's grey body (the bright core inside the dark ring) carries the PS3 texture compression's grain; it is
# smoothed more and filled from a lower level, so the core comes out clean like a drawn letter
GREY = {'dsfont24': (1.2, EDGE), 'talkfont24': (2.4, (0.30, 0.60))}


def plane(rows, w, h):
    return Image.frombytes('L', (w, h), b''.join(bytes(r) for r in rows))


def curve_table(edge=EDGE):
    a, b = int(edge[0] * 255), int(edge[1] * 255)
    out = []
    for v in range(256):
        if v <= a:
            out.append(0)
        elif v >= b:
            out.append(255)
        else:
            t = (v - a) / (b - a)
            out.append(int(255 * t * t * (3 - 2 * t)))
    return out


def upscale(im, smooth, edge=EDGE):
    big = im.resize((im.size[0] * K, im.size[1] * K), Image.BICUBIC)
    if smooth:
        big = big.filter(ImageFilter.GaussianBlur(smooth))
    return big.point(curve_table(edge))


EMPTY_BLOCK = bytes(8) + g.EMPTY_COLOR


def encode_level(alpha, grey):
    """DXT5 blocks with the font encoder of gen_ptbr_glyphs (grey body from black to its brightest grey; a generic
    BC1 encoder speckled talkfont24's bright core). Empty blocks are written directly, which keeps this quick."""
    w, h = alpha.size
    ab, gb = alpha.tobytes(), grey.tobytes()
    out = bytearray()
    for by in range(0, max(h, 4), 4):
        for bx in range(0, max(w, 4), 4):
            vals, lums = [], []
            for j in range(4):
                y = min(by + j, h - 1)
                for i in range(4):
                    o = y * w + min(bx + i, w - 1)
                    vals.append(ab[o])
                    lums.append(gb[o])
            if not any(vals):
                out += EMPTY_BLOCK
            else:
                out += g.encode_alpha_block(vals) + g.encode_color_block(lums, vals)
    return out


def encode_chain(alpha, grey):
    """DXT5 with the full mip chain down to 1x1, like the game's own font textures."""
    out = bytearray()
    w = alpha.size[0]
    while True:
        out += encode_level(alpha, grey)
        if w == 1:
            return bytes(out)
        w //= 2
        alpha, grey = alpha.resize((w, w), Image.BOX), grey.resize((w, w), Image.BOX)


def rebuild_tpf(d, index, w, h, data):
    """The same TPF with texture `index` replaced by a w x h one (offsets, sizes and the header total updated)."""
    n = struct.unpack('>I', d[8:12])[0]
    ents = g.tpf_entries(d)
    head = bytearray(d[:16])
    table = bytearray(d[16:16 + 32 * n])
    first = min(e['off'] for e in ents)
    names = d[16 + 32 * n:first]             # entry names (and padding) sit between the table and the data
    blobs = [d[e['off']:e['off'] + e['size']] for e in ents]
    blobs[index] = data
    off = first
    body = bytearray()
    for i, blob in enumerate(blobs):
        o = 32 * i
        struct.pack_into('>II', table, o, off, len(blob))
        if i == index:
            struct.pack_into('>HH', table, o + 12, w, h)
        body += blob
        pad = (-len(blob)) % 16
        body += b'\0' * pad
        off += len(blob) + pad
    struct.pack_into('>I', head, 4, sum(len(b) for b in blobs))
    return bytes(head) + bytes(table) + names + bytes(body)


def run(font_dir):
    for font in FONTS:
        tpf_path = os.path.join(font_dir, font + '.tpf')
        ccm = g.Ccm(open(os.path.join(font_dir, font + '.ccm'), 'rb').read())
        d = open(tpf_path, 'rb').read()
        index = ccm.glyph(ccm.index(ord('A')))['tex']
        e = g.tpf_entries(d)[index]
        T = e['w']
        if T != ccm.tw:
            raise SystemExit('%s: letters texture is %d, expected the game size %d' % (font, T, ccm.tw))
        tex = d[e['off']:e['off'] + e['size']]
        src_a = plane(g.decode_alpha(tex, T, T), T, T)
        src_g = plane(g.decode_lum(tex, T, T), T, T)
        # each glyph is enlarged inside its own cell: done on the whole atlas, the smoothing would carry ink from the
        # letter in the row below into this one (and the accents would then sit on a wrong baseline)
        alpha = Image.new('L', (T * K, T * K), 0)
        grey = Image.new('L', (T * K, T * K), 0)
        done = set()
        for i in range(ccm.nglyph):
            gl = ccm.glyph(i)
            if gl['tex'] != index or gl['rect'] in done:
                continue
            done.add(gl['rect'])
            x0, y0, x1, y1 = gl['rect']
            if x1 <= x0 or y1 <= y0:
                continue
            pad = 3                                    # empty margin so the smoothing has room at the cell edge
            ca = Image.new('L', (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 0)
            cg = Image.new('L', ca.size, 0)
            ca.paste(src_a.crop((x0, y0, x1, y1)), (pad, pad))
            cg.paste(src_g.crop((x0, y0, x1, y1)), (pad, pad))
            ua = upscale(ca, SMOOTH[font])
            # a glyph whose bright core is tiny (the dots of the ellipsis: one pixel) loses it under talkfont24's strong
            # grey smoothing and came out black in game (play test 2026-11-11): smooth it less until the core is back
            top = cg.getextrema()[1]
            sigma, edge = GREY[font]
            for s in (sigma, 2.0, 1.2, 0.6, 0):
                ug = upscale(cg, min(s, sigma), edge if s == sigma else EDGE)
                if ug.getextrema()[1] >= 0.8 * top:
                    break
            box = (pad * K, pad * K, (pad + x1 - x0) * K, (pad + y1 - y0) * K)
            alpha.paste(ua.crop(box), (x0 * K, y0 * K))
            grey.paste(ug.crop(box), (x0 * K, y0 * K))
        data = encode_chain(alpha, grey)
        open(tpf_path + '.tmp', 'wb').write(rebuild_tpf(d, index, T * K, T * K, data))
        os.replace(tpf_path + '.tmp', tpf_path)
        print('   %s: HD letters %dx%d' % (font, T * K, T * K), flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
