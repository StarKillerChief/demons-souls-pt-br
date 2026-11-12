#!/usr/bin/env python3
"""Demon's Souls text pipeline (BND3 msgbnd -> FMG): size report, extract, re-import, validate.

Original code (project rule): this tool is committed; the game text it extracts and every translation
stay OUTSIDE the repository (a local work folder). Reads the player's own dump read-only.

Format (docs/fonts.md section 1, docs/localization.md): msgbnd = BND3 (big-endian) of FMGs.
FMG = u32 0x00010000, u32 size, u32 flags(0x01FF0000), u32 groups, u32 strings, u32 string-table offset,
u32 0; groups (u32 first index, u32 first id, u32 last id); u32 offsets (0 = no text); UTF-16BE NUL-terminated.

commands:
  report  <USRDIR> [--lang na_english]                 strings / words / chars per category
  extract <USRDIR> <outdir> [--lang na_english]        outdir/<bnd>/<fmgid>_<category>.json  (source text, ids, limits)
  import  <USRDIR> <trans_dir> <outdir> [--lang ..]    builds outdir/msg/<lang>/<bnd>.msgbnd from translated JSON (plain, no .dcx)
  validate <USRDIR> <trans_dir> [--ccm <ccm>...]       overflow, tags, control codes, untranslated, missing glyphs
JSON per file: {"fmg":id,"category":..,"bnd":..,"entries":[{"id":N,"en":"..","pt":"..","max_chars":N,"max_lines":N}]}
"""
import struct, sys, os, json, re, argparse, collections

# FMG id -> (category, role). Names come from the Japanese entry names + observed content; see localization.md.
CATS = {
    ('item', 10): 'item_names_goods', ('item', 11): 'item_names_weapons', ('item', 12): 'item_names_armor',
    ('item', 13): 'item_names_accessories', ('item', 14): 'item_names_magic', ('item', 15): 'item_names_traits',
    ('item', 16): 'trait_desc', ('item', 17): 'trait_lore', ('item', 18): 'npc_names', ('item', 19): 'place_names',
    ('item', 20): 'goods_desc', ('item', 21): 'weapon_desc', ('item', 22): 'armor_desc', ('item', 23): 'accessory_desc',
    ('item', 24): 'goods_lore', ('item', 25): 'weapon_lore', ('item', 26): 'armor_lore', ('item', 27): 'accessory_lore',
    ('item', 28): 'magic_desc', ('item', 29): 'magic_lore',
}
CONTENT = {  # from the observed strings-per-FMG; refined by content in categorize()
    ('menu', 1): 'dialogue', ('menu', 2): 'blood_messages', ('menu', 3): 'subtitles', ('menu', 30): 'event_text',
    ('menu', 70): 'menu_ingame', ('menu', 76): 'menu_common', ('menu', 77): 'menu_misc', ('menu', 78): 'menu_dialogs',
    ('menu', 79): 'menu_keyguide', ('menu', 80): 'menu_onelinehelp', ('menu', 81): 'menu_itemhelp', ('menu', 90): 'menu_taglist',
}


def read_bnd3(d):
    assert d[:4] == b'BND3'
    n = struct.unpack_from('>I', d, 0x10)[0]
    ents = []
    for i in range(n):
        o = 0x20 + 0x18 * i
        fl, csz, off, id_, noff, usz = struct.unpack_from('>IIIIII', d, o)
        nm = d[noff:d.index(b'\0', noff)]
        ents.append(dict(flags=fl, off=off, size=csz, id=id_, noff=noff, name=nm, data=d[off:off + csz]))
    return ents


def write_bnd3(orig, ents):
    """Rewrite a BND3 with new entry data; header, entry table layout and the name table are kept; data 16-aligned."""
    n = len(ents)
    first = min(e['off'] for e in ents)
    head = bytearray(orig[:first])
    pos = first
    for i, e in enumerate(ents):
        data = e['data']
        pos = (pos + 15) & ~15
        while len(head) < pos:
            head += b'\0'
        head += data
        pos += len(data)
        o = 0x20 + 0x18 * i
        struct.pack_into('>III', head, o + 4 - 4 + 4, len(data), pos - len(data), e['id'])      # size, offset, id
        struct.pack_into('>I', head, o + 20, len(data))                                         # uncompressed size
    return bytes(head)


