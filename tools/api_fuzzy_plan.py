# 近似重复组中能对上站点判定的，追加到 api_plan.json
import json, sqlite3, re, collections, opencc
R = 'build/attrib'
cc = opencc.OpenCC('t2s'); N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
nz = lambda s: cc.convert(N.sub('', s or ''))
D = json.load(open(R + '/decisions.json')); AL = dict(D['alias']); AL.update({'宋太宗': '赵炅', '无名氏': '佚名'})
def canon(a, n=0):
    b = AL.get(a, a); return b if b == a or n > 5 else canon(b, n + 1)
P = json.load(open(R + '/api_plan.json'))
used = {p['keep'] for p in P['groups']} | {d for p in P['groups'] for d in p['drop']}
db = sqlite3.connect('/tmp/api.db')
T = {}
for d in D['groups']:
    t = nz(d['text']); T.setdefault((len(t), t[:6]), []).append((t, d)); T.setdefault((len(t), t[-6:]), []).append((t, d))
def match(s):
    for k in ((len(s), s[:6]), (len(s), s[-6:])):
        for t, d in T.get(k, []):
            if sum(p != q for p, q in zip(s, t)) <= max(1, len(s) // 25): return d
add = 0; left = []
for g in json.load(open(R + '/fuzzy_api.json')):
    if len({canon(a) for _, _, a in g} - {'佚名'}) < 2 and len({canon(a) for _, _, a in g}) < 2: continue
    if any(i in used for i, _, _ in g): continue
    info = [(i, t, a) + db.execute('select famous, content from w where id=?', (i,)).fetchone() for i, t, a in g]
    d = None
    for x in info:
        d = match(nz(x[4]))
        if d: break
    named = {canon(x[2]) for x in info} - {'佚名'}
    if not d and len(named) == 1:
        d = {'author': named.pop(), 'title': None}
    if not d: left.append(g); continue
    A = canon(d['author'])
    cand = [x for x in info if canon(x[2]) == A] or info
    keep = sorted(cand, key=lambda x: (-int(x[3] or 0), x[0]))[0]
    P['groups'].append({'keep': keep[0], 'author': A, 'title': d.get('title') or keep[1], 'famous': max(int(x[3] or 0) for x in info),
                        'drop': [x[0] for x in info if x[0] != keep[0]], 'fuzzy': 1})
    used |= {x[0] for x in info}; add += 1
P['alias'] = {k: canon(k) for k in AL if canon(k) != k}
json.dump(P, open(R + '/api_plan.json', 'w'), ensure_ascii=False)
json.dump(left, open(R + '/fuzzy_api_left.json', 'w'), ensure_ascii=False)
print('fuzzy added', add, 'left', len(left), 'plan groups', len(P['groups']), 'drop', sum(len(p['drop']) for p in P['groups']))
print([p for p in P['groups'] if 40339 in p['drop'] or p['keep'] == 40339])
