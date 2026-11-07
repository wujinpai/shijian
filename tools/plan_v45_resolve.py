#!/usr/bin/env python3
"""v45 二次干跑：对仍有残差的作者用全文内容逐首配对，解决 first16 碰撞/典籍标题差异。
输入 build/consist/v45-unify-plan.json；输出 build/consist/v45-unify-plan2.json。
另验证：李好古/释子温须按人豁免相邻合并（站点把宋/元分开，实为同名不同人），
陈毅亦然；其余作者沿用 dyn_norm 合并规则。
"""
import json, os, sys, collections, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dyn_norm import gn, grp, ndyn, STDV
from canon_lib import nz, near

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'app', 'site', 'data')
CONS = os.path.join(ROOT, 'build', 'consist')
TURSO = '/home/hatch/workspace/custom-connectors/custom.turso/bin/turso.py'
META = json.load(open(os.path.join(SITE, 'meta.json')))
PSPLIT = META.get('psplit', {})

def tq(sql):
    out = subprocess.run(['python3', TURSO, 'query', '--org', 'jisu', '--db', 'shijian-v2',
                          '--sql', sql], capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stdout + out.stderr)
    d = json.loads(out.stdout)
    return [dict(zip(d['cols'], r)) for r in d['rows']]

plan = json.load(open(os.path.join(CONS, 'v45-unify-plan.json')))
base_corr = plan['corrections']
mismatch_authors = sorted({k[0] for k, _, _ in plan['mismatch']})
unmatched_authors = sorted({w['author'] for w in plan['unmatched_turso']})
re_authors = sorted(set(mismatch_authors) | set(unmatched_authors) | {'吕岩', '高氏', '徐氏', '王谟', '贾岛', '王鉴'})
print('re-resolve authors:', re_authors)

# ---- 站点：a/ 分桶取诗 id，再读 p/ 分片取全文与真实朝代
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

site_entries = collections.defaultdict(list)  # gn(author) -> [(pid, title, bucket_dyn)]
for fn in sorted(os.listdir(os.path.join(SITE, 'a'))):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(SITE, 'a', fn)))
    entries = [(d['d'], d)] if isinstance(d, dict) and 'n' in d and 'L' in d else [(e['d'], e) for e in d.values()]
    for dd, e in entries:
        if gn(e['n']) in re_authors:
            for pid, title, _f16 in e['L']:
                site_entries[gn(e['n'])].append((pid, title, dd))

_pcache = {}
def poem_row(pid):
    k = pid // 500
    rel = pid % 500
    if k not in _pcache:
        plain = os.path.join(SITE, 'p', f'{k}.json')
        if os.path.exists(plain):
            _pcache[k] = json.load(open(plain))
        else:
            bounds = PSPLIT[str(k)]
            sub = max(i for i, b in enumerate(bounds) if b <= rel)
            _pcache[k] = (json.load(open(os.path.join(SITE, 'p', f'{k}-{sub}.json'))), bounds[sub])
    v = _pcache[k]
    if isinstance(v, tuple):
        lst, base = v
        return lst[rel - base]
    return v[rel]

site_poems = []  # (pid, author, title, dyn, nz_text)
for gname, lst in site_entries.items():
    for pid, title, dd in lst:
        row = poem_row(pid)
        assert row is not None, pid
        paras = row[3] if len(row) > 3 else []
        site_poems.append({'pid': pid, 'author': row[1], 'title': row[0],
                           'dyn': row[6], 'nz': nz(''.join(paras))})
print('site poems (re-resolve authors):', len(site_poems))
# 校验：分桶朝代与 p/ 行朝代一致？
bad = [s for s in site_poems if True]
n_mismatch_dyn = 0
for gname, lst in site_entries.items():
    for pid, title, dd in lst:
        row = poem_row(pid)
        if row[6] != dd:
            n_mismatch_dyn += 1
            if n_mismatch_dyn <= 5:
                print('  BUCKET-DYN-DIFF', pid, title, 'bucket', dd, 'p/', row[6])
print('bucket vs p/ dynasty diffs:', n_mismatch_dyn)

# ---- Turso：重解作者全量行（含 content/kind/book/chapter）
cand = set()
for g in re_authors:
    cand.update(variants(g))
live_authors = json.load(open(os.path.join(CONS, 'live-authors-2026-11-07.json')))
for a in live_authors:
    if gn(a['name']) in re_authors:
        cand.add(a['name'])
site_idx = json.load(open(os.path.join(SITE, 'authors.json')))
for r in site_idx:
    if gn(r[0]) in re_authors:
        cand.add(r[0])
ph = ','.join("'%s'" % n.replace("'", "''") for n in sorted(cand))
trows = tq("SELECT id, title, author, dynasty, era, kind, book, chapter, content FROM works WHERE author IN (%s)" % ph)
print('turso rows (re-resolve authors):', len(trows))

# ---- 全文配对：nz 精确，其次 near（同长、差异 ≤10%）
by_nz = collections.defaultdict(list)
for s in site_poems:
    by_nz[s['nz']].append(s)