def parse_fmg(b):
    ver, size, flags, ng, ns, soff = struct.unpack_from('>IIIIII', b, 0)
    # note: header words: 0 version, 4 size, 8 flags, 0xC group count, 0x10 string count, 0x14 table offset
    groups = [struct.unpack_from('>III', b, 0x1c + 12 * i) for i in range(ng)]
    offs = struct.unpack_from('>%dI' % ns, b, soff)
    out = []   # (id, text or None)
    for first, a, z in groups:
        for k, id_ in enumerate(range(a, z + 1)):
            o = offs[first + k]
            if o == 0:
                out.append((id_, None)); continue
            j = o; chars = []
            while True:
                u = struct.unpack_from('>H', b, j)[0]
                if u == 0:
                    break
                chars.append(u); j += 2
            out.append((id_, ''.join(map(chr, chars))))
    return flags, out


def build_fmg(flags, items):
    """items: sorted list of (id, text or None). Groups = runs of consecutive ids."""
    groups, run = [], None
    for idx, (id_, _) in enumerate(items):
        if run and run[2] + 1 == id_:
            run[2] = id_
        else:
            run = [idx, id_, id_]; groups.append(run)
    ng, ns = len(groups), len(items)
    soff = 0x1c + 12 * ng
    strs = bytearray(); offs = []
    base = soff + 4 * ns
    for _, t in items:
        if t is None:
            offs.append(0); continue
        offs.append(base + len(strs))
        strs += t.encode('utf-16-be') + b'\0\0'
    body = b''.join(struct.pack('>III', *g) for g in groups) + struct.pack('>%dI' % ns, *offs) + bytes(strs)
    size = 0x1c + len(body)
    return struct.pack('>IIIIIII', 0x00010000, size, flags, ng, ns, soff, 0) + body


def jp_name(raw):
    try:
        return raw.decode('shift_jis').split('\\')[-1]
    except Exception:
        return '?'


def category(bnd, fid, name):
    return CATS.get((bnd, fid)) or CONTENT.get((bnd, fid)) or '%s_%d' % (bnd, fid)


def words(t):
    return len(re.findall(r"\S+", t))


def load_all(usr, lang):
    res = []
    for bnd in ('item', 'menu'):
        p = os.path.join(usr, 'msg', lang, bnd + '.msgbnd')
        d = open(p, 'rb').read()
        for e in read_bnd3(d):
            flags, items = parse_fmg(e['data'])
            res.append(dict(bnd=bnd, fid=e['id'], name=jp_name(e['name']), flags=flags, items=items))
    return res


def cmd_report(usr, lang):
    tot = collections.Counter(); tu = collections.Counter()
    print('%-8s %4s %-22s %7s %8s %9s  %s' % ('bnd', 'fmg', 'category', 'strings', 'words', 'chars', 'jp entry name'))
    for f in load_all(usr, lang):
        txt = [t for _, t in f['items'] if t]
        uq = set(txt); tu.update(strings=len(uq), words=sum(words(t) for t in uq))
        s, w, c = len(txt), sum(words(t) for t in txt), sum(len(t) for t in txt)
        tot.update(strings=s, words=w, chars=c)
        print('%-8s %4d %-22s %7d %8d %9d  %s' % (f['bnd'], f['fid'], category(f['bnd'], f['fid'], f['name']), s, w, c, f['name']))
    print('TOTAL strings %(strings)d words %(words)d chars %(chars)d' % tot)
    print('per-FMG unique: strings %(strings)d words %(words)d' % tu)


