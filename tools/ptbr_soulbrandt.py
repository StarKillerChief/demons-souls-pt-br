#!/usr/bin/env python3
"""Install or remove the PT-BR pack on an official Soulbrandt install (0.1.1 and later, US version only).

    ptbr_soulbrandt.py instalar    [--program FOLDER] [--data FOLDER]
    ptbr_soulbrandt.py desinstalar [--program FOLDER] [--data FOLDER]
    ptbr_soulbrandt.py estado      [--program FOLDER] [--data FOLDER]

--program  the folder with Soulbrandt.exe. Default: the folder holding the pack's PT-BR folder.
--data     setup's folder. Default: found the way Soulbrandt finds it (below).

Setup's folder: a portable install (portable.txt beside the program) keeps it in data/setup-data; otherwise
%LOCALAPPDATA%/DemonsSoulsRecomp, or the Build folder named by setup-folder.txt inside that folder. setup/ready.txt
there names the game folder, in full or relative to setup's folder.

What it changes, all undone by `desinstalar`:
- nothing in the game folder setup uses (it may be RPCS3's own library folder or the player's disc copy): the
  translation goes into a folder of its own, <setup's folder>/ptbr-game, and ready.txt's game= line points there
  (see build_overlay below); `desinstalar` points it back and deletes that folder;
- avcodec-62.dll in the program folder: the official file is kept as avcodec-62.orig.dll, and movie_subs/ is added;
- setup's game cache (hdd1/cache) is emptied, because the game copies files there and would keep showing old ones.
  The game fills it again by itself. Saves and settings are not touched.

A Soulbrandt update puts its own avcodec-62.dll back and asks for its setup to run again. The translation stays;
movie subtitles return when `instalar` runs again. If anything here is missing, movies simply play with no subtitles.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DLL, ORIG = 'avcodec-62.dll', 'avcodec-62.orig.dll'
OUR_MARK = ORIG.encode()  # the official FFmpeg file never names this


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fail(msg):
    raise SystemExit('\nNao deu certo: ' + msg)


def has_ready(data):
    return os.path.isfile(os.path.join(data, 'setup', 'ready.txt'))


def find_data(program):
    if os.path.isfile(os.path.join(program, 'portable.txt')):
        return os.path.join(program, 'data', 'setup-data')
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    usual = os.path.join(base, 'DemonsSoulsRecomp')
    try:
        for line in open(os.path.join(usual, 'setup-folder.txt'), encoding='utf-8-sig', errors='replace'):
            line = line.strip()
            if line and not line.startswith('#'):
                named = os.path.normpath(line if os.path.isabs(line) else os.path.join(usual, line))
                # a folder chosen on setup's screens but never built in: the build is in the usual place
                return named if has_ready(named) or not has_ready(usual) else usual
    except OSError:
        pass
    return usual


def ready_path(data):
    return os.path.join(data, 'setup', 'ready.txt')


def find_game(data):
    try:
        lines = open(ready_path(data), encoding='utf-8-sig', errors='replace').read().splitlines()
    except OSError:
        fail('o Soulbrandt ainda nao foi preparado neste PC. Abra o Soulbrandt.exe, termine a instalacao dele e rode '
             'este instalador de novo.')
    for line in lines:
        if line.startswith('game='):
            game = line[5:].strip()
            return os.path.normpath(game if os.path.isabs(game) else os.path.join(data, game))
    fail('nao encontrei a pasta do jogo em ' + ready_path(data))


def set_ready_game(data, game):
    """Point setup/ready.txt's game= line at `game`, keeping every other line as it is."""
    p = ready_path(data)
    raw = open(p, 'rb').read().decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in raw else '\n'
    lines = [('game=' + game) if ln.startswith('game=') else ln for ln in raw.splitlines()]
    with open(p + '.tmp', 'w', encoding='utf-8', newline='') as f:
        f.write(nl.join(lines) + nl)
    os.replace(p + '.tmp', p)


