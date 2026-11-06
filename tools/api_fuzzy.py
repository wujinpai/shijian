# 近似重复：正文等长、相异字 ≤ max(2, 4%)，作者不同（异体字/讹字导致精确匹配漏掉）
import sqlite3, re, json, collections, opencc, sys
cc = opencc.OpenCC('t2s')
N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
src = sys.argv[1]  # api | site
rows = []
if src == 'api':
    db = sqlite3.connect('/tmp/api.db')
    for i, t, a, c in db.execute('select id,title,author,content from w'): rows.append((i, t, a, cc.convert(N.sub('', c or ''))))
else:
    for r in json.load(open('build/corpus.json')): rows.append((r['i'], r['t'], r['a'], cc.convert(N.sub('', ''.join(r.get('c') or r.get('p') or [])) if isinstance(r.get('c') or r.get('p'), list) else N.sub('', r.get('c') or r.get('p') or ''))))
rows = [r for r in rows if len(r[3]) >= 12]
par = {}
def f(x):
    while par.get(x, x) != x: x = par[x]
    return x
def u(a, b): par[f(a)] = f(b)
idx = {r[0]: r for r in rows}
for key in (lambda s: s[:6], lambda s: s[-6:], lambda s: s[len(s)//2-3:len(s)//2+3]):
    B = collections.defaultdict(list)
    for r in rows: B[(len(r[3]), key(r[3]))].append(r)
    for v in B.values():
        if len(v) < 2 or len(v) > 300: continue
        for x in range(len(v)):
            for y in range(x + 1, len(v)):
                a, b = v[x], v[y]
                if a[2] == b[2] or a[3] == b[3]: continue
                d = sum(p != q for p, q in zip(a[3], b[3]))
                if d <= max(1, len(a[3]) // 25) and len(a[3]) >= 16: u(a[0], b[0])
G = collections.defaultdict(list)
for i in list(par): G[f(i)].append(i)
out = [[idx[i][:3] for i in v] for v in G.values() if len(v) > 1]
json.dump(out, open(f'build/attrib/fuzzy_{src}.json', 'w'), ensure_ascii=False)
print(src, 'groups', len(out), 'items', sum(map(len, out)))
