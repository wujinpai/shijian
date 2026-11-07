#!/usr/bin/env python3
"""v45 站点数据：只动陈毅 11 首（元帅陈毅的近现代诗从「清」拆出）。
改动：
  p/ 分片：11 首的朝代改「近现代」，作者 ref 改为新分桶号 md5('近现代|陈毅')%256。
  a/202.json：从「清|陈毅」L 移出 11 首，简介 b/bw/bt 清空（简介属于元帅，随诗走）。
  a/<new_h>.json：新建「近现代|陈毅」条目（简介 + 11 首，保持原顺序）。
  authors.json：清 24->13（无简介），新增近现代 11（有简介），宋 2 不动；按篇数重排。
  pop.json：db（dyb）11 首的朝代字节改「近现代」（dl 已含该值）。
  meta.json：authors 30431->30432。
不改：诗 id、merged.json、s/、l/、其余作者。先校验后写入，可重跑（已是新状态时不再改）。
另把简介文本打印出来，供 Turso 近现代作者行（id 31492）intro 回填用。
"""
import json, os, sys, hashlib, base64

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'app', 'site', 'data')
AB = 256
JIUTI = {356062, 356783, 356784, 356785, 356786, 356787, 356788, 365542, 373755, 375501, 386714}
NEW_KEY = '近现代|陈毅'
NEW_H = int(hashlib.md5(NEW_KEY.encode()).hexdigest(), 16) % AB


def load(p):
    return json.load(open(p, encoding='utf-8'))


def dump(p, obj):
    json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False)


def main():
    print('new bucket:', NEW_H, flush=True)
    meta = load(os.path.join(SITE, 'meta.json'))
    psplit = meta.get('psplit', {})

    # ---- 1. a/202.json：移出 11 首，简介清空
    p202 = os.path.join(SITE, 'a', '202.json')
    b202 = load(p202)
    qing = b202['清|陈毅']
    moved = [e for e in qing['L'] if e[0] in JIUTI]
    assert len(moved) == 11, len(moved)
    assert {e[0] for e in moved} == JIUTI
    bio, bw, bt = qing.get('b', ''), qing.get('bw'), qing.get('bt')
    assert bio.startswith('陈毅（1901年'), bio[:20]
    remaining = [e for e in qing['L'] if e[0] not in JIUTI]
    assert len(remaining) == 13
    if qing.get('b'):
        qing['L'] = remaining
        qing['b'] = ''
        qing.pop('bw', None)
        qing.pop('bt', None)
        dump(p202, b202)
        print('a/202.json: 清|陈毅 24 -> 13, bio cleared', flush=True)
    else:
        print('a/202.json: already done', flush=True)

    # ---- 2. 新分桶条目
    pnew = os.path.join(SITE, 'a', f'{NEW_H}.json')
    nb = load(pnew) if os.path.exists(pnew) else {}
    if NEW_KEY not in nb:
        nb[NEW_KEY] = {'n': '陈毅', 'd': '近现代', 'b': bio, 'bw': bw, 'bt': bt, 'L': moved}
        dump(pnew, nb)
        print(f'a/{NEW_H}.json: created 近现代|陈毅 (11 poems)', flush=True)
    else:
        assert len(nb[NEW_KEY]['L']) == 11 and nb[NEW_KEY]['b'] == bio
        print(f'a/{NEW_H}.json: already done', flush=True)

    # ---- 3. p/ 分片：11 首朝代 + ref
    touched = {}
    for pid in sorted(JIUTI):
        k = pid // 500
        rel = pid % 500
        plain = os.path.join(SITE, 'p', f'{k}.json')
        if os.path.exists(plain):
            fn, idx = plain, rel
        else:
            bounds = psplit[str(k)]
            sub = max(i for i, b in enumerate(bounds) if b <= rel)
            fn, idx = os.path.join(SITE, 'p', f'{k}-{sub}.json'), rel - bounds[sub]
        if fn not in touched:
            touched[fn] = load(fn)
        row = touched[fn][idx]
        assert row is not None and row[1] == '陈毅', (pid, row)
        if row[6] != '近现代' or row[5] != NEW_H:
            row[6] = '近现代'
            row[5] = NEW_H
    for fn, lst in touched.items():
        dump(fn, lst)
    print('p/ shards updated:', sorted(os.path.basename(f) for f in touched), flush=True)

    # ---- 4. authors.json
    pauth = os.path.join(SITE, 'authors.json')
    idx = load(pauth)
    by_key = {(r[0], r[1]): r for r in idx}
    assert by_key[('陈毅', '清')][2] in (24, 13)
    assert by_key[('陈毅', '宋')][2] == 2
    if ('陈毅', '近现代') not in by_key:
        by_key[('陈毅', '清')][2] = 13
        by_key[('陈毅', '清')][4] = 0
        idx.append(['陈毅', '近现代', 11, NEW_H, 1])
        idx.sort(key=lambda e: -e[2])
        dump(pauth, idx)
        print('authors.json: 清 24->13, +近现代 11', flush=True)
    else:
        print('authors.json: already done', flush=True)

    # ---- 5. pop.json db（dyb）
    ppop = os.path.join(SITE, 'pop.json')
    pop = load(ppop)
    dl = pop['dl']
    assert '近现代' in dl and '清' in dl
    dyb = bytearray(base64.b64decode(pop['db']))
    changed = 0
    for pid in JIUTI:
        if dyb[pid] != dl.index('近现代'):
            assert dyb[pid] == dl.index('清'), (pid, dyb[pid])
            dyb[pid] = dl.index('近现代')
            changed += 1
    if changed:
        pop['db'] = base64.b64encode(bytes(dyb)).decode()
        dump(ppop, pop)
    print(f'pop.json db: {changed} poems updated', flush=True)

    # ---- 6. meta.json authors 计数
    if meta.get('authors') == 30431:
        meta['authors'] = 30432
        dump(os.path.join(SITE, 'meta.json'), meta)
        print('meta.json: authors 30431 -> 30432', flush=True)
    else:
        print('meta.json authors =', meta.get('authors'), flush=True)

    # ---- 校验
    b202 = load(p202)
    assert len(b202['清|陈毅']['L']) == 13 and b202['清|陈毅']['b'] == ''
    nb = load(pnew)
    assert len(nb[NEW_KEY]['L']) == 11 and nb[NEW_KEY]['b'] == bio
    idx = load(pauth)
    m = {(r[0], r[1]): r for r in idx}
    assert (m[('陈毅', '清')][2], m[('陈毅', '清')][4]) == (13, 0)
    assert (m[('陈毅', '近现代')][2], m[('陈毅', '近现代')][4]) == (11, 1)
    assert m[('陈毅', '宋')][2] == 2
    assert [e[2] for e in idx] == sorted([e[2] for e in idx], reverse=True)
    pop = load(ppop)
    dyb = bytearray(base64.b64decode(pop['db']))
    assert all(dyb[pid] == dl.index('近现代') for pid in JIUTI)
    print('SITE V45 OK: 陈毅 清 13 / 近现代 11 / 宋 2', flush=True)
    print('BIO-FOR-TURSO-31492-BEGIN')
    print(bio)
    print('BIO-FOR-TURSO-31492-END')


if __name__ == '__main__':
    main()
