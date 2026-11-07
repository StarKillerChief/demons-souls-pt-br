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
- six files in the game folder (install_ptbr.py keeps the originals beside them);
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


def find_data(program):
    if os.path.isfile(os.path.join(program, 'portable.txt')):
        return os.path.join(program, 'data', 'setup-data')
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    usual = os.path.join(base, 'DemonsSoulsRecomp')
    try:
        for line in open(os.path.join(usual, 'setup-folder.txt'), encoding='utf-8-sig', errors='replace'):
            line = line.strip()
            if line and not line.startswith('#'):
                return os.path.normpath(line if os.path.isabs(line) else os.path.join(usual, line))
    except OSError:
        pass
    return usual


def find_game(data):
    ready = os.path.join(data, 'setup', 'ready.txt')
    try:
        lines = open(ready, encoding='utf-8-sig', errors='replace').read().splitlines()
    except OSError:
        fail('o Soulbrandt ainda nao foi preparado neste PC. Abra o Soulbrandt.exe, termine a instalacao dele e rode '
             'este instalador de novo.')
    for line in lines:
        if line.startswith('game='):
            game = line[5:].strip()
            return os.path.normpath(game if os.path.isabs(game) else os.path.join(data, game))
    fail('nao encontrei a pasta do jogo em ' + ready)


def is_ours(path):
    try:
        return OUR_MARK in open(path, 'rb').read()
    except OSError:
        return False


def game_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Soulbrandt.exe', '/NH'], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    return 'Soulbrandt.exe' in r.stdout


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['instalar', 'desinstalar', 'estado'])
    ap.add_argument('--program', default=os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
    ap.add_argument('--data')
    a = ap.parse_args()
    program = os.path.abspath(a.program)
    if not os.path.isfile(os.path.join(program, 'Soulbrandt.exe')):
        fail('nao encontrei o Soulbrandt.exe em %s. Extraia esta pasta dentro da pasta do Soulbrandt.' % program)
    data = os.path.abspath(a.data) if a.data else find_data(program)
    game = find_game(data)
    pack = load(os.path.join(HERE, 'install_ptbr.py'), 'install_ptbr')
    usr = pack.find_usrdir(game)
    print('Soulbrandt: ' + program)
    print('Jogo:       ' + game)
    if a.cmd == 'estado':
        print('Traducao:   ' + ('instalada' if pack.read_manifest(usr) else 'nao instalada'))
        print('Legendas:   ' + ('instaladas' if is_ours(os.path.join(program, DLL)) else 'nao instaladas'))
        return
    if game_running():
        fail('feche o Soulbrandt e rode de novo.')
    if a.cmd == 'instalar':
        pack.install(usr, os.path.join(HERE, '..', 'text'))
        install_subs(program, game)
        clear_cache(data)
        print('\nPronto! Abra o Soulbrandt normalmente.')
    else:
        if pack.read_manifest(usr) and not pack.uninstall(usr):
            fail('nao consegui devolver os arquivos originais do jogo.')
        remove_subs(program)
        clear_cache(data)
        print('\nPronto! O jogo voltou ao original.')


if __name__ == '__main__':
    main()
