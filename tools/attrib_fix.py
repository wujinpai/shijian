# 异作者同文去重 + 作者归属校正。load.py 之后、emit.py 之前运行。
# 输入 build/attrib/out*.json（每组 keep/author/title/drop），输出：改写 build/corpus.json；
# app/site/data/merged.json（被并掉的旧 id → 保留 id）；build/attrib/decisions.json（供 API/仓库同步）。
import json, glob, re, os, shutil
from paths import ROOT as R
B = R + '/build'
# 同一人异名 → 通行名（全站统一）
import os
ALIAS = {'太宗皇帝': '李世民', '则天皇后': '武则天', '于邺': '于武陵', '张佖': '张泌', '郭元振': '郭震',
         '僧贯休': '贯休', '僧齐己': '齐己', '僧皎然': '皎然', '僧子兰': '子兰', '延寿': '释延寿', '赞宁': '释赞宁',
         '宋高宗': '赵构', '朱淑贞': '朱淑真', '李嘉佑': '李嘉祐', '韩王从善': '李从善', '赵东阁': '赵汝回',
         '杜北山': '杜汝能', '李舒': '李纾', '侯置': '侯寘', '张祠部': '张景修', '刘氏媛': '刘媛', '刘氏云': '刘云',
         '纪唐天': '纪唐夫', '毛达': '毛友', '后主煜': '李煜', '后主衍': '王衍', '释德洪': '惠洪',
         '释无本': '贾岛', '杜小山': '杜耒', '周𪸩': '周辉', '义铦': '葛天民'}
if os.path.exists(B + '/attrib/alias_auto.json'):
    for k, v in json.load(open(B + '/attrib/alias_auto.json')).items(): ALIAS.setdefault(k, v)
def canon(a, n=0):
    b = ALIAS.get(a, a)
    return b if b == a or n > 5 else canon(b, n + 1)
# load.py 重跑后先删 corpus.pre_attrib.json；否则从备份读，保证可重复执行
if not os.path.exists(B + '/corpus.pre_attrib.json'): shutil.copy(B + '/corpus.json', B + '/corpus.pre_attrib.json')
C = json.load(open(B + '/corpus.pre_attrib.json'))
byid = {r['i']: r for r in C}
# groups.json 用的是 corpus 下标，换成 id
pos2id = {k: r['i'] for k, r in enumerate(C)}
dec = []
for f in sorted(glob.glob(B + '/attrib/out*.json')): dec += json.load(open(f))
merged, drop, out = {}, set(), []
for d in dec:
    k = pos2id[d['keep']]; r = byid[k]
    olda = r['a']
    r['a'] = canon(d['author']); r['t'] = d['title'] or r['t']
    if d.get('disputed') and d.get('other'):
        r.setdefault('x', {})
        r['x']['yz'] = [canon(o) for o in d['other'] if canon(o) != r['a'] and o not in ('拾遗',) and '郊庙' not in o]
    for p in d['drop']:
        i = pos2id[p]; merged[i] = k; drop.add(i)
        dr = byid[i]
        # 保留条缺的选本/标签信息从被并条补上
        for key in ('sel', 'tg', 'pr'):
            v = (dr.get('x') or {}).get(key)
            if v and not (r.get('x') or {}).get(key): r.setdefault('x', {})[key] = v
        if dr.get('_pop', 0) > r.get('_pop', 0): r['_pop'] = dr['_pop']
    out.append({'text': ''.join(r['p']), 'author': r['a'], 'title': r['t'], 'dynasty': r.get('d'),
                'from': sorted({olda} | {byid[pos2id[p]]['a'] for p in d['drop']}), 'disputed': bool(d.get('disputed')),
                'other': r.get('x', {}).get('yz', [])})
# 第二轮（繁简归一后才相同）的站内组：groups2.json 里 src=site 的条目
G2 = {g['g']: g for g in json.load(open(B + '/attrib/groups2.json'))}
for f in sorted(glob.glob(B + '/attrib/o2_*.json')):
    for o in json.load(open(f)):
        ids = [it['id'] for it in G2[o['g']]['items'] if it['src'] == 'site' and it['id'] in byid and it['id'] not in drop]
        if len(ids) < 2: continue
        A = canon(o['author']); ids.sort(key=lambda i: (canon(byid[i]['a']) != A, -byid[i].get('_pop', 0)))
        k = ids[0]; byid[k]['a'] = A; byid[k]['t'] = o['title'] or byid[k]['t']
        for i in ids[1:]: merged[i] = k; drop.add(i)
        dec.append({'keep': None})
import collections
keepids = {pos2id[d['keep']] for d in dec if d['keep'] is not None}
dynof = collections.defaultdict(collections.Counter)
for r in C:
    if r['i'] not in drop and r.get('d') and r['i'] not in keepids: dynof[canon(r['a'])][r['d']] += 1
for d in dec:
    if d['keep'] is None: continue
    r = byid[pos2id[d['keep']]]
    if dynof[r['a']] and r.get('d') not in dynof[r['a']]:
        r['d'] = dynof[r['a']].most_common(1)[0][0]
n0 = len(C)
C = [r for r in C if r['i'] not in drop]
ren = 0
for r in C:
    a = canon(r['a'])
    if a != r['a']: r['a'] = a; ren += 1
json.dump(C, open(B + '/corpus.json', 'w'), ensure_ascii=False)
json.dump({str(k): v for k, v in merged.items()}, open(R + '/app/site/data/merged.json', 'w'), separators=(',', ':'))
json.dump({'alias': ALIAS, 'groups': out}, open(B + '/attrib/decisions.json', 'w'), ensure_ascii=False)
print('groups', len(dec), 'dropped', n0 - len(C), 'alias renamed', ren, 'total', len(C))