new_corr = []
paired_t = set()
paired_s = set()
leftover_t = []
for w in trows:
    w_nz = nz(w['content'] or '')
    cands = by_nz.get(w_nz, [])
    # 典籍：标题是章节名，站点标题是“书·章节”；全文 nz 已可配对，无需特殊处理
    if len(cands) == 1:
        s = cands[0]
        paired_t.add(w['id']); paired_s.add(s['pid'])
        if s['dyn'] != w['dynasty']:
            new_era = s['dyn'] if w['era'] == w['dynasty'] else w['era']
            new_corr.append({'id': w['id'], 'author': w['author'], 'title': w['title'],
                             'old_dynasty': w['dynasty'], 'new_dynasty': s['dyn'],
                             'old_era': w['era'], 'new_era': new_era})
    elif len(cands) > 1:
        # 同文多首：按 (dynasty, era) 提示配对——取与 Turso dynasty/era 最接近的站点朝代
        # （如李世民冬宵：Turso 隋末唐初/隋 -> 站点隋；唐/唐 -> 站点唐）
        pref = [s for s in cands if s['dyn'] == w['dynasty'] or s['dyn'] == w['era']]
        pick = pref[0] if pref else cands[0]
        paired_t.add(w['id']); paired_s.add(pick['pid'])
        if pick['dyn'] != w['dynasty']:
            new_era = pick['dyn'] if w['era'] == w['dynasty'] else w['era']
            new_corr.append({'id': w['id'], 'author': w['author'], 'title': w['title'],
                             'old_dynasty': w['dynasty'], 'new_dynasty': pick['dyn'],
                             'old_era': w['era'], 'new_era': new_era})
    else:
        leftover_t.append(w)
print('paired:', len(paired_t), 'new corrections:', len(new_corr))
print('leftover turso rows:', len(leftover_t))
for w in leftover_t:
    print('  LEFT-T', w['id'], w['author'], repr(w['title']), w['dynasty'], w['kind'], w.get('book'), w.get('chapter'))
left_s = [s for s in site_poems if s['pid'] not in paired_s]
print('leftover site poems:', len(left_s))
for s in left_s:
    print('  LEFT-S', s['pid'], s['author'], repr(s['title']), s['dyn'])

# ---- 合并修正清单：去掉重解作者的旧修正，换上新修正
re_gn = set(re_authors)
final_corr = [c for c in base_corr if gn(c['author']) not in re_gn] + new_corr
print('final corrections:', len(final_corr))

# ---- 重新模拟预测：基底必须是 works 级聚合（ndyn 后），不能用已合并过的 authors 表。
# （authors 表的朝代已是归一结果；逐首修正的 old_dynasty 是 works 原始值，必须 ndyn 后再增减。）
NOMERGE_EXTRA = {'陈毅', '李好古', '释子温', '孙光宪', '李世民', '王谟', '贾岛'}
import dyn_norm as DN
agg = tq("SELECT author, dynasty, COUNT(*) AS c FROM works GROUP BY author, dynasty")
full = collections.Counter()
for r in agg:
    full[(gn(r['author']), ndyn(r['dynasty']))] += r['c']
for c in final_corr:
    g = gn(c['author'])
    full[(g, ndyn(c['old_dynasty']))] -= 1
    full[(g, ndyn(c['new_dynasty']))] += 1
rows = [(g, d, n) for (g, d), n in full.items() if n]
_orig = DN.NOMERGE
DN.NOMERGE = _orig | NOMERGE_EXTRA
target_out, _m = DN.normalize_works(rows)
DN.NOMERGE = _orig
pred = collections.Counter(dict(target_out))
site_n = collections.Counter()
for r in site_idx:
    site_n[(gn(r[0]), grp(ndyn(r[1])))] += r[2]
want = collections.Counter()
for (g, d), n in site_n.items():
    if g == '佚名':
        continue
    want[(g, d)] = n
want[('陈毅', '清')] = 13
want[('陈毅', '近现代')] = 11
want[('陈毅', '宋')] = 2
pred_f = {k: v for k, v in pred.items() if k[0] != '佚名'}
mismatch = []
for k in set(pred_f) | set(want):
    if pred_f.get(k, 0) != want.get(k, 0):
        mismatch.append((k, pred_f.get(k, 0), want.get(k, 0)))
print('predicted mismatch (excl 佚名):', len(mismatch))
for m in sorted(mismatch, key=lambda x: -abs((x[1] or 0) - (x[2] or 0))):
    print('  MISMATCH', m)
print('predicted total keys:', len([k for k in pred if pred[k]]))

json.dump({'corrections': final_corr,
           'leftover_turso': [{k: v for k, v in w.items() if k != 'content'} for w in leftover_t],
           'leftover_site': [{'pid': s['pid'], 'author': s['author'], 'title': s['title'], 'dyn': s['dyn']} for s in left_s],
           'mismatch': [[list(k), v1, v2] for k, v1, v2 in mismatch],
           're_authors': re_authors},
          open(os.path.join(CONS, 'v45-unify-plan2.json'), 'w'), ensure_ascii=False, indent=1)
print('plan2 written')
