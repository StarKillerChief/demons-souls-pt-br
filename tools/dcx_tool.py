#!/usr/bin/env python3
"""DCX (EDGE variant) reader and writer for Demon's Souls (BLUS30443).

Layout (big-endian), confirmed on the game's own files, and matching the checks in
tools/spu_harness/src/dcx.cpp (parse_dcx_edge):
  0x00 'DCX\0'  0x04 0x00010000  0x08 0x18  0x0C 0x24  0x10 0x24  0x14 (0x24 + DCA size)
  0x18 'DCS\0'  0x1C uncompressed size  0x20 compressed payload size (padded entries, see below)
  0x24 'DCP\0'  0x28 'EDGE'  0x2C 0x20  0x30 0x09000000  0x34 0x00010000  0x38 0  0x3C 0  0x40 0x00100100
  0x44 'DCA\0'  0x48 DCA size (8 + EgdT size)   0x4C 'EgdT'  0x50 0x00010100  0x54 0x24  0x58 0x10
  0x5C chunk size 0x10000  0x60 last chunk uncompressed size  0x64 EgdT size (0x24 + 16*n)
  0x68 chunk count n  0x6C 0x00100000
  0x70 + 16*i: (0, offset relative to payload, stored size, flag 1=raw deflate, 0=stored)
  payload starts at 0x44 + DCA size; chunk offsets are 16-byte aligned.
Every chunk is a raw deflate stream (zlib wbits=-15) of up to 0x10000 uncompressed bytes.

Usage:
  dcx_tool.py unpack IN.dcx OUT
  dcx_tool.py pack   IN OUT.dcx
  dcx_tool.py verify IN.dcx            # structural check + decode + re-encode round trip
No game data is stored in this repository.
"""
import struct
import sys
import zlib

CHUNK = 0x10000


class DcxError(Exception):
    pass


def _u32(d, o):
    return struct.unpack_from(">I", d, o)[0]


def parse(d):
    """Return (uncompressed_size, compressed_size, chunk_size, last_size, payload_off, chunks, hdr_fields)."""
    if d[0:4] != b"DCX\0" or d[0x18:0x1C] != b"DCS\0" or d[0x24:0x28] != b"DCP\0":
        raise DcxError("not a DCX with DCS/DCP")
    if d[0x28:0x2C] != b"EDGE":
        raise DcxError("DCP method is %r, only EDGE is supported" % d[0x28:0x2C])
    if d[0x44:0x48] != b"DCA\0" or d[0x4C:0x50] != b"EgdT":
        raise DcxError("missing DCA/EgdT")
    usize, csize = _u32(d, 0x1C), _u32(d, 0x20)
    payload = 0x44 + _u32(d, 0x48)
    hdr, esz, chunk, last, tsz, n = (_u32(d, 0x54), _u32(d, 0x58), _u32(d, 0x5C), _u32(d, 0x60),
                                     _u32(d, 0x64), _u32(d, 0x68))
    if esz != 16 or n == 0 or hdr + n * esz != tsz or chunk == 0 or chunk > CHUNK:
        raise DcxError("inconsistent EgdT table")
    chunks = []
    total = 0
    for i in range(n):
        e = 0x4C + hdr + i * esz
        off, size, flag = _u32(d, e + 4), _u32(d, e + 8), _u32(d, e + 12)
        if flag > 1 or payload + off + size > len(d):
            raise DcxError("bad chunk %d" % i)
        ulen = last if i == n - 1 else chunk
        total += ulen
        chunks.append((off, size, flag, ulen))
    if total != usize:
        raise DcxError("chunk sizes (%d) != DCS size (%d)" % (total, usize))
    return usize, csize, chunk, last, payload, chunks, d[0x2C:0x44]


def decode(d):
    usize, _, _, _, payload, chunks, _ = parse(d)
    out = bytearray()
    for off, size, flag, ulen in chunks:
        raw = d[payload + off: payload + off + size]
        part = zlib.decompress(raw, -15) if flag else bytes(raw)
        if len(part) < ulen:
            raise DcxError("chunk decoded to %d bytes, expected %d" % (len(part), ulen))
        # Some third-party DCX writers (older fan translations re-packed this way) put one byte too many in every
        # chunk: the next chunk's first byte. The game reads only the size the table gives, so do the same.
        out += part[:ulen]
    if len(out) != usize:
        raise DcxError("decoded %d bytes, expected %d" % (len(out), usize))
    return bytes(out)


def encode(data, level=9):
    n = max(1, (len(data) + CHUNK - 1) // CHUNK)
    last = len(data) - (n - 1) * CHUNK if data else 0
    if data and last == 0:
        last = CHUNK
    blobs, table, off = [], [], 0
    for i in range(n):
        piece = data[i * CHUNK:(i + 1) * CHUNK]
        co = zlib.compressobj(level, zlib.DEFLATED, -15)
        comp = co.compress(piece) + co.flush()
        flag = 1
        if len(comp) >= len(piece):  # never grow a chunk
            comp, flag = piece, 0
        table.append((off, len(comp), flag))
        pad = (-len(comp)) % 16
        blobs.append(comp + b"\0" * pad)
        off += len(comp) + pad
    payload = b"".join(blobs)
    tsz = 0x24 + 16 * n
    dca = 8 + tsz
    h = bytearray()
    h += b"DCX\0" + struct.pack(">IIIII", 0x10000, 0x18, 0x24, 0x24, 0x24 + dca)
    h += b"DCS\0" + struct.pack(">II", len(data), len(payload))
    h += b"DCP\0EDGE" + struct.pack(">IIIIII", 0x20, 0x09000000, 0x00010000, 0, 0, 0x00100100)
    h += b"DCA\0" + struct.pack(">I", dca)
    h += b"EgdT" + struct.pack(">IIIIIIII", 0x00010100, 0x24, 0x10, CHUNK, last, tsz, n, 0x00100000)
    for o, s, f in table:
        h += struct.pack(">IIII", 0, o, s, f)
    assert len(h) == 0x44 + dca
    return bytes(h) + payload


def verify(d):
    """Decode, re-encode, decode again; compare header skeleton with the input. Returns a report string."""
    usize, csize, chunk, last, payload, chunks, fixed = parse(d)
    plain = decode(d)
    re = encode(plain)
    plain2 = decode(re)
    if plain2 != plain:
        raise DcxError("round trip mismatch")
    u2, c2, ch2, l2, p2, chunks2, fixed2 = parse(re)
    same_hdr = (fixed == fixed2 and chunk == ch2 and last == l2 and usize == u2 and len(chunks) == len(chunks2)
                and payload == p2)
    aligned = all(o % 16 == 0 for o, _, _, _ in chunks2)
    pad_ok = (len(d) == payload + csize)
    return ("ok: %d bytes -> %d chunks; header skeleton %s; re-encoded %d bytes (orig %d); aligned=%s; "
            "orig size==payload+DCS.csize: %s" % (usize, len(chunks), "identical" if same_hdr else "DIFFERS",
                                                  len(re), len(d), aligned, pad_ok))


def main(a):
    if len(a) < 2:
        print(__doc__)
        return 2
    cmd = a[0]
    rd = lambda p: open(p, "rb").read()
    if cmd == "unpack":
        open(a[2], "wb").write(decode(rd(a[1])))
    elif cmd == "pack":
        open(a[2], "wb").write(encode(rd(a[1])))
    elif cmd == "verify":
        print(verify(rd(a[1])))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
