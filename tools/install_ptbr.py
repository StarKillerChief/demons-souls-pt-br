#!/usr/bin/env python3
"""Apply (and undo) the PT-BR pack on a COPY of the player's own Demon's Souls files (BLUS30443, US).

Nothing is ever downloaded and no game file is shipped: the fonts and message archives are rebuilt on this PC
from the files in the folder you point at, plus the Portuguese text in ../text.

    install_ptbr.py install   --game GAMEDIR --out NEWDIR     # copy GAMEDIR to NEWDIR, then apply there
    install_ptbr.py install   --game GAMEDIR --in-place       # apply to GAMEDIR itself (use ONLY on a copy)
    install_ptbr.py uninstall --game GAMEDIR                  # put the saved originals back
    install_ptbr.py status    --game GAMEDIR

GAMEDIR is the folder that contains PS3_GAME (or PS3_GAME/USRDIR itself).
Files touched (all inside USRDIR; the originals are saved first under USRDIR/.ptbr-backup with SHA-256):
    font/na_english/dsfont24.ccm.dcx   dsfont24.tpf.dcx   talkfont24.ccm.dcx   talkfont24.tpf.dcx
    msg/na_english/item.msgbnd.dcx     menu.msgbnd.dcx
    menu/menu.tpf.dcx                  (the big on-screen messages; needs Pillow)
    menu/00.tpf.dcx ... 16.tpf.dcx     (the loading screens: name and CARREGANDO; needs Pillow)
The game only ever opens the `.dcx` names for these files, so the plain twins are left alone.
`install` refuses to run on a folder that is not BLUS30443, refuses --in-place without the flag, and never
writes outside GAMEDIR/NEWDIR. Running `install` again first restores the originals, then re-applies.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.join(os.path.dirname(HERE), 'text')
BACKUP = '.ptbr-backup'
FONTS = ('dsfont24', 'talkfont24')
LANG = 'na_english'
TARGETS = ([('font/%s/%s.%s.dcx' % (LANG, f, e)) for f in FONTS for e in ('ccm', 'tpf')]
           + [('msg/%s/%s.msgbnd.dcx' % (LANG, b)) for b in ('item', 'menu')]
           + ['menu/menu.tpf.dcx']             # the big on-screen messages (YOU DIED and the rest)
           + ['menu/%02d.tpf.dcx' % i for i in range(17)])     # the loading screens


VERSION = '0.1.1'


def step(key, **info):
    """Machine-readable progress for the launcher (only when PTBR_PROGRESS is set): one '@@{json}' line per step."""
    if os.environ.get('PTBR_PROGRESS'):
        print('@@' + json.dumps(dict(step=key, **info), ensure_ascii=False), flush=True)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def find_usrdir(game):
    for c in (os.path.join(game, 'PS3_GAME', 'USRDIR'), game):
        if os.path.isdir(os.path.join(c, 'font')) and os.path.isdir(os.path.join(c, 'msg')):
            return c
    raise SystemExit('error: no PS3_GAME/USRDIR with font/ and msg/ under %s' % game)


def check_title(usr):
    sfo = os.path.join(os.path.dirname(usr), 'PARAM.SFO')
    if not os.path.isfile(sfo):
        raise SystemExit('error: PS3_GAME/PARAM.SFO not found, cannot confirm the game version')
    if b'BLUS30443' not in open(sfo, 'rb').read():
        raise SystemExit('error: this is not BLUS30443 (US). The pack only supports the US disc version for now; the European version (BLES00932) is not supported yet.')


def manifest_path(usr):
    return os.path.join(usr, BACKUP, 'manifest.json')


def read_manifest(usr):
    p = manifest_path(usr)
    return json.load(open(p, encoding='utf-8')) if os.path.isfile(p) else None


def uninstall(usr, force=False):
    man = read_manifest(usr)
    if not man:
        print('nothing to undo: no manifest under %s' % os.path.join(usr, BACKUP))
        return True
    ok = True
    for rel, rec in man['files'].items():
        cur = os.path.join(usr, rel)
        bak = os.path.join(usr, BACKUP, rel)
        if not os.path.isfile(bak):
            print('  MISSING backup for %s: cannot restore' % rel)
            ok = False
            continue
        if os.path.isfile(cur) and sha(cur) != rec['installed_sha256'] and not force:
            print('  SKIPPED %s: it changed after the install (updated or edited by something else). '
                  'Use --force to overwrite it with the saved original.' % rel)
            ok = False
            continue
        shutil.copyfile(bak, cur + '.tmp')
        os.replace(cur + '.tmp', cur)
        if sha(cur) != rec['original_sha256']:
            print('  WARNING %s restored but its hash differs from the recorded original' % rel)
            ok = False
        else:
            print('  restored %s' % rel)
    if ok:
        shutil.rmtree(os.path.join(usr, BACKUP))
        print('undone: all %d files are the originals again, backup folder removed' % len(man['files']))
    return ok


def current_font(usr, rel):
    """The font file the game opens now (as it was before our install), decoded, and the disc's plain twin."""
    dcx = load('dcx_tool')
    src = os.path.join(usr, BACKUP, rel)
    if not os.path.isfile(src):
        src = os.path.join(usr, rel)
    plain = os.path.join(usr, rel[:-4])
    data = dcx.decode(open(src, 'rb').read()) if os.path.isfile(src) else None
    twin = open(plain, 'rb').read() if os.path.isfile(plain) else None
    return data, twin


