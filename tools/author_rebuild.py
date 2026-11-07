#!/usr/bin/env python3
"""API authors 表重建（与站点统一规则）：从 works 出发，按 tools/dyn_norm.py
重建 authors 表并重映射 works.author_id。供 api_sync.py 在同步末尾调用，
保证 authors 表始终与站点同一规则。幂等：状态已一致时几乎不写。
q(sql, *params) -> [dict]，run([(sql, params)]) -> [rows]，由调用方传入
（tq.py 的 q/run 或 turso.py helper 的等价函数）。
"""
import sys, os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dyn_norm import normalize_works, gn, grp, ndyn

BATCH = 50


def rebuild_authors(q, run, log=print):
    works = q('SELECT author, dynasty, era, author_id, count(*) AS n FROM works GROUP BY author, dynasty, era, author_id')
    authors = q('SELECT id, name, dynasty, era, intro, works FROM authors ORDER BY id')
    cur = {r['id']: r for r in authors}
    max_id = max(cur) if cur else 0

    rows = [(r['author'], r['dynasty'], r['n']) for r in works]
    target, mapping = normalize_works(rows)

    era_c = defaultdict(Counter)
    for r in works:
        nd = mapping[(r['author'], r['dynasty'])]
        era_c[(gn(r['author']), grp(nd))][r['era']] += 1
    intro_by = {}
    for r in authors:
        g = gn(r['name'])
        if r['intro']:
            if g not in intro_by or r['works'] > intro_by[g][1]:
                intro_by[g] = (r['intro'], r['works'])
    intro_by = {g: v[0] for g, v in intro_by.items()}

    old_norm = {r['id']: (gn(r['name']), grp(ndyn(r['dynasty']))) for r in authors}
    by_name = defaultdict(list)
    for r in authors:
        by_name[gn(r['name'])].append(r['id'])

    new_authors = []
    id_map = {}
    next_id = max_id + 1
    for (name, dyn), cnt in sorted(target.items(), key=lambda kv: -kv[1]):
        cands = by_name.get(name, [])
        keeper = None
        for oid in cands:
            if oid not in id_map and old_norm[oid] == (name, dyn):
                keeper = oid
                break
        if keeper is None:
            for oid in sorted(cands, key=lambda o: -cur[o]['works']):
                if oid not in id_map:
                    keeper = oid
                    break
        if keeper is None:
            keeper = next_id
            next_id += 1
        id_map[keeper] = keeper
        new_authors.append([keeper, name, dyn, era_c[(name, dyn)].most_common(1)[0][0], intro_by.get(name), cnt])
        for oid in cands:
            if old_norm[oid] == (name, dyn) and oid not in id_map:
                id_map[oid] = keeper

    key_to_id = {(r[1], r[2]): r[0] for r in new_authors}
    target_authors = {r[0]: r for r in new_authors}

    # 1. 先补齐缺失的 keeper 行
    ins, upd, dele = [], [], []
    for kid, r in target_authors.items():
        if kid not in cur:
            ins.append(('INSERT OR IGNORE INTO authors(id, name, dynasty, era, intro, works) VALUES (?,?,?,?,?,?)', r))
        else:
            c = cur[kid]
            if (c['name'], c['dynasty'], c['era'], c['intro'], c['works']) != (r[1], r[2], r[3], r[4], r[5]):
                upd.append(('UPDATE authors SET name=?, dynasty=?, era=?, intro=?, works=? WHERE id=?',
                            [r[1], r[2], r[3], r[4], r[5], kid]))
    for cid in cur:
        if cid not in target_authors:
            dele.append(cid)
    log(f'[authors] insert {len(ins)}, update {len(upd)}, delete {len(dele)}', flush=True)
    for i in range(0, len(ins), BATCH):
        run(ins[i:i + BATCH])
    # 2. works 重映射
    remap = []
    for r in works:
        nd = mapping[(r['author'], r['dynasty'])]
        nid = key_to_id[(gn(r['author']), grp(nd))]
        if nid != r['author_id']:
            remap.append(('UPDATE works SET author_id=? WHERE author_id=? AND dynasty=?', [nid, r['author_id'], r['dynasty']]))
    log(f'[authors] works remap {len(remap)} groups', flush=True)
    for i in range(0, len(remap), BATCH):
        run(remap[i:i + BATCH])
    # 3. 更新 keeper 行、删多余行、更新 meta
    for i in range(0, len(upd), BATCH):
        run(upd[i:i + BATCH])
    for i in range(0, len(dele), 400):
        ch = dele[i:i + 400]
        run([(f"DELETE FROM authors WHERE id IN ({','.join('?' * len(ch))})", ch)])
    run([("UPDATE meta SET v=(SELECT count(*) FROM authors) WHERE k='authors'", [])])
    # 4. 校验
    n = q('SELECT count(*) AS n FROM authors')[0]['n']
    bad = q('SELECT count(*) AS n FROM works w LEFT JOIN authors a ON a.id = w.author_id WHERE a.id IS NULL')[0]['n']
    badw = q('SELECT count(*) AS n FROM authors a WHERE a.works != (SELECT count(*) FROM works w WHERE w.author_id = a.id)')[0]['n']
    n0 = q('SELECT count(*) AS n FROM authors WHERE works = 0')[0]['n']
    log(f'[authors] verify: authors={n} missing_author={bad} wrong_works={badw} works0={n0}', flush=True)
    if bad or badw or n0:
        raise RuntimeError('author rebuild verification failed')
    return n
