#!/usr/bin/env python3
"""Regenerate ./text from the working translation (Portuguese only, entries equal to the source dropped).

    sync_text.py [--src DIR] [--dst DIR] [--check]

--src  working translation tree (default: the path in tools/.sync_src, a git-ignored file with one line, or the
       environment variable PTBR_SRC). Each file is
       <bnd>/<fmg id>_<category>.json with entries {id, en, pt, ...}. The English field is read ONLY to
       decide what to drop; it is never written to the output.
--dst  output folder (default: ../text next to this script).
--check  write nothing; exit 1 if the output would change.

Output entries are {"id": N, "pt": "..."}. An entry is dropped when `pt` is empty or identical to the English
source (the game keeps its own text for ids that are missing, see fmg_tool.py import).
After running, review `git diff --stat` and commit.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def default_src():
    if os.environ.get('PTBR_SRC'):
        return os.environ['PTBR_SRC']
    p = os.path.join(HERE, '.sync_src')
    return open(p, encoding='utf-8').read().strip() if os.path.isfile(p) else None


def build(src):
    out = {}
    for bnd in ('item', 'menu'):
        d = os.path.join(src, bnd)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.json'):
                continue
            j = json.load(open(os.path.join(d, fn), encoding='utf-8'))
            ents = [{'id': e['id'], 'pt': e['pt']} for e in j['entries'] if e.get('pt') and e['pt'] != e.get('en')]
            head = {k: j[k] for k in ('fmg', 'category', 'bnd', 'jp_name', 'flags') if k in j}
            head['entries'] = ents
            out[os.path.join(bnd, fn)] = head
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', default=default_src())
    ap.add_argument('--dst', default=os.path.join(os.path.dirname(HERE), 'text'))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    out = build(a.src)
    if not out:
        raise SystemExit('error: no translation files under %s' % a.src)
    changed = 0
    for rel, j in out.items():
        text = json.dumps(j, ensure_ascii=False, indent=0)
        p = os.path.join(a.dst, rel)
        old = open(p, encoding='utf-8').read() if os.path.isfile(p) else None
        if old != text:
            changed += 1
            if not a.check:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'w', encoding='utf-8', newline='\n').write(text)
    n = sum(len(j['entries']) for j in out.values())
    print('%d files, %d entries, %d file(s) %s' % (len(out), n, changed, 'would change' if a.check else 'written'))
    if a.check and changed:
        sys.exit(1)


if __name__ == '__main__':
    main()
