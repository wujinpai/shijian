#!/usr/bin/env python3
"""诗笺 API authors 表统一迁移：离线算方案（不写库），输出迁移计划 JSON。
输入：/home/hatch/workspace/work/shijian/build/consist/works-agg-backup-2026-11-07.json（works 聚合）、/home/hatch/workspace/work/shijian/build/consist/authors-backup-2026-11-07.json（authors 全表）。
输出：/home/hatch/workspace/work/shijian/build/consist/author-migration-plan-2026-11-07.json。
规则：tools/dyn_norm.py（站点归一 + 分组 + 站点标签覆盖）。
"""
import json, sys
from collections import Counter, defaultdict

sys.path.insert(0, '/home/hatch/workspace/work/shijian/tools')
from dyn_norm import normalize_works, gn, grp, ndyn

works = json.load(open('/home/hatch/workspace/work/shijian/build/consist/works-agg-backup-2026-11-07.json'))['rows']
authors = json.load(open('/home/hatch/workspace/work/shijian/build/consist/authors-backup-2026-11-07.json'))['rows']
old_by_id = {r[0]: r for r in authors}
max_id = max(old_by_id)

rows = [(a, d, n) for a, d, e, aid, n in works]
target, mapping = normalize_works(rows)

era_counter = defaultdict(Counter)
for a, d, e, aid, n in works:
    nd = mapping[(a, d)]
    era_counter[(gn(a), grp(nd))][e] += n
new_era = {k: c.most_common(1)[0][0] for k, c in era_counter.items()}

intro_by_name = {}
for r in authors:
    g = gn(r[1])
    if r[4]:
        if g not in intro_by_name or r[5] > intro_by_name[g][1]:
            intro_by_name[g] = (r[4], r[5])
intro_by_name = {g: v[0] for g, v in intro_by_name.items()}

old_norm = {r[0]: (gn(r[1]), grp(ndyn(r[2]))) for r in authors}
by_name_old = defaultdict(list)
for r in authors:
    by_name_old[gn(r[1])].append(r[0])

new_authors = []
id_map = {}
next_id = max_id + 1
for (name, dyn), cnt in sorted(target.items(), key=lambda kv: -kv[1]):
    cands = by_name_old.get(name, [])
    keeper = None
    for oid in cands:
        if oid not in id_map and old_norm[oid] == (name, dyn):
            keeper = oid
            break
    if keeper is None:
        for oid in sorted(cands, key=lambda o: -old_by_id[o][5]):
            if oid not in id_map:
                keeper = oid
                break
    if keeper is None:
        keeper = next_id
        next_id += 1
    id_map[keeper] = keeper  # keeper 本身被认领，不可再被复用，也不是 orphan
    new_authors.append([keeper, name, dyn, new_era[(name, dyn)], intro_by_name.get(name), cnt])
    for oid in cands:
        if old_norm[oid] == (name, dyn) and oid not in id_map:
            id_map[oid] = keeper

orphans = [oid for oid in old_by_id if oid not in id_map]
print('old authors:', len(old_by_id), 'new authors:', len(new_authors))
print('new ids allocated:', next_id - max_id - 1)
print('orphan old ids:', len(orphans))

key_to_id = {(r[1], r[2]): r[0] for r in new_authors}
# works 重映射：按 (old author_id, 原始 dynasty) -> new id
remap = {}
for a, d, e, aid, n in works:
    nd = mapping[(a, d)]
    nid = key_to_id[(gn(a), grp(nd))]
    if nid != aid:
        remap.setdefault((aid, d), [nid, 0])[1] += n
remap_list = [[aid, d, nid, n] for (aid, d), (nid, n) in sorted(remap.items())]
print('works remap groups (old_id, dynasty -> new_id):', len(remap_list),
      'works affected:', sum(r[3] for r in remap_list))
multi_old = Counter(r[0] for r in remap_list)
print('old ids splitting to >1 new id:', sum(1 for o, c in multi_old.items() if c > 1))

site = json.load(open('/home/hatch/workspace/work/shijian/app/site/data/authors.json'))
site_keys = {}
for row in site:
    k = (gn(row[0]), grp(row[1]))
    site_keys[k] = site_keys.get(k, 0) + row[2]
new_keys = {(r[1], r[2]): r[5] for r in new_authors}
print('new keys:', len(new_keys), 'site keys:', len(site_keys), 'net:', len(new_keys) - len(site_keys))
print('works sum new:', sum(new_keys.values()), 'site:', sum(site_keys.values()))
print('only-new:', len(set(new_keys) - set(site_keys)), 'only-site:', len(set(site_keys) - set(new_keys)))

# 校验 keeper 唯一
kids = [r[0] for r in new_authors]
assert len(kids) == len(set(kids)), 'duplicate keeper id!'
print('keeper ids unique: OK')

plan = {
    'new_authors': new_authors,
    'id_map': {str(k): v for k, v in id_map.items()},
    'remap': remap_list,
    'orphans': orphans,
    'next_id': next_id,
}
json.dump(plan, open('/home/hatch/workspace/work/shijian/build/consist/author-migration-plan-2026-11-07.json', 'w'), ensure_ascii=False)
print('plan saved to /home/hatch/workspace/work/shijian/build/consist/author-migration-plan-2026-11-07.json')
