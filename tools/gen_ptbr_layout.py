#!/usr/bin/env python3
"""Room for the longer Portuguese area names on the in-game HUD, made on the player's PC from their own menu.drb.

    gen_ptbr_layout.py MENU_DRB OUT_DRB --ccm DSFONT24_CCM --names PLACE_NAMES_JSON

The area name next to the world-tendency eye (dialog F20-00, text object `map_name`) is right-aligned in a box
from x=891 to x=1139 on the 1280x720 layout; the eye's backing plate starts at x=1155, so the text ends 16 units
before it. The box is 248 units wide: enough for the longest name on the US disc (251 game px with dsfont24),
not for "Santuário das Tempestades" (317), which the game then lets spill over the eye.

Only the left edge of that box moves, just far enough for the widest translated name in the font being
installed. The right edge stays where it is, so every name still ends 16 units before the eye, exactly as the
original. Nothing else in the file changes. Nothing from the game is stored in this repository.
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_ptbr_glyphs as g  # noqa: E402

DIALOG, OBJECT = 'F20-00', 'map_name'
RECT = (891, 88, 1139, 112)        # the box as the US disc has it
MARGIN = 4                          # spare units on the left of the widest name


def chunks(d):
    if d[:4] != b'\0BRD':
        raise SystemExit('not a DRB layout file')
    out, p = {}, 0x10
    while True:
        tag = bytes(d[p:p + 4][::-1])
        size, count = struct.unpack('>II', d[p + 4:p + 12])
        out[tag] = (p + 0x10, size, count)
        if tag == b'END\0':
            return out
        p = (p + 0x10 + size + 15) & ~15


def find_rect(d):
    """File offset of the rectangle (left, top, right, bottom: big-endian int16) of OBJECT inside DIALOG."""
    ch = chunks(d)
    s0 = ch[b'STR\0'][0]

    def name(o):
        e = o
        while d[s0 + e:s0 + e + 2] != b'\0\0':
            e += 2
        return d[s0 + o:s0 + e].decode('utf-16-be')
    dlg, n_dlg = ch[b'DLG\0'][0], ch[b'DLG\0'][2]
    dlgo, shap, shpr = ch[b'DLGO'][0], ch[b'SHAP'][0], ch[b'SHPR'][0]
    for i in range(n_dlg):
        v = struct.unpack('>16i', d[dlg + 64 * i:dlg + 64 * i + 64])
        if name(v[0]) != DIALOG:
            continue
        for j in range(v[8]):
            q = dlgo + v[9] + 32 * j
            o_name, o_shap = struct.unpack('>ii', d[q:q + 8])
            if name(o_name) != OBJECT:
                continue
            t_off, p_off = struct.unpack('>ii', d[shap + o_shap:shap + o_shap + 8])
            if name(t_off) != 'Text':
                raise SystemExit('%s/%s is not a text object' % (DIALOG, OBJECT))
            return shpr + p_off
    raise SystemExit('%s/%s not found in this menu.drb' % (DIALOG, OBJECT))


def widest(ccm_path, names_path):
    ccm = g.Ccm(open(ccm_path, 'rb').read())
    best = (0, '')
    for e in json.load(open(names_path, encoding='utf-8'))['entries']:
        s = e.get('pt') or ''
        w = 0
        for c in s:
            i = ccm.index(ord(c))
            w += ccm.glyph(i)['adv'] if i is not None else 0
        best = max(best, (w, s))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('menu_drb')
    ap.add_argument('out_drb')
    ap.add_argument('--ccm', required=True)
    ap.add_argument('--names', required=True)
    a = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')       # the name may not fit the console's code page
    d = bytearray(open(a.menu_drb, 'rb').read())
    at = find_rect(d)
    rect = struct.unpack('>4h', d[at:at + 8])
    if rect != RECT:
        raise SystemExit('unexpected %s/%s box %s (this tool knows the US disc box %s)' % (DIALOG, OBJECT, rect, RECT))
    w, s = widest(a.ccm, a.names)
    left = min(RECT[0], RECT[2] - w - MARGIN)
    struct.pack_into('>h', d, at, left)
    open(a.out_drb + '.tmp', 'wb').write(d)
    os.replace(a.out_drb + '.tmp', a.out_drb)
    print('   area name box: %d..%d (was %d..%d); widest name %d px: %s' % (left, RECT[2], RECT[0], RECT[2], w, s))


if __name__ == '__main__':
    main()
