# 站点统一到仓库（2026-11-06 用户：仓库为唯一数据源，站点/API/关于页一致、不重复）
# 构建顺序：load → attrib_fix → canon → emit → index → said_build → moved；cats 单独跑。
# 每条站点记录配到仓库一条（作品或典籍章节）：正文全同 → 同作者近似 → 异作者近似 → 同作者同题。
# 同一仓库条目配到多条站点记录 → 只留一条（专集 > 朝代合集 > 蒙学/水墨），其余写入 merged.json 跳转；
# 千家诗、水墨唐诗被并掉的篇目改为「选本」（x.ls），在选本页列出。
# 保留条：作者、正文、标题（作品）取仓库；典籍章节的标题沿用站点，站点作者回写仓库章节 author（repo_feedback.json）。
# 仓库有、站点无的条目追加进对应合集（新 ext 段）。最后校验一一对应。
import json, os, re, sys, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('REPO_READ', '/tmp/cc/chinese-classics')
from canon_lib import *
from repo_canon import gn, COLL_DIR
RW = os.environ['REPO_READ']
import shutil
MERGED = SH + '/app/site/data/merged.json'
# attrib_fix 之后的状态先备份（重跑 load/attrib_fix 后删掉 *.pre_canon.*），保证可重复执行
for a, b in ((B + '/corpus.json', B + '/corpus.pre_canon.json'), (B + '/meta_raw.json', B + '/meta_raw.pre_canon.json'), (MERGED, B + '/merged.pre_canon.json')):
    if not os.path.exists(b): shutil.copy(a, b)
C = json.load(open(B + '/corpus.pre_canon.json')); M = json.load(open(B + '/meta_raw.pre_canon.json'))
merged = {int(k): v for k, v in json.load(open(B + '/merged.pre_canon.json')).items()}
# 仓库条目（带原文）
E = []
for f in repo_files():
    rp = f[len(REPO) + 1:]; j = json.load(open(f, encoding='utf-8'))
    a = (j.get('author') or '').strip() or '佚名'
    for n, w in enumerate(j.get('works', [])):
        E.append(('w', rp, n, a, w.get('title') or '', w.get('paragraphs') or [], nz(''.join(w.get('paragraphs') or [])), j.get('dynasty') or ''))
    for n, c in enumerate(j.get('chapters', [])):
        E.append(('c', rp, n, gn(c.get('author') or a), c.get('chapter') or '', c.get('paragraphs') or [], nz(''.join(c.get('paragraphs') or [])), j.get('dynasty') or ''))
print('repo entries', len(E), flush=True)
byid = {r['i']: r for r in C}
SR = {r['i']: (gn(s2(r['a'])), nz(''.join(r['p'])), r['t'], r['c']) for r in C}
empty = [i for i, s in SR.items() if len(s[1]) < 4]
ex = collections.defaultdict(list); ba = collections.defaultdict(list); tk = collections.defaultdict(list)
for k, e in enumerate(E):
    ex[e[6]].append(k); ba[(gn(e[3]), len(e[6]))].append(k); tk[(gn(e[3]), re.sub(r'\s+', '', s2(e[4])))].append(k)
pair = {}; left = []
for i, s in SR.items():
    if len(s[1]) < 4: continue
    c = ex.get(s[1])
    if c: pair[i] = sorted(c, key=lambda k: (gn(E[k][3]) != s[0], E[k][0] != 'c'))[0]; continue
    c = [k for k in ba.get((s[0], len(s[1])), []) if near(E[k][6], s[1])]
    if c: pair[i] = sorted(c, key=lambda k: E[k][4] != s[2])[0]; continue
    left.append(i)
