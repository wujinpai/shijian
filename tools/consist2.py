# 站点↔仓库逐篇配对。输出 build/consist/pair.json
import json, glob, os, re, collections, sys, opencc, time
P = '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03'
cc = opencc.OpenCC('t2s'); N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
TT = {}
def _c(x):
    for ch in set(x) - TT.keys(): TT[ch] = cc.convert(ch)
    return x.translate(_TB)
class _TBc(dict):
    def __missing__(self, o):
        ch = chr(o); v = TT.get(ch) or cc.convert(ch); TT[ch] = v; self[o] = v; return v
_TB = _TBc()
def _c(x): return x.translate(_TB)
nz = lambda s: _c(N.sub('', s or ''))
t0 = time.time()
def near(a, b): return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= max(1, len(a) // 10)
# repo records list
RR = []
for f in sorted(glob.glob(P + '/chinese-classics/*/*.json')):
    d = os.path.basename(os.path.dirname(f))
    if d in ('scripts', '名篇索引'): continue
    j = json.load(open(f, encoding='utf-8')); a = _c((j.get('author') or '').strip()) or '佚名'
    for n, w in enumerate(j.get('works', [])): RR.append((f.split('chinese-classics/')[1], n, a, nz(''.join(w.get('paragraphs') or [])), w.get('title') or ''))
SR = [(r['i'], _c(r['a']), nz(''.join(r['p'])), r['t'], r['c']) for r in json.load(open(P + '/shici/build/corpus.json'))]
byk = collections.defaultdict(list); bya = collections.defaultdict(list); byb = collections.defaultdict(list)
for k, r in enumerate(RR):
    byk[(r[2], r[3])].append(k); bya[(r[2], len(r[3]))].append(k)
    byb[(len(r[3]), r[3][:5])].append(k); byb[(len(r[3]), r[3][-5:])].append(k)
used = set(); res = {'exact': [], 'near': [], 'xa_exact': [], 'xa_near': [], 'site_only': []}
pending = []
for s in SR:
    c = [k for k in byk.get((s[1], s[2]), []) if k not in used]
    if c: used.add(c[0]); res['exact'].append((s[0], c[0])); continue
    pending.append(s)
p2 = []
for s in pending:
    c = [k for k in bya.get((s[1], len(s[2])), []) if k not in used and near(RR[k][3], s[2])]
    if c:
        c.sort(key=lambda k: RR[k][4] != s[3]); used.add(c[0]); res['near'].append((s[0], c[0])); continue
    p2.append(s)
for s in p2:
    c = [k for k in set(byb.get((len(s[2]), s[2][:5]), []) + byb.get((len(s[2]), s[2][-5:]), [])) if k not in used and near(RR[k][3], s[2])]
    if c:
        c.sort(key=lambda k: (RR[k][3] != s[2], RR[k][4] != s[3])); used.add(c[0]); res['xa_exact' if RR[c[0]][3] == s[2] else 'xa_near'].append((s[0], c[0])); continue
    res['site_only'].append(s[0])
res['repo_only'] = [k for k in range(len(RR)) if k not in used]
for k, v in res.items(): print(k, len(v))
S = {s[0]: s for s in SR}
print('site_only by coll', collections.Counter(S[i][4] for i in res['site_only']).most_common())
print('repo_only by dir', collections.Counter(RR[k][0].split('/')[0] for k in res['repo_only']).most_common(12))
ro = collections.Counter((RR[k][2], RR[k][3]) for k in range(len(RR)))
print('repo_only that are exact dup of a matched repo rec', sum(1 for k in res['repo_only'] if ro[(RR[k][2], RR[k][3])] > 1))
json.dump({'res': res, 'RR': RR}, open(P + '/shici/build/consist/pair.json', 'w'), ensure_ascii=False)
import random; random.seed(2)
for i, k in random.sample(res['xa_exact'], 8): print('XA', S[i][1], S[i][3], S[i][4], '| repo', RR[k][2], RR[k][4])
for i in random.sample(res['site_only'], 8): print('SO', S[i][1:2], S[i][3], S[i][4], S[i][2][:20])
for k in random.sample(res['repo_only'], 8): print('RO', RR[k][0], RR[k][4], RR[k][3][:20])