# --- The translated game folder -------------------------------------------------------------------------------
# Setup can use the game straight from RPCS3's library (its "Import from RPCS3" route), so the folder ready.txt names
# may belong to RPCS3, or be the player's own disc copy. This tool NEVER writes there. It builds its own folder inside
# setup's folder: real copies of the three folders it changes (font, msg, menu, about 85 MB) and of the loose files,
# and directory junctions (read-only use) to everything else. ready.txt is pointed at it; `desinstalar` points it back.
OVERLAY = 'ptbr-game'
SOURCE_NOTE = '.ptbr-source.txt'
CHANGED = {'ps3_game': {'usrdir': {'font': 'copy', 'msg': 'copy', 'menu': 'copy'}}}


def overlay_of(data):
    return os.path.join(data, OVERLAY)


def overlay_source(ov):
    try:
        return open(os.path.join(ov, SOURCE_NOTE), encoding='utf-8').read().strip()
    except OSError:
        return None


def junction(link, target):
    import _winapi
    _winapi.CreateJunction(target, link)
    if not os.path.isdir(link):
        raise OSError('could not link %s' % link)


def build_overlay(src, ov):
    if not os.path.isdir(os.path.join(src, 'PS3_GAME')):
        fail('a pasta do jogo nao tem PS3_GAME: ' + src)
    os.makedirs(ov)

    def mirror(s, d, spec):
        for name in os.listdir(s):
            sp, dp = os.path.join(s, name), os.path.join(d, name)
            sub = spec.get(name.lower())
            if os.path.isdir(sp):
                if sub == 'copy':
                    shutil.copytree(sp, dp)
                elif sub:
                    os.mkdir(dp)
                    mirror(sp, dp, sub)
                else:
                    junction(dp, sp)
            else:
                shutil.copy2(sp, dp)
    mirror(src, ov, CHANGED)
    with open(os.path.join(ov, SOURCE_NOTE), 'w', encoding='utf-8') as f:
        f.write(src)


def remove_overlay(ov):
    """Delete our folder. Junctions are removed as links only: what they point to is never entered."""
    def rm(d):
        for e in os.scandir(d):
            if e.is_junction() or e.is_symlink():
                os.rmdir(e.path) if e.is_dir() or e.is_junction() else os.remove(e.path)
            elif e.is_dir(follow_symlinks=False):
                rm(e.path)
            else:
                os.chmod(e.path, 0o666)
                os.remove(e.path)
        os.rmdir(d)
    if os.path.isdir(ov):
        rm(ov)


def is_ours(path):
    try:
        return OUR_MARK in open(path, 'rb').read()
    except OSError:
        return False


def game_running():
    # bytes, not text: tasklist answers in the console's code page (UTF-8 under the .bat, the OEM page when run
    # from the launcher), and its Portuguese "INFORMACOES" line does not decode as UTF-8
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Soulbrandt.exe', '/NH'], capture_output=True,
                       stdin=subprocess.DEVNULL)
    return b'Soulbrandt.exe' in (r.stdout or b'')


def clear_cache(data):
    cache = os.path.join(data, 'hdd1', 'cache')
    if os.path.isdir(cache):
        shutil.rmtree(cache, ignore_errors=True)


def install_subs(program, game):
    shim = os.path.join(HERE, 'movie_subs', DLL)
    cur = os.path.join(program, DLL)
    if not os.path.isfile(shim):
        print('Legendas dos filmes: arquivo nao incluido neste pacote, seguindo sem elas.')
        return
    if not os.path.isfile(cur):
        print('Legendas dos filmes: esta versao do Soulbrandt nao tem %s, seguindo sem elas.' % DLL)
        return
    mk = load(os.path.join(HERE, 'movie_subs', 'make_movie_subs.py'), 'make_movie_subs')
    out = os.path.join(program, 'movie_subs')
    shutil.rmtree(out, ignore_errors=True)
    sys.argv = ['make_movie_subs', '--game', game, '--subs', os.path.join(HERE, '..', 'text', 'movies'), '--out', out]
    mk.main()
    if not is_ours(cur):  # first install, or an update put the official file back: keep the file it brought
        shutil.copyfile(cur, os.path.join(program, ORIG))
    shutil.copyfile(shim, cur + '.tmp')
    os.replace(cur + '.tmp', cur)


