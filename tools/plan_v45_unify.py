#!/usr/bin/env python3
"""v45 干跑：诗笺作者统一残差 -14 + 陈毅拆分。
目标（用户 2026-11-07 定夺“统一吧”）：
- 70 人残差按站点口径统一：Turso works 的逐首朝代改为站点逐首朝代，API 与站点一致。
- 陈毅：三人同名须拆分——宋 2 首（全宋诗）、清 13 首（晚晴簃诗汇卷八十六：陈毅字直方号古渔上元人）、
  近现代 11 首（元帅陈毅 1901-1972：青松/梅岭三章/雪夜行军等，jiuti 合集）。站点与 API 目前都把 11 首并入清，
  因 load.py/dyn_norm.py 的 ADJ 清-近现代合并；须把陈毅加入 NOMERGE，并把 11 首逐首改回近现代。
- 佚名不动（对照表建议：两边总数同为 8245，站点多历代 4 首/南北朝 3 首两个键，不逐首定）。
只算计划、不写库。输出 build/consist/v45-unify-plan.json。
"""
import json, os, sys, collections, subprocess, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dyn_norm import gn, grp, ndyn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'app', 'site', 'data')
CONS = os.path.join(ROOT, 'build', 'consist')
TURSO = '/home/hatch/workspace/custom-connectors/custom.turso/bin/turso.py'

def tq(sql):
    out = subprocess.run(['python3', TURSO, 'query', '--org', 'jisu', '--db', 'shijian-v2',
                          '--sql', sql], capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stdout + out.stderr)
    d = json.loads(out.stdout)
    return [dict(zip(d['cols'], r)) for r in d['rows']]

# ---- 1. 目标人名：新鲜 live 与站点归一对照（与 author-residual 表一致：-14，29/43/79）
live_authors = json.load(open(os.path.join(CONS, 'live-authors-2026-11-07.json')))
site_idx = json.load(open(os.path.join(SITE, 'authors.json')))
def norm_agg(rows):
    c = collections.Counter()
    for r in rows:
        if isinstance(r, dict):
            c[(gn(r['name']), grp(ndyn(r['dynasty'])))] += r['works']
        else:
            c[(gn(r[0]), grp(ndyn(r[1])))] += r[2]
    return c
live_n = norm_agg(live_authors)
site_n = norm_agg(site_idx)
target_names = set()
for k in set(live_n) | set(site_n):
    if live_n.get(k, 0) != site_n.get(k, 0):
        target_names.add(k[0])
target_names.discard('佚名')
target_names.add('陈毅')
print('target names:', len(target_names))

# live 侧人名拼写（works.author 用仓库拼写，以 authors 表为准）
live_spell = collections.defaultdict(set)
for a in live_authors:
    if gn(a['name']) in target_names:
        live_spell[gn(a['name'])].add(a['name'])
# 异体字：works.author 可能是未归一的原始拼写（如于瓌/屠瓌智），authors.name 是 gn 归一后。
# 把每个目标名的每个字展开为“归一形/异体形”全部组合，避免 IN 过滤漏行；匹配时仍以 gn() 为准。
from dyn_norm import STDV
REV = {}
for _var, _norm in STDV.items():
    REV.setdefault(_norm, set()).add(_var)
    REV.setdefault(_var, set()).add(_norm)
def variants(name):
    outs = ['']
    for ch in name:
        alts = sorted(REV.get(ch, {ch}))
        outs = [o + a for o in outs for a in alts]
    return outs
cand_spell = set()
for g in target_names:
    cand_spell.update(variants(g))
    cand_spell.update(live_spell.get(g, set()))
for r in site_idx:
    if gn(r[0]) in target_names:
        cand_spell.add(r[0])
print('candidate spellings:', len(cand_spell))

# ---- 2. 站点逐首朝代：a/ 分桶（key 为 grp(d)|人名，entry['d'] 为原始朝代）
# 注意：唐/五代在 key 上合并，但目标作者中无人同时有唐与五代两个原始键（下面校验）。
site_poems = {}   # (gn(author), title, first16) -> [site_dynasty, poem_id]
site_by_author = collections.defaultdict(list)
for fn in sorted(os.listdir(os.path.join(SITE, 'a'))):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(SITE, 'a', fn)))
    # 两种形态：分桶 a/<hash>.json 是 {key: entry}；大作者 a/x<N>-<pi>.json 是单个 entry
    if isinstance(d, dict) and 'n' in d and 'L' in d:
        entries = [(grp(d['d']) + '|' + d['n'], d)]
    else:
        entries = list(d.items())
    for key, e in entries:
        gname = gn(e['n'])
        if gname not in target_names:
            continue
        for pid, title, first16 in e['L']:
            site_by_author[gname].append((pid, title, first16, e['d']))
            site_poems.setdefault((gname, title, first16), []).append((e['d'], pid))
multi = {k: v for k, v in site_poems.items() if len(set(x[0] for x in v)) > 1}
print('site poems:', sum(len(v) for v in site_by_author.values()),
      'ambiguous (same author+title+first16, diff dynasty):', len(multi))
for k, v in list(multi.items())[:10]:
    print('  AMBIG', k, v)

# ---- 3. Turso works（目标作者）
names_sql = sorted(cand_spell)
ph = ','.join("'%s'" % n.replace("'", "''") for n in names_sql)
works = tq("SELECT id, title, author, dynasty, era, content FROM works WHERE author IN (%s)" % ph)
print('turso works rows:', len(works))
# era 分布：修正时 era 是否跟 dynasty 走
ed = collections.Counter((w['dynasty'], w['era']) for w in works)
print('dynasty==era rows:', sum(n for (d, e), n in ed.items() if d == e), '/', len(works))
print('dynasty!=era:', [(k, v) for k, v in ed.items() if k[0] != k[1]][:10])

