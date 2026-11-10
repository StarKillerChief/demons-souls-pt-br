#!/usr/bin/env python3
"""Build PT-BR.exe (the launcher) with llvm-mingw.

    build.py --cxx PATH\\x86_64-w64-mingw32-clang++.exe --out DIR

Makes the icon (a Brazil flag drawn by this script, our own art), the manifest (per-monitor DPI, common controls v6,
UTF-8 code page) and links one static exe with no extra DLLs.
"""
import argparse
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

MANIFEST = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="DemonsSouls.PTBR.Launcher" version="0.1.0.0"/>
  <description>Traducao PT-BR de Demon's Souls</description>
  <dependency><dependentAssembly>
    <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0"
      processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/>
  </dependentAssembly></dependency>
  <application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings>
    <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
    <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness>
    <activeCodePage xmlns="http://schemas.microsoft.com/SMI/2019/WindowsSettings">UTF-8</activeCodePage>
  </windowsSettings></application>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges>
    <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
  </requestedPrivileges></security></trustInfo>
</assembly>
'''


def flag_rgba(n):
    """A Brazil flag (public-domain design) drawn pixel by pixel at n x n, 4x supersampled."""
    ss = 4
    out = bytearray()
    for y in range(n):
        out.append(0)                                   # PNG filter byte
        for x in range(n):
            acc = [0, 0, 0, 0]
            for j in range(ss):
                for i in range(ss):
                    u = (x + (i + .5) / ss) / n * 256
                    v = (y + (j + .5) / ss) / n * 256
                    c = None
                    if 8 <= u <= 248 and 40 <= v <= 216:
                        c = (30, 148, 71)
                        if abs(u - 128) / 104 + abs(v - 128) / 72 <= 1:
                            c = (247, 209, 22)
                        if (u - 128) ** 2 + (v - 128) ** 2 <= 38 ** 2:
                            c = (38, 53, 127)
                            if abs(((u - 128) ** 2 + (v - 175) ** 2) ** .5 - 60) < 4.5:
                                c = (242, 242, 242)
                    if c:
                        acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]; acc[3] += 255
            k = ss * ss
            out += bytes((acc[0] // max(1, acc[3] // 255), acc[1] // max(1, acc[3] // 255),
                          acc[2] // max(1, acc[3] // 255), acc[3] // k)) if acc[3] else bytes(4)
    return bytes(out)


def png(n):
    import struct, zlib

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', n, n, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(flag_rgba(n), 9)) + chunk(b'IEND', b''))


def icon(path):
    """ICO with PNG-compressed images (Windows Vista and later), no image library needed."""
    import struct
    sizes = [16, 24, 32, 48, 64, 256]
    imgs = [png(s) for s in sizes]
    head = struct.pack('<HHH', 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    dirs = b''
    for s, data in zip(sizes, imgs):
        dirs += struct.pack('<BBBBHHII', s % 256, s % 256, 0, 0, 1, 32, len(data), off)
        off += len(data)
    open(path, 'wb').write(head + dirs + b''.join(imgs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cxx', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bindir = os.path.dirname(a.cxx)
    windres = os.path.join(bindir, 'x86_64-w64-mingw32-windres.exe')
    if not os.path.isfile(windres):
        windres = os.path.join(bindir, 'llvm-windres.exe')
    with tempfile.TemporaryDirectory() as tmp:
        icon(os.path.join(tmp, 'ptbr.ico'))
        open(os.path.join(tmp, 'app.manifest'), 'w', encoding='utf-8').write(MANIFEST)
        rc = os.path.join(tmp, 'app.rc')
        open(rc, 'w', encoding='utf-8').write('1 ICON "ptbr.ico"\n1 24 "app.manifest"\n')
        res = os.path.join(tmp, 'app.res.o')
        subprocess.run([windres, rc, '-O', 'coff', '-o', res], check=True, cwd=tmp)
        exe = os.path.join(a.out, 'PT-BR.exe')
        cmd = [a.cxx, '-std=c++17', '-O2', '-municode', '-mwindows', '-static', '-s',
               os.path.join(HERE, 'main.cpp'), res, '-o', exe,
               '-ld2d1', '-ldwrite', '-lwindowscodecs', '-lole32', '-luuid', '-lshell32', '-ldwmapi', '-luser32',
               '-lgdi32']
        subprocess.run(cmd, check=True)
    print(exe, os.path.getsize(exe))


if __name__ == '__main__':
    main()
