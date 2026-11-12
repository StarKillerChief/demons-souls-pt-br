#!/usr/bin/env python3
"""Build PT-BR-Soulbrandt.zip and update-info.json (upload both to the release). Output goes outside the repository;
it holds no game files.

    build_pack.py --out DIR --cxx CLANG++  (mingw-w64 clang)

It downloads Python's official embeddable package, checked by SHA-256, the same version Soulbrandt's setup uses.
"""
import argparse, hashlib, io, os, shutil, subprocess, sys, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
URL = 'https://www.python.org/ftp/python/3.13.9/python-3.13.9-embed-amd64.zip'
SHA = '91d828c2da3a029b41699e918674a0cb379c02cf20dab9c501306885f837402a'
PILLOW = '12.0.0'
TOOLS = ['ptbr_soulbrandt.py', 'install_ptbr.py', 'gen_ptbr_glyphs.py', 'gen_ptbr_banners.py', 'gen_ptbr_loading.py', 'gen_ptbr_hdfont.py', 'gen_ptbr_freefont.py', 'gen_ptbr_layout.py', 'launcher_backend.py',
         'fmg_tool.py', 'dcx_tool.py',
         'font_mark.py']

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--cxx', required=True)
a = ap.parse_args()
root = os.path.join(a.out, 'PT-BR')
shutil.rmtree(root, ignore_errors=True)
os.makedirs(os.path.join(root, 'pack', 'tools', 'movie_subs'))
for t in TOOLS:
    shutil.copy(os.path.join(REPO, 'tools', t), os.path.join(root, 'pack', 'tools', t))
ms = os.path.join(REPO, 'tools', 'movie_subs')
shutil.copy(os.path.join(ms, 'make_movie_subs.py'), os.path.join(root, 'pack', 'tools', 'movie_subs'))
subprocess.run([a.cxx, '-O2', '-std=c++17', '-shared', '-static', '-s', '-o',
                os.path.join(root, 'pack', 'tools', 'movie_subs', 'avcodec-62.dll'),
                os.path.join(ms, 'avcodec_shim.cpp')], check=True)
shutil.copytree(os.path.join(REPO, 'text'), os.path.join(root, 'pack', 'text'))
shutil.copytree(os.path.join(REPO, 'tools', 'fonts'), os.path.join(root, 'pack', 'tools', 'fonts'))   # EB Garamond (OFL), TeX Gyre Schola (GUST)
for f in ('LICENSE', 'NOTICE.md'):
    shutil.copy(os.path.join(REPO, f), os.path.join(root, 'pack', f))
for f in ('LEIA-ME.txt', 'TERCEIROS.txt'):
    shutil.copy(os.path.join(HERE, f), root)
# the launcher (install, change fonts, uninstall), built with the same compiler
subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'launcher', 'build.py'), '--cxx', a.cxx, '--out', root], check=True)
os.replace(os.path.join(root, 'PT-BR.exe'), os.path.join(root, 'Tradução PT-BR.exe'))
cache = os.path.join(a.out, 'python-embed.zip')
if not os.path.isfile(cache):
    urllib.request.urlretrieve(URL, cache)
data = open(cache, 'rb').read()
if hashlib.sha256(data).hexdigest() != SHA:
    raise SystemExit('python download: wrong SHA-256')
zipfile.ZipFile(io.BytesIO(data)).extractall(os.path.join(root, 'python'))
# Pillow (HPND licence) for the banner textures: the official wheel, unpacked next to the embedded Python
site = os.path.join(root, 'python', 'Lib', 'site-packages')
os.makedirs(site)
wheels = os.path.join(a.out, 'wheels')
subprocess.run([sys.executable, '-m', 'pip', 'download', 'pillow==' + PILLOW, '--only-binary=:all:', '--platform',
                'win_amd64', '--python-version', '3.13', '--no-deps', '-d', wheels, '-q'], check=True)
whl = [f for f in os.listdir(wheels) if f.startswith('pillow-' + PILLOW) and f.endswith('.whl')][0]
zipfile.ZipFile(os.path.join(wheels, whl)).extractall(site)
pth = [f for f in os.listdir(os.path.join(root, 'python')) if f.endswith('._pth')][0]
with open(os.path.join(root, 'python', pth), 'a') as f:
    f.write('Lib/site-packages' + chr(10))
# build stamp: the launcher's "Atualizar" compares it with update-info.json of the newest GitHub release, so a release
# replaced under the same version number is still seen as new
import datetime, json, re
version = re.search(r"VERSION = '([^']+)'", open(os.path.join(REPO, 'tools', 'install_ptbr.py'), encoding='utf-8').read()).group(1)
build = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
json.dump({'version': version, 'build': build}, open(os.path.join(root, 'pack', 'build.json'), 'w', encoding='utf-8'))
zpath = shutil.make_archive(os.path.join(a.out, 'PT-BR-Soulbrandt'), 'zip', a.out, 'PT-BR')
zdata = open(zpath, 'rb').read()
json.dump({'version': version, 'build': build, 'sha256': hashlib.sha256(zdata).hexdigest(), 'size': len(zdata)},
          open(os.path.join(a.out, 'update-info.json'), 'w', encoding='utf-8'), indent=1)
print(zpath)
print(os.path.join(a.out, 'update-info.json'), version, build)