def remove_subs(program):
    cur, orig = os.path.join(program, DLL), os.path.join(program, ORIG)
    if os.path.isfile(orig):
        if is_ours(cur):
            os.replace(orig, cur)
        else:
            os.remove(orig)  # an update already put its own file back
    shutil.rmtree(os.path.join(program, 'movie_subs'), ignore_errors=True)


def ask_fonts(pack, usr):
    """The player picks the fonts: the game's own, or HD versions of them made on this PC (no mod needed)."""
    if pack.font_mod(usr):
        print('Aviso: encontrei um mod de fonte no seu jogo. Ele fica desligado enquanto a traducao estiver '
              'instalada (a traducao faz as proprias fontes, originais ou HD).')
    print()
    print('Com qual fonte voce quer jogar a traducao?')
    print('   1 - Fontes originais do jogo (como no PS3)')
    print('   2 - Fontes HD (as letras do jogo em alta resolucao, geradas no seu PC)')
    while True:
        try:
            r = input('Digite 1 ou 2 e aperte Enter: ').strip()
        except EOFError:
            r = '1'
        if r in ('1', '2'):
            print()
            return 'original' if r == '1' else 'hd'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['instalar', 'desinstalar', 'estado'])
    ap.add_argument('--program', help='the folder with Soulbrandt.exe (default: the nearest one above this pack)')
    ap.add_argument('--data')
    ap.add_argument('--fontes', choices=['hd', 'original', 'novas'],
                    help='instalar: sem perguntar, usar as fontes originais ou as fontes HD (geradas no PC)')
    a = ap.parse_args()
    if a.program:
        program = os.path.abspath(a.program)
    else:
        # PT-BR/pack/tools is HERE. Windows' "Extract all" adds a folder named after the zip
        # (Soulbrandt/PT-BR-Soulbrandt/PT-BR), so look a few folders up for the program.
        program = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        cand = program
        for _ in range(3):
            if os.path.isfile(os.path.join(cand, 'Soulbrandt.exe')):
                program = cand
                break
            cand = os.path.dirname(cand)
    if not os.path.isfile(os.path.join(program, 'Soulbrandt.exe')):
        fail('nao encontrei o Soulbrandt.exe perto de %s. Coloque a pasta PT-BR dentro da pasta onde esta o '
             'Soulbrandt.exe e rode de novo.' % program)
    data = os.path.abspath(a.data) if a.data else find_data(program)
    game = find_game(data)
    ov = overlay_of(data)
    on = os.path.normcase(game) == os.path.normcase(ov)
    source = overlay_source(ov) if on else game
    pack = load(os.path.join(HERE, 'install_ptbr.py'), 'install_ptbr')
    print('Soulbrandt: ' + program)
    print('Jogo:       ' + (source or game))
    if a.cmd == 'estado':
        print('Traducao:   ' + ('instalada (pasta propria: %s)' % ov if on else 'nao instalada'))
        print('Legendas:   ' + ('instaladas' if is_ours(os.path.join(program, DLL)) else 'nao instaladas'))
        return
    if game_running():
        fail('feche o Soulbrandt e rode de novo.')
    if a.cmd == 'instalar':
        if not on:
            if os.path.isdir(ov):
                remove_overlay(ov)       # left from before a Soulbrandt update rebuilt the game: start fresh
            pack.step('folder')
            print('Preparando uma pasta propria para a traducao (a pasta original do jogo nao e alterada)...')
            build_overlay(game, ov)
            set_ready_game(data, ov)
        try:
            usr = pack.find_usrdir(ov)
            pack.install(usr, os.path.join(HERE, '..', 'text'), a.fontes or ask_fonts(pack, usr))
            pack.step('subs')
            install_subs(program, ov)
        except BaseException:
            if not on:                   # undo: the game goes back to the folder it used before
                set_ready_game(data, game)
                remove_overlay(ov)
            raise
        clear_cache(data)
        print('\nPronto! Abra o Soulbrandt normalmente.')
    else:
        if on:
            if not source or not os.path.isdir(source):
                fail('nao sei para qual pasta do jogo voltar (%s). Nada foi alterado.' % source)
            set_ready_game(data, source)
        remove_overlay(ov)
        remove_subs(program)
        clear_cache(data)
        print('\nPronto! O jogo voltou ao original.')


if __name__ == '__main__':
    main()