CHENYI_JIUTI = {356062, 356783, 356784, 356785, 356786, 356787, 356788,
                365542, 373755, 375501, 386714}  # 站点 jiuti 合集 id，元帅陈毅 11 首
corrections = []   # (works_id, author, title, old_dyn, new_dyn, old_era, new_era)
unmatched_turso = []
unmatched_site = set()
used_site_keys = set()
for w in works:
    gname = gn(w['author'])
    first = (w['content'].split('\n')[0] if w['content'] else '').strip()[:16]
    key = (gname, w['title'].strip(), first)
    cands = site_poems.get(key)
    if not cands:
        unmatched_turso.append(w)
        continue
    used_site_keys.add(key)
    dyns = sorted(set(d for d, _ in cands))
    if len(dyns) > 1:
        unmatched_turso.append({**w, '_ambig': cands})
        continue
    new_dyn = dyns[0]
    # 陈毅：站点逐首朝代来自 a/ 分桶——但分桶里的 11 首 jiuti 诗在站点也被并入清，
    # 须用诗 id 判定：jiuti 合集的 11 首目标为近现代。其余按站点。
    if gname == '陈毅':
        # Turso id 与站点诗 id 不同源；用 (title, first16) 在站点 jiuti id 集合里反查
        site_ids = [pid for _, pid in cands]
        if any(pid in CHENYI_JIUTI for pid in site_ids):
            new_dyn = '近现代'
    if new_dyn != w['dynasty']:
        new_era = new_dyn if w['era'] == w['dynasty'] else w['era']
        corrections.append({'id': w['id'], 'author': w['author'], 'title': w['title'],
                            'old_dynasty': w['dynasty'], 'new_dynasty': new_dyn,
                            'old_era': w['era'], 'new_era': new_era})
for k, v in site_poems.items():
    if k not in used_site_keys:
        unmatched_site.add(k)
print('corrections:', len(corrections))
print('unmatched turso works:', len(unmatched_turso))
for w in unmatched_turso[:15]:
    print('  UNMATCHED-T', w.get('id'), w.get('author'), w.get('title'), w.get('dynasty'), w.get('_ambig', ''))
print('unmatched site poems:', len(unmatched_site))
for k in sorted(unmatched_site)[:15]:
    print('  UNMATCHED-S', k, site_poems[k])

# ---- 4. 干跑预测：修正后的 works 聚合 -> dyn_norm 归一（陈毅 NOMERGE）-> 与站点归一对照
# 修正后聚合：以 Turso 现有 works 聚合为基，逐首改朝代
agg = collections.Counter()
for w in works:
    agg[(gn(w['author']), w['dynasty'])] += 1
for c in corrections:
    agg[(gn(c['author']), c['old_dynasty'])] -= 1
    agg[(gn(c['author']), c['new_dynasty'])] += 1
# 其余作者（非目标）保持 live 不变：用 live 全表聚合
full = collections.Counter()
for a in live_authors:
    full[(gn(a['name']), a['dynasty'])] += a['works']
# 把目标作者的全表聚合替换为修正后聚合（目标作者的诗都在 works 查询里；佚名未动）
for (g, d) in list(full):
    if g in target_names:
        del full[(g, d)]
for (g, d), n in agg.items():
    if n:
        full[(g, d)] += n
# dyn_norm 归一（含 NOMERGE 陈毅的效果：手工模拟——author_fix 跳过陈毅）
import dyn_norm as DN
rows = [(g, d, n) for (g, d), n in full.items() if n]
# normalize_works 内部用 gn() 再归一；陈毅需 NOMERGE：临时打补丁
_orig_nomer = DN.NOMERGE
DN.NOMERGE = _orig_nomer | {'陈毅'}
# normalize_works 要求 rows 为 (作者, 朝代, 篇数)；它内部再 gn/ndyn/grp
target_out, _map = DN.normalize_works(rows)
DN.NOMERGE = _orig_nomer
pred = collections.Counter({k: v for k, v in target_out.items()})
# 目标站点归一：陈毅按拆分后（清 13/近现代 11/宋 2），佚名按 live（不动）
want = collections.Counter()
for (g, d), n in site_n.items():
    if g == '佚名':
        continue
    want[(g, d)] = n
want[('陈毅', '清')] = 13
want[('陈毅', '近现代')] = 11
want[('陈毅', '宋')] = 2
for (g, d) in list(want):
    if g == '陈毅' and d not in ('清', '近现代', '宋'):
        del want[(g, d)]
pred_f = {k: v for k, v in pred.items() if k[0] != '佚名'}
want_f = dict(want)
mismatch = []
for k in set(pred_f) | set(want_f):
    if pred_f.get(k, 0) != want_f.get(k, 0):
        mismatch.append((k, pred_f.get(k, 0), want_f.get(k, 0)))
print('predicted mismatch (excl 佚名):', len(mismatch))
for m in sorted(mismatch, key=lambda x: -abs((x[1] or 0) - (x[2] or 0)))[:20]:
    print('  MISMATCH', m)
print('predicted total keys:', len([k for k in pred if pred[k]]), 'site norm keys:', len(site_n))

json.dump({'corrections': corrections,
           'unmatched_turso': [{k: v for k, v in w.items() if k != 'content'} for w in unmatched_turso],
           'unmatched_site': sorted([list(k) for k in unmatched_site]),
           'mismatch': [[list(k), v1, v2] for k, v1, v2 in mismatch],
           'target_names': sorted(target_names)},
          open(os.path.join(CONS, 'v45-unify-plan.json'), 'w'), ensure_ascii=False, indent=1)
print('plan written')
