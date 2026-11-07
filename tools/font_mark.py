#!/usr/bin/env python3
"""Mark a CCM font for in-game identification: make some code points draw another code point's glyph.

Test aid for "which font does which text use". Only edits the glyph record table of a CCM (UV rectangle,
pad, width, advance, texture index are copied from the source glyph); the atlas (TPF) is untouched, so no
game pixels are produced or stored. Output stays outside the repository.

usage: font_mark.py IN.ccm OUT.ccm e=W E=W ...      (single characters, or U+XXXX)
"""
import struct
import sys


def cp(s):
    return int(s[2:], 16) if s.upper().startswith("U+") else ord(s)


def main(a):
    d = bytearray(open(a[0], "rb").read())
    ngrp, nglyph, ogrp, oreg = struct.unpack_from(">HHII", d, 0x10)[0], struct.unpack_from(">H", d, 0x12)[0], \
        struct.unpack_from(">I", d, 0x14)[0], struct.unpack_from(">I", d, 0x18)[0]
    groups = [struct.unpack_from(">III", d, ogrp + 12 * i) for i in range(ngrp)]

    def idx(c):
        for first, last, g0 in groups:
            if first <= c <= last:
                return g0 + (c - first)
        raise SystemExit("code point U+%04X not in this font" % c)

    for pair in a[2:]:
        dst, src = pair.split("=")
        di, si = idx(cp(dst)), idx(cp(src))
        d[oreg + 24 * di: oreg + 24 * di + 24] = d[oreg + 24 * si: oreg + 24 * si + 24]
        print("U+%04X (glyph %d) now draws U+%04X (glyph %d)" % (cp(dst), di, cp(src), si))
    open(a[1], "wb").write(d)


if __name__ == "__main__":
    main(sys.argv[1:])