def cmd_extract(usr, out, lang):
    for f in load_all(usr, lang):
        cat = category(f['bnd'], f['fid'], f['name'])
        os.makedirs(os.path.join(out, f['bnd']), exist_ok=True)
        ents = []
        for id_, t in f['items']:
            if t is None:
                continue
            lines = t.split('\n')
            ents.append(dict(id=id_, en=t, pt='', max_lines=len(lines), max_chars=max(len(l) for l in lines) if lines else 0,
                             total_chars=len(t), tags=sorted(set(re.findall(r'<[^>]*>|%[sd0-9.]*[sdf]|\{[^}]*\}', t)))))
        json.dump(dict(fmg=f['fid'], category=cat, bnd=f['bnd'], jp_name=f['name'], flags=f['flags'], entries=ents),
                  open(os.path.join(out, f['bnd'], '%02d_%s.json' % (f['fid'], cat)), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('extracted to', out)


def load_trans(tdir):
    out = {}
    for bnd in ('item', 'menu'):
        d = os.path.join(tdir, bnd)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.json'):
                j = json.load(open(os.path.join(d, fn), encoding='utf-8'))
                out[(bnd, j['fmg'])] = j
    return out


def cmd_import(usr, tdir, out, lang):
    tr = load_trans(tdir)
    for bnd in ('item', 'menu'):
        p = os.path.join(usr, 'msg', lang, bnd + '.msgbnd')
        d = open(p, 'rb').read()
        ents = read_bnd3(d)
        for e in ents:
            j = tr.get((bnd, e['id']))
            if not j:
                continue
            flags, items = parse_fmg(e['data'])
            pt = {x['id']: x['pt'] for x in j['entries'] if x['pt']}
            have = {i for i, _ in items}
            lost = sorted(set(pt) - have)
            if lost:   # another translation installed earlier removed or renumbered these: put ours back
                print('note: %s fmg %d lacked %d entries the US disc has (%s...); added them'
                      % (bnd, e['id'], len(lost), ','.join(map(str, lost[:8]))))
            e['data'] = build_fmg(flags, sorted([(i, pt.get(i, t)) for i, t in items] + [(i, pt[i]) for i in lost]))
        missing = sorted({k[1] for k in tr if k[0] == bnd} - {e['id'] for e in ents})
        if missing:
            print('note: %s.msgbnd has no fmg %s (changed by another mod?); that text stays as it is'
                  % (bnd, ','.join(map(str, missing))))
        os.makedirs(os.path.join(out, 'msg', lang), exist_ok=True)
        open(os.path.join(out, 'msg', lang, bnd + '.msgbnd'), 'wb').write(write_bnd3(d, ents))
    print('wrote', os.path.join(out, 'msg', lang))


def ccm_codepoints(p):
    b = open(p, 'rb').read()
    ngrp = struct.unpack_from('>H', b, 0x10)[0]
    s = set()
    for i in range(ngrp):
        a, e, _ = struct.unpack_from('>III', b, 0x20 + 12 * i)
        s.update(range(a, e + 1))
    return s


def ccm_advances(p):
    b = open(p, 'rb').read()
    ngrp, ng = struct.unpack_from('>HH', b, 0x10)
    oreg = struct.unpack_from('>I', b, 0x18)[0]
    adv = {}
    for i in range(ngrp):
        a, z, g = struct.unpack_from('>III', b, 0x20 + 12 * i)
        for k, cp in enumerate(range(a, z + 1)):
            adv[cp] = struct.unpack_from('>H', b, oreg + 24 * (g + k) + 20)[0]
    return adv


def px_width(t, adv):
    return max((sum(adv.get(ord(c), 12) for c in line) for line in t.split(chr(10))), default=0)


def validate_entry(e, cps, adv=None):
    issues = []
    en, pt = e['en'], e['pt']
    if not pt:
        return ['untranslated']
    if len(pt.split('\n')) > e['max_lines'] + 1:
        issues.append('lines %d > %d+1' % (len(pt.split('\n')), e['max_lines']))
    if adv:   # pixel width of the widest line vs the English one (UI boxes were sized for English)
        w_en, w_pt = px_width(en, adv), px_width(pt, adv)
        if w_pt > w_en * 1.5 and w_pt - w_en > 50:
            issues.append('width %d px > 1.5 x %d px (EN)' % (w_pt, w_en))
    else:
        lim = max(e['max_chars'], 1)
        worst = max(len(l) for l in pt.split(chr(10)))
        if worst > lim * 1.35 and worst > 12:
            issues.append('line length %d > 1.35 x %d (EN)' % (worst, lim))
    if sorted(set(re.findall(r'<[^>]*>|%[sd0-9.]*[sdf]|\{[^}]*\}', pt))) != e['tags']:
        issues.append('tags differ: %s vs %s' % (sorted(re.findall(r'<[^>]*>|%[sd0-9.]*[sdf]|\{[^}]*\}', pt)), e['tags']))
    if any(ord(c) < 32 and c != '\n' for c in pt):
        issues.append('control character')
    if en.count('\n') and not pt.count('\n') and len(en) > 40:
        issues.append('line breaks lost')
    if cps:
        miss = sorted({c for c in pt if ord(c) not in cps and c != '\n'})
        if miss:
            issues.append('no glyph: ' + ''.join(miss))
    return issues


def cmd_validate(tdir, ccms):
    cps = adv = None
    if ccms:
        cps = set.intersection(*[ccm_codepoints(p) for p in ccms])
        adv = ccm_advances(ccms[0])
    tot = bad = done = 0
    for (bnd, fid), j in sorted(load_trans(tdir).items()):
        fb = fd = 0
        for e in j['entries']:
            tot += 1
            iss = validate_entry(e, cps, adv)
            if iss == ['untranslated']:
                continue
            done += 1; fd += 1
            if iss:
                bad += 1; fb += 1
                if fb <= 5:
                    print('%s/%02d id %d: %s' % (bnd, fid, e['id'], '; '.join(iss)))
        print('%s/%02d %-20s translated %d/%d, with issues %d' % (bnd, fid, j['category'], fd, len(j['entries']), fb))
    print('TOTAL entries %d translated %d with issues %d' % (tot, done, bad))


def cat_entries(tdir, cats):
    for (bnd, fid), j in sorted(load_trans(tdir).items()):
        if j['category'] in cats:
            yield j


def cmd_worklist(tdir, cat, out):
    """Unique source strings of a category, numbered, one per line (a newline is written as backslash-n)."""
    seen = []
    for j in cat_entries(tdir, [cat]):
        for e in j['entries']:
            if e['en'] not in seen:
                seen.append(e['en'])
    os.makedirs(out, exist_ok=True)
    NL = chr(10)
    with open(os.path.join(out, cat + '.en.txt'), 'w', encoding='utf-8') as f:
        for i, t in enumerate(seen):
            f.write('%d\t%s\n' % (i, t.replace(NL, '\\n')))
    json.dump(seen, open(os.path.join(out, cat + '.map.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(cat, len(seen), 'unique strings')


def cmd_merge(work, cat, tm_dir):
    """Merge <cat>.pt*.txt (same numbering, 'n<TAB>text') into tm/<cat>.json {english: portuguese}."""
    seen = json.load(open(os.path.join(work, cat + '.map.json'), encoding='utf-8'))
    tm = {}
    p = os.path.join(tm_dir, cat + '.json')
    if os.path.exists(p):
        tm = json.load(open(p, encoding='utf-8'))
    NL = chr(10)
    for fn in sorted(os.listdir(work)):
        if fn.startswith(cat + '.pt') and fn.endswith('.txt'):
            for ln in open(os.path.join(work, fn), encoding='utf-8'):
                ln = ln.rstrip('\n')
                if '\t' in ln:
                    n, t = ln.split('\t', 1)
                    if n.isdigit() and int(n) < len(seen) and t.strip():
                        tm[seen[int(n)]] = t.replace('\\n', NL)
    os.makedirs(tm_dir, exist_ok=True)
    json.dump(tm, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(cat, 'tm entries', len(tm), 'of', len(seen))


def cmd_apply(tdir, tm_dir):
    """Fill 'pt' of every entry from the translation memory (exact English match, any category)."""
    tm = {}
    for fn in os.listdir(tm_dir):
        if fn.endswith('.json'):
            tm.update(json.load(open(os.path.join(tm_dir, fn), encoding='utf-8')))
    for (bnd, fid), j in load_trans(tdir).items():
        n = 0
        for e in j['entries']:
            if e['en'] in tm:
                e['pt'] = tm[e['en']]; n += 1
        fn = [x for x in os.listdir(os.path.join(tdir, bnd)) if x.startswith('%02d_' % fid)][0]
        json.dump(j, open(os.path.join(tdir, bnd, fn), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print('%s/%02d %-18s %d/%d filled' % (bnd, fid, j['category'], n, len(j['entries'])))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8'); a = sys.argv[1:]
    lang = a[a.index('--lang') + 1] if '--lang' in a else 'na_english'
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == 'report': cmd_report(a[1], lang)
    elif a[0] == 'extract': cmd_extract(a[1], a[2], lang)
    elif a[0] == 'import': cmd_import(a[1], a[2], a[3], lang)
    elif a[0] == 'worklist': cmd_worklist(a[1], a[2], a[3])
    elif a[0] == 'merge': cmd_merge(a[1], a[2], a[3])
    elif a[0] == 'apply': cmd_apply(a[1], a[2])
    elif a[0] == 'validate': cmd_validate(a[1], a[a.index('--ccm') + 1:] if '--ccm' in a else [])