def SL(t):
    n = len(t); q = max(4, n // 6)
    return {(n, j, t[j:j + 4]) for j in range(0, max(1, n - 3), q)}
L = set(len(SR[i][1]) for i in left); bt = collections.defaultdict(list)
for k, e in enumerate(E):
    if len(e[6]) in L:
        for kk in SL(e[6]): bt[kk].append(k)
unp = []; nsplit = [0]
heads = collections.defaultdict(list); bya_all = collections.defaultdict(list)
for k, e in enumerate(E): bya_all[gn(e[3])].append(k)
for k, e in enumerate(E):
    if len(e[6]) >= 20: heads[(gn(e[3]), e[6][:8])].append(k)
for i in left:
    t = SR[i][1]; c = [k for k in {x for kk in SL(t) for x in bt.get(kk, [])} if near(E[k][6], t)]
    if c: print('XNEAR', i, byid[i]['a'], byid[i]['t'], '->', E[c[0]][3], E[c[0]][4])
    if not c: c = tk.get((SR[i][0], re.sub(r'\s+', '', s2(SR[i][2]))))
    if not c:  # 同作者同长、差 ≤25%（如《清平调》其三 常/长、得/释、沉/沈）
        t = SR[i][1]; c = sorted([k for k in ba.get((SR[i][0], len(t)), []) if sum(x != y for x, y in zip(E[k][6], t)) <= max(2, len(t) // 4)],
                                 key=lambda k: sum(x != y for x, y in zip(E[k][6], t)))
        if c: print('LOOSE', i, byid[i]['a'], byid[i]['t'], '->', E[c[0]][4])
    if not c:  # v36：同作者近似（≥90%，同人异名合并后去掉的版本）
        import difflib; t = SR[i][1]
        c = sorted([k for k in bya_all.get(SR[i][0], []) if abs(len(E[k][6]) - len(t)) <= max(2, len(t) // 10) and difflib.SequenceMatcher(None, E[k][6], t, autojunk=False).ratio() >= 0.9],
                   key=lambda k: -difflib.SequenceMatcher(None, E[k][6], t, autojunk=False).ratio())
        if c: print('NEAR90', i, byid[i]['a'], byid[i]['t'], '->', E[c[0]][3], E[c[0]][4])
    if not c and len(SR[i][1]) >= 40:  # 站点整组合抄（如「二首」连在一条），仓库已分条：配到第一首，其余各首作为新篇追加
        t = SR[i][1]; c = [k for k in heads.get((SR[i][0], t[:8]), []) if len(E[k][6]) >= 20 and t.startswith(E[k][6])]
        c.sort(key=lambda k: -len(E[k][6]))
        if not c:
            c = [k for k in bya_all.get(SR[i][0], []) if 20 <= len(E[k][6]) < len(t) and near(E[k][6], t[:len(E[k][6])])]
            c.sort(key=lambda k: -len(E[k][6]))
        if c: nsplit[0] += 1
    if c: pair[i] = c[0]
    else: unp.append(i)
print('paired', len(pair), 'split (合抄配第一首)', nsplit[0], 'unpaired', len(unp), 'empty', len(empty), flush=True)
if unp:
    json.dump([[i, byid[i]['c'], byid[i]['a'], byid[i]['t'], SR[i][1]] for i in unp], open(B + '/consist/unpaired.json', 'w'), ensure_ascii=False)
    for i in unp[:10]: print('UNPAIRED', i, byid[i]['c'], byid[i]['a'], byid[i]['t'])
    if os.environ.get('CANON_STRICT', '1') == '1': raise SystemExit('站点有仓库无的记录：先补进仓库（repo_canon.py）')
PRI = {c: 0 for c in ('shijing', 'chuci', 'caocao', 'huajian', 'nantang', 'nalan', 'lunyu', 'sishu', 'dianji', 'guwen', 'youmeng')}
PRI.update({'mengxue': 2, 'shuimo': 2})
DIRC = {v: k for k, v in COLL_DIR.items()}
bye = collections.defaultdict(list)
for i, k in pair.items(): bye[k].append(i)
drop = set(empty); feedback = []; textfix = []
ORIG = {r['i']: (list(r['p']), dict(r.get('x') or {})) for r in C}
def near2(a, b): return abs(len(a) - len(b)) <= 2 and sum(x != y for x, y in zip(a, b)) <= max(2, len(a) // 5)
LS = lambda r: '千家诗' if (r['c'] == 'mengxue' and r['g'] == '千家诗') else ('水墨唐诗' if r['c'] == 'shuimo' else None)
nchg = collections.Counter(); achg = set()
for k, ids in bye.items():
    e = E[k]; ea = gn(e[3]); d0 = e[1].split('/')[0]
    ids.sort(key=lambda i: (PRI.get(byid[i]['c'], 1), SR[i][0] != ea, DIRC.get(d0) != byid[i]['c'], -byid[i].get('_pop', 0), i))
    keep = byid[ids[0]]
    ls = sorted({LS(byid[i]) for i in ids if LS(byid[i])})
    for i in ids[1:]:
        dr = byid[i]; merged[i] = keep['i']; drop.add(i)
        for key in ('sel', 'tg', 'pr', 'cm'):
            v = (dr.get('x') or {}).get(key)
            if v and not (keep.get('x') or {}).get(key): keep.setdefault('x', {})[key] = v
        if dr.get('_pop', 0) > keep.get('_pop', 0): keep['_pop'] = dr['_pop']
    if ls: keep.setdefault('x', {})['ls'] = ls
    if e[0] == 'w':
        if keep['a'] != e[3]: keep['a'] = e[3]; achg.add(keep['i']); nchg['author'] += 1
        if keep['t'] != e[4]: keep['t'] = e[4]; nchg['title'] += 1
    elif keep['a'] != ea:
        keep['a'] = ea; achg.add(keep['i']); nchg['author'] += 1
    # 通行本优先：组里有唐诗三百首/宋词三百首/水墨唐诗/千家诗的篇目而文字与仓库不同（如《静夜思》床前明月光、《赤壁》沉沙），
    # 用该版本文字并回写仓库（textfix.json），仓库与站点仍一致
    cur = [i for i in ids if (ORIG[i][1].get('sel') or byid[i]['c'] == 'shuimo' or (byid[i]['c'] == 'mengxue' and byid[i]['g'] == '千家诗'))]
    cur = [] if any(nz(''.join(ORIG[i][0])) == e[6] for i in cur) else [i for i in cur if near2(nz(''.join(ORIG[i][0])), e[6])]
    if cur:
        tp = list(ORIG[cur[0]][0]); textfix.append([e[0], e[1], e[2], tp]); nchg['textfix'] += 1
        if keep['p'] != tp: keep['p'] = tp; nchg['text'] += 1
    elif keep['p'] != e[5]: keep['p'] = list(e[5]); nchg['text'] += 1
for i, k in merged.items():  # 跳转链压平
    seen = 0
    while k in merged and seen < 10: k = merged[k]; seen += 1
    merged[i] = k
# 作者改了的：朝代取该作者其余篇目的多数
dynof = collections.defaultdict(collections.Counter)
for r in C:
    if r['i'] not in drop and r['i'] not in achg and r.get('d'): dynof[r['a']][r['d']] += 1
for i in achg:
    r = byid[i]
    if dynof[r['a']] and r.get('d') not in dynof[r['a']]: r['d'] = dynof[r['a']].most_common(1)[0][0]
# 仓库有、站点无 → 追加
miss = [k for k in range(len(E)) if k not in bye and len(E[k][6]) >= 4]
print('repo entries not on site', len(miss), flush=True)
cm = {m['code']: m for m in M['colls']}
nid = M['total_ids']; add = collections.defaultdict(list)
D2C = {'唐诗': 'tang', '唐词': 'tang', '五代诗': 'tang', '五代词': 'tang', '宋诗': 'songshi', '宋词': 'songci', '元曲': 'yuanqu', '元诗': 'jinyuan', '元词': 'jinyuan',
       '辽金诗': 'jinyuan', '辽金词': 'jinyuan', '明诗': 'mingshi', '明词': 'mingshi', '清诗': 'qingshi', '清词': 'qingshi', '近代诗': 'jiuti', '现代诗': 'xinshi',
       '先秦诗': 'xiantang', '秦汉诗': 'xiantang', '魏晋南北朝诗': 'xiantang', '隋诗': 'xiantang'}
for k in miss:
    e = E[k]; c = D2C[e[1].split('/')[0]]
    if e[0] == 'c': c = 'dianji'
    add[c].append(k)
for c, ks in add.items():
    m = cm[c]; nid = ((nid + 249) // 250) * 250; start = nid
    for k in ks:
        e = E[k]; d = m['dyn'] if m['dyn'] not in ('历代', '先秦至隋', '辽金元') else (e[7] or m['dyn'])
        g = '词' if e[1].split('/')[0].endswith('词') else ('曲' if e[1].startswith('元曲') else (m['genres'][0][0] if m.get('genres') and c in ('dianji',) else '诗'))
        C.append({'t': e[4], 'a': e[3], 'p': list(e[5]), 'g': g, 'i': nid, 'c': c, 'd': d, '_pop': 0.3}); nid += 1
        print('ADD', c, nid - 1, e[3], e[4])
    m.setdefault('ext', []).append([start, len(ks)]); m['count'] += len(ks)
M['total_ids'] = ((nid + 249) // 250) * 250
n0 = len(C)
C = [r for r in C if r['i'] not in drop]
for i in empty: merged.pop(i, None)
# 校验：一一对应
assert len(C) == len({r['i'] for r in C})
print('site total', len(C), 'dropped', len(drop), '(empty', len(empty), ')', 'changes', dict(nchg), 'chapter author feedback', len(feedback))
json.dump(C, open(B + '/corpus.json', 'w'), ensure_ascii=False)
json.dump(M, open(B + '/meta_raw.json', 'w'), ensure_ascii=False)
json.dump({str(k): v for k, v in merged.items()}, open(MERGED, 'w'), separators=(',', ':'))
json.dump(textfix, open(B + '/consist/textfix.json', 'w'), ensure_ascii=False)
json.dump({'empty_dropped': empty}, open(B + '/consist/site_empty.json', 'w'))