def font_mod(usr):
    """None: the game's own fonts. 'hd': the HD font mod (4x atlases, same glyph table), which the pack supports.
    'other': some other font mod, which the pack cannot build on (the original fonts are used then)."""
    g = load('gen_ptbr_glyphs')
    found = None
    for f in FONTS:
        tpf, twin = current_font(usr, 'font/%s/%s.tpf.dcx' % (LANG, f))
        ccm, ccm_twin = current_font(usr, 'font/%s/%s.ccm.dcx' % (LANG, f))
        if tpf is None or twin is None or tpf == twin:
            continue
        if ccm != ccm_twin:
            return 'other'
        table = g.Ccm(ccm)
        ent = g.tpf_entries(tpf)[table.glyph(table.index(ord('A')))['tex']]
        if ent['w'] != 4 * table.tw or ent['h'] != 4 * table.th:
            return 'other'
        found = 'hd'
    return found


def decode_to_plain(usr, work, fonts='original'):
    """Write the plain ccm/tpf/msgbnd to build from into work/{font,msg}/na_english (from the backup if one exists).
    fonts: 'original' builds on the disc's own fonts even when a font mod replaced them; 'hd' builds on the HD font."""
    dcx = load('dcx_tool')
    for rel in TARGETS:
        src = os.path.join(usr, BACKUP, rel)
        if not os.path.isfile(src):
            src = os.path.join(usr, rel)
        if not os.path.isfile(src):
            plain = os.path.join(usr, rel[:-4])
            if not os.path.isfile(plain):
                raise SystemExit('error: neither %s nor its plain twin exists' % rel)
            data = open(plain, 'rb').read()
        else:
            data = dcx.decode(open(src, 'rb').read())
            plain = os.path.join(usr, rel[:-4])
            if rel.startswith('font/') and os.path.isfile(plain) and fonts != 'hd':
                orig_plain = open(plain, 'rb').read()
                if orig_plain != data:
                    # Another mod (a high-resolution font, for example) replaced the .dcx the game opens. The disc's
                    # plain twin still holds the original font, which is what the accented letters are made from.
                    print('note: %s comes from a font mod; the original game font is used, so that font mod is '
                          'off while the translation is installed' % rel)
                    data = orig_plain
        out = os.path.join(work, rel[:-4])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(data)


