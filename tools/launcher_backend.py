#!/usr/bin/env python3
"""Back end of the PT-BR launcher (PT-BR.exe). The launcher draws the window; everything that touches files is here.

Every command prints one JSON object per line. Progress lines start with '@@' (see install_ptbr.step); the last line
of every command is '@@{"step": "done", ...}' or '@@{"step": "error", "code": ..., "message": ...}'.

    launcher_backend.py state
    launcher_backend.py validate  --game FOLDER
    launcher_backend.py install   --target soulbrandt|rpcs3 --fonts original|hd [--game FOLDER]
    launcher_backend.py uninstall --target soulbrandt|rpcs3 [--game FOLDER]
    launcher_backend.py art       --out DIR [--target soulbrandt|rpcs3] [--game FOLDER] [--translated]

state     what the launcher shows first: Soulbrandt found / prepared / running / translated (fonts, version), and
          RPCS3 folders holding BLUS30443 that could be found without searching the disk (the folder Soulbrandt
          imported from, and the games list of RPCS3 installs in a few usual places).
validate  is FOLDER (the game folder, PS3_GAME or USRDIR) Demon's Souls BLUS30443?
art       the white logo and the 17 loading-screen paintings, as PNG files, from the player's own copy (never
          shipped): logo.png, NN.png (the picture part, 1024x720); --translated reads the installed files.
"""
import argparse
import contextlib
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('PTBR_PROGRESS', '1')
import install_ptbr as pack  # noqa: E402
import ptbr_soulbrandt as sb  # noqa: E402

TEXT = os.path.join(HERE, '..', 'text')


def emit(**kv):
    print('@@' + json.dumps(kv, ensure_ascii=False), flush=True)


class Fail(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


# ----------------------------------------------------------------------------- finding things
def find_program():
    """Soulbrandt.exe: the folder above the PT-BR folder (or a few above, after Windows' 'Extract all')."""
    cand = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))      # PT-BR/pack/tools -> the folder above PT-BR
    for _ in range(3):
        if os.path.isfile(os.path.join(cand, 'Soulbrandt.exe')):
            return cand
        cand = os.path.dirname(cand)
    return None


def usrdir_of(folder):
    """USRDIR for a game folder given as the game root, PS3_GAME or USRDIR itself (None if it is not a game)."""
    if not folder:
        return None
    folder = os.path.normpath(folder)
    for c in (os.path.join(folder, 'PS3_GAME', 'USRDIR'), os.path.join(folder, 'USRDIR'), folder):
        if os.path.isdir(os.path.join(c, 'font')) and os.path.isdir(os.path.join(c, 'msg')):
            return c
    return None


def check_game(folder):
    usr = usrdir_of(folder)
    if not usr:
        raise Fail('not_game', 'Esta pasta não parece ser a do Demon\'s Souls. Escolha a pasta do jogo '
                               '(a que tem PS3_GAME), a PS3_GAME ou a USRDIR.')
    sfo = os.path.join(os.path.dirname(usr), 'PARAM.SFO')
    if not os.path.isfile(sfo):
        raise Fail('not_game', 'Não encontrei o PARAM.SFO do jogo nesta pasta.')
    if b'BLUS30443' not in open(sfo, 'rb').read():
        raise Fail('wrong_version', 'Esta é outra versão do Demon\'s Souls. Por enquanto a tradução funciona só '
                                    'na versão americana (BLUS30443).')
    return usr


def installed_info(usr):
    man = pack.read_manifest(usr) if usr else None
    if not man:
        return {'installed': False}
    return {'installed': True, 'fonts': man.get('fonts', 'original'), 'version': man.get('version', '0.1')}


RPCS3_PLACES = ['C:\\', 'D:\\', 'E:\\', os.path.expanduser('~'), os.path.join(os.path.expanduser('~'), 'Desktop'),
                os.path.join(os.path.expanduser('~'), 'Downloads'), os.path.join(os.path.expanduser('~'), 'Documents'),
                os.environ.get('ProgramFiles', 'C:\\Program Files'), os.environ.get('LOCALAPPDATA', '')]


