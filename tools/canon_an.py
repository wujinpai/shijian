# 分析：站点每条配到仓库哪一条；站点内部重复的合集对
import json, collections, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canon_lib import *
t0 = time.time(); E = load_repo(); print('E', len(E), time.time() - t0, flush=True)
C = json.load(open(B + '/corpus.json'))
SR = [(r['i'], s2(r['a']), nz(''.join(r['p'])), r['c']) for r in C]
ex = collections.defaultdict(list); ba = collections.defaultdict(list); bt = collections.defaultdict(list)
for k, e in enumerate(E): ex[e[5]].append(k); ba[(e[3], len(e[5]))].append(k)
def find(s):
    c = ex.get(s[2])
    if c: return sorted(c, key=lambda k: E[k][3] != s[1])[0]
    c = [k for k in ba.get((s[1], len(s[2])), []) if near(E[k][5], s[2])]
    return c[0] if c else None
g = collections.defaultdict(list); left = []
for s in SR:
    k = find(s)
    if k is None: left.append(s)
    else: g[k].append(s)
print('left after exact/same-author', len(left), time.time() - t0, flush=True)
L = set(len(s[2]) for s in left)
for k, e in enumerate(E):
    if len(e[5]) in L: bt[(len(e[5]), e[5][:4])].append(k); bt[(len(e[5]), e[5][-4:])].append(k)
for s in left:
    t = s[2]; c = [k for k in set(bt.get((len(t), t[:4]), []) + bt.get((len(t), t[-4:]), [])) if near(E[k][5], t)]
    g[c[0] if c else None].append(s)
cp = collections.Counter()
for k, ss in g.items():
    if k is None or len(ss) < 2: continue
    cp[tuple(sorted(x[3] for x in ss))] += 1
print('unpaired site', len(g.get(None, [])), collections.Counter(x[3] for x in g.get(None, [])))
print('site dup groups', sum(cp.values()), 'extra recs', sum(len(v) - 1 for k, v in g.items() if k is not None and len(v) > 1))
for x in cp.most_common(40): print(x)
pickle.dump({k: [x[0] for x in v] for k, v in g.items()}, open('/tmp/sgroups.pkl', 'wb'))