def install(usr, text, fonts='original'):
    """fonts: 'original' (the game's own fonts) or 'hd' (the same fonts made 4x sharper on this PC by
    gen_ptbr_hdfont.py, then given the accents at that size). Both start from the disc's own fonts; a font mod
    installed in this copy is set aside while the translation is installed."""
    check_title(usr)
    if read_manifest(usr):
        print('a previous install was found: restoring the originals first')
        if not uninstall(usr):
            raise SystemExit('error: could not restore the originals; fix that first (or use uninstall --force)')
    dcx = load('dcx_tool')
    fmg = load('fmg_tool')
    with tempfile.TemporaryDirectory(prefix='ptbr_') as tmp:
        base, out = os.path.join(tmp, 'orig'), os.path.join(tmp, 'out')
        decode_to_plain(usr, base, 'original')
        if fonts in ('hd', 'novas'):
            step('fonts', fonts=fonts)
            print('1/4 fonts: making the game fonts of this copy 4x sharper (HD), then the accented letters', flush=True)
            r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gen_ptbr_hdfont.py'),
                                os.path.join(base, 'font', LANG)],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True)
            if r.returncode:
                raise SystemExit('error: HD font generation failed:\n' + r.stdout + r.stderr)
            if fonts == 'novas':
                print('   new fonts (test): letters and accents redrawn from free fonts (Schola, Almendra)', flush=True)
                r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gen_ptbr_freefont.py'),
                                    os.path.join(base, 'font', LANG)],
                                   stdin=subprocess.DEVNULL, capture_output=True, text=True)
                if r.returncode:
                    raise SystemExit('error: new font generation failed:\n' + r.stdout + r.stderr)
        else:
            step('fonts', fonts='original')
            print('1/4 fonts: deriving the accented letters from the original game fonts of this copy', flush=True)
        r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gen_ptbr_glyphs.py'), base, out],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('error: font generation failed:\n' + r.stdout + r.stderr)
        step('text')
        print('2/4 text: building the message archives')
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fmg.cmd_import(base, text, out, LANG)
        cp_ds = fmg.ccm_codepoints(os.path.join(out, 'font', LANG, 'dsfont24.ccm'))
        cp_talk = fmg.ccm_codepoints(os.path.join(out, 'font', LANG, 'talkfont24.ccm'))
        used = set()
        for j in fmg.load_trans(text).values():
            for e in j['entries']:
                used.update(e.get('pt') or '')
        used.discard(chr(10))
        missing = sorted(c for c in used if ord(c) not in cp_ds)
        if missing:
            raise SystemExit('error: dsfont24 has no glyph for: %s (nothing was written)' % ''.join(missing))
        talk_only = sorted(c for c in used if ord(c) not in cp_talk)
        if talk_only:
            print('note: talkfont24 (bold face) has no glyph for %s; the game draws a blank for it, as it does for the '
                  'English original (the same symbol appears there)' % ' '.join('U+%04X' % ord(c) for c in talk_only))
        print('3/4 checked: every character of the Portuguese text has a glyph in dsfont24')
        try:
            import PIL  # noqa: F401  (bundled with the installer's Python)
            os.makedirs(os.path.join(out, 'menu'), exist_ok=True)
            r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gen_ptbr_banners.py'),
                                os.path.join(base, 'menu', 'menu.tpf'), os.path.join(out, 'menu', 'menu.tpf')],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True)
            if r.returncode:
                raise SystemExit('error: banner generation failed:' + chr(10) + r.stdout + r.stderr)
            step('banners')
            print('   big on-screen messages (VOCÊ MORREU and the rest) made from the lettering of this copy')
            print('   loading screens: names and CARREGANDO, set in EB Garamond over the art of this copy', flush=True)
            r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gen_ptbr_loading.py'),
                                os.path.join(base, 'menu'), os.path.join(out, 'menu')],
                               stdin=subprocess.DEVNULL)
            if r.returncode:
                raise SystemExit('error: loading screen generation failed (see above)')
        except ImportError:
            print('note: Pillow is missing, so the big on-screen messages stay in English')
        step('writing')
        print('4/4 writing (originals are saved in %s first)' % BACKUP)
        files = {}
        newdcx = {}
        for rel in TARGETS:
            built = os.path.join(out, rel[:-4])
            if not os.path.isfile(built):
                continue
            newdcx[rel] = dcx.encode(open(built, 'rb').read())
            cur = os.path.join(usr, rel)
            orig_sha = sha(cur) if os.path.isfile(cur) else None
            files[rel] = {'original_sha256': orig_sha,
                          'installed_sha256': hashlib.sha256(newdcx[rel]).hexdigest(),
                          'existed': orig_sha is not None}
        os.makedirs(os.path.join(usr, BACKUP), exist_ok=True)
        for rel, rec in files.items():
            if rec['existed']:
                b = os.path.join(usr, BACKUP, rel)
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copyfile(os.path.join(usr, rel), b)
        json.dump({'pack': 'demons-souls-ptbr', 'format': 1, 'version': VERSION, 'fonts': fonts, 'files': files},
                  open(manifest_path(usr), 'w', encoding='utf-8'), indent=1)
        for rel, data in newdcx.items():
            cur = os.path.join(usr, rel)
            os.makedirs(os.path.dirname(cur), exist_ok=True)
            open(cur + '.tmp', 'wb').write(data)
            os.replace(cur + '.tmp', cur)
            print('  wrote', rel)
    print('done. To undo: install_ptbr.py uninstall --game <same folder>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['install', 'uninstall', 'status'])
    ap.add_argument('--game', required=True)
    ap.add_argument('--out', help='install: copy --game here first and apply there (the original stays untouched)')
    ap.add_argument('--in-place', action='store_true', help='install: apply to --game itself (only for a copy)')
    ap.add_argument('--text', default=TEXT)
    ap.add_argument('--force', action='store_true', help='uninstall: overwrite files changed after the install')
    ap.add_argument('--fonts', choices=['original', 'hd', 'novas'], default='original',
                    help='install: the original game fonts (default) or HD versions of them made on this PC')
    a = ap.parse_args()
    game = os.path.abspath(a.game)
    if a.cmd == 'install':
        if bool(a.out) == a.in_place:
            raise SystemExit('error: give exactly one of --out NEWDIR (recommended) or --in-place')
        if a.out:
            out = os.path.abspath(a.out)
            if os.path.exists(out) and os.listdir(out):
                raise SystemExit('error: %s exists and is not empty' % out)
            if out == game or out.startswith(game + os.sep) or game.startswith(out + os.sep):
                raise SystemExit('error: --out must be a different folder, not inside or around --game')
            find_usrdir(game)
            print('copying %s -> %s (a plain copy, no links; several GB, takes a while)' % (game, out))
            shutil.copytree(game, out, symlinks=False)
            game = out
        install(find_usrdir(game), a.text, a.fonts)
    elif a.cmd == 'uninstall':
        sys.exit(0 if uninstall(find_usrdir(game), a.force) else 1)
    else:
        usr = find_usrdir(game)
        man = read_manifest(usr)
        if not man:
            print('not installed')
            return
        for rel, rec in man['files'].items():
            cur = os.path.join(usr, rel)
            state = 'installed' if os.path.isfile(cur) and sha(cur) == rec['installed_sha256'] else 'CHANGED since the install'
            print('%-45s %s' % (rel, state))


if __name__ == '__main__':
    main()