def rpcs3_candidates(extra=()):
    """BLUS30443 folders known to RPCS3 installs in the usual places (one folder level only: no disk search)."""
    found = []

    def add(p):
        p = os.path.normpath(p)
        if usrdir_of(p) and p not in found:
            try:
                check_game(p)
                found.append(p)
            except Fail:
                pass
    for p in extra:
        if p and 'rpcs3' in p.lower():
            add(p)
    for place in RPCS3_PLACES:
        if not place or not os.path.isdir(place):
            continue
        for root in glob.glob(os.path.join(place, '[Rr][Pp][Cc][Ss]3*')):
            for yml in (os.path.join(root, 'config', 'games.yml'), os.path.join(root, 'games.yml')):
                try:
                    for line in open(yml, encoding='utf-8', errors='replace'):
                        if line.strip().startswith('BLUS30443:'):
                            add(line.split(':', 1)[1].strip().strip('"\''))
                except OSError:
                    pass
            for g in glob.glob(os.path.join(root, 'games', '*')):
                if 'BLUS30443' in os.path.basename(g).upper():
                    add(g)
    return found


# ----------------------------------------------------------------------------- commands
def cmd_state(a):
    out = {'version': pack.VERSION, 'soulbrandt': {'found': False}, 'rpcs3': {}}
    prog = find_program()
    extra = []
    if prog:
        data = sb.find_data(prog)
        s = {'found': True, 'program': prog, 'prepared': sb.has_ready(data), 'running': sb.game_running()}
        if s['prepared']:
            try:
                game = sb.find_game(data)
                ov = sb.overlay_of(data)
                on = os.path.normcase(game) == os.path.normcase(ov)
                src = sb.overlay_source(ov) if on else game
                s['game'] = src
                extra.append(src)
                s.update(installed_info(usrdir_of(ov)) if on else {'installed': False})
                s['subs'] = on and sb.is_ours(os.path.join(prog, sb.DLL))
            except SystemExit:
                s['prepared'] = False
        out['soulbrandt'] = s
    cands = rpcs3_candidates(extra)
    out['rpcs3'] = {'candidates': [dict(game=c, **installed_info(usrdir_of(c))) for c in cands]}
    print(json.dumps(out, ensure_ascii=False))


def cmd_validate(a):
    usr = check_game(a.game)
    emit(step='done', usrdir=usr, **installed_info(usr))


def run_quiet(fn, *args):
    """Run an installer function; its plain prints go to stderr, so stdout carries only the JSON lines."""
    with contextlib.redirect_stdout(_Router()):
        return fn(*args)


class _Router(io.TextIOBase):
    """'@@' lines to the real stdout, the rest to stderr (kept for the log)."""

    def write(self, s):
        for line in s.splitlines(True):
            (sys.__stdout__ if line.startswith('@@') else sys.__stderr__).write(line)
        sys.__stdout__.flush()
        return len(s)


def soulbrandt_args(cmd, fonts=None):
    prog = find_program()
    if not prog:
        raise Fail('no_soulbrandt', 'Não encontrei o Soulbrandt.exe. Coloque a pasta PT-BR dentro da pasta do '
                                    'Soulbrandt e abra de novo.')
    if not sb.has_ready(sb.find_data(prog)):
        raise Fail('not_prepared', 'O Soulbrandt ainda não foi preparado. Abra o Soulbrandt.exe uma vez, deixe ele '
                                   'preparar o jogo até o fim e feche.')
    if sb.game_running():
        raise Fail('running', 'O Soulbrandt está aberto. Feche o jogo e tente de novo.')
    argv = ['ptbr_soulbrandt', cmd, '--program', prog]
    if fonts:
        argv += ['--fontes', fonts]
    return argv


def cmd_install(a):
    emit(step='prepare', target=a.target, fonts=a.fonts)
    if a.target == 'soulbrandt':
        sys.argv = soulbrandt_args('instalar', a.fonts)
        run_quiet(sb.main)
    else:
        usr = check_game(a.game)
        run_quiet(pack.install, usr, TEXT, a.fonts)
    emit(step='done', target=a.target, fonts=a.fonts)


def cmd_uninstall(a):
    emit(step='prepare', target=a.target)
    if a.target == 'soulbrandt':
        sys.argv = soulbrandt_args('desinstalar')
        run_quiet(sb.main)
    else:
        usr = check_game(a.game)
        if not run_quiet(pack.uninstall, usr):
            raise Fail('uninstall', 'Alguns arquivos mudaram depois da instalação e não foram restaurados. '
                                    'Veja o registro para os detalhes.')
    emit(step='done', target=a.target)


def cmd_art(a):
    """Logo + paintings from the player's copy into a.out (PNG)."""
    from PIL import Image
    import gen_ptbr_glyphs as g
    import gen_ptbr_loading as L
    dcx = pack.load('dcx_tool')
    if a.target == 'rpcs3':
        usr = check_game(a.game)
    else:
        prog = find_program()
        if not prog:
            raise Fail('no_soulbrandt', 'Soulbrandt não encontrado.')
        data = sb.find_data(prog)
        game = sb.find_game(data)
        usr = usrdir_of(game)
        if not a.translated:
            ov = sb.overlay_of(data)
            if os.path.normcase(game) == os.path.normcase(ov):
                usr = usrdir_of(sb.overlay_source(ov)) or usr      # the originals, before the translation
    if not usr:
        raise Fail('not_game', 'Jogo não encontrado.')
    os.makedirs(a.out, exist_ok=True)

    def read(rel):
        p = os.path.join(usr, rel)
        if not a.translated and os.path.isfile(os.path.join(usr, pack.BACKUP, rel)):
            p = os.path.join(usr, pack.BACKUP, rel)                # installed in place (RPCS3): the saved original
        return dcx.decode(open(p, 'rb').read())
    # logo: texture Title of menu/menu.tpf; its right part is stored rotated in the strip under the main block
    menu = read('menu/menu.tpf.dcx')
    e = next(x for x in g.tpf_entries(menu) if x['name'] == 'Title')
    img = L.decode(menu[e['off']:e['off'] + e['size']])
    canvas = Image.new('RGB', (1024 + 256, 720), (0, 0, 0))
    canvas.paste(img.crop((0, 0, 1024, 720)), (0, 0))
    # (one row in from each edge of the strip: its outer rows hold the border colour, which drew a seam)
    canvas.paste(img.crop((0, 729, 720, 983)).rotate(90, expand=True), (1025, 0))
    canvas.crop((120, 60, 1170, 510)).convert('L').save(os.path.join(a.out, 'logo.png'))
    n = 0
    for key in L.SCREENS:
        try:
            d = read('menu/%s.tpf.dcx' % key)
        except OSError:
            continue
        e = g.tpf_entries(d)[0]
        img = L.decode(d[e['off']:e['off'] + e['size']])
        if a.translated:
            img = img.crop((0, 0, 1024, L.PIC_H))
        else:
            try:
                # the window shows the painting alone: the name and NOW LOADING painted over with the parchment
                img = L.clean(img, L.SCREENS[key][0])
            except ValueError:
                img = img.crop((0, 0, 1024, L.PIC_H))
        img.save(os.path.join(a.out, key + '.png'))
        n += 1
    emit(step='done', out=a.out, paintings=n, translated=bool(a.translated))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['state', 'validate', 'install', 'uninstall', 'art'])
    ap.add_argument('--target', choices=['soulbrandt', 'rpcs3'], default='soulbrandt')
    ap.add_argument('--fonts', choices=['original', 'hd'], default='original')
    ap.add_argument('--game')
    ap.add_argument('--out')
    ap.add_argument('--translated', action='store_true')
    a = ap.parse_args()
    if a.target == 'rpcs3' and a.cmd in ('install', 'uninstall') and not a.game:
        ap.error('--game is needed for rpcs3')
    try:
        {'state': cmd_state, 'validate': cmd_validate, 'install': cmd_install, 'uninstall': cmd_uninstall,
         'art': cmd_art}[a.cmd](a)
    except Fail as f:
        emit(step='error', code=f.code, message=f.message)
        sys.exit(2)
    except SystemExit as x:
        if x.code in (0, None):
            raise
        msg = str(x.code).strip()
        emit(step='error', code='failed', message=msg.replace('Nao deu certo: ', ''))
        sys.exit(1)
    except Exception as x:          # noqa: BLE001  (shown to the player in plain words, details in the log)
        emit(step='error', code='crash', message='Algo deu errado: %s' % x)
        raise


if __name__ == '__main__':
    main()
