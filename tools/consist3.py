import json, collections, re, opencc
P = '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03'
cc = opencc.OpenCC('t2s'); N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
class T(dict):
    def __missing__(s, o): v = cc.convert(chr(o)); s[o] = v; return v
TB = T(); nz = lambda x: N.sub('', x or '').translate(TB)
D = json.load(open(P + '/shici/build/consist/pair.json')); res = D['res']; RR = D['RR']
C = json.load(open(P + '/shici/build/corpus.json')); S = {r['i']: r for r in C}
def near(a, b): return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= max(1, len(a) // 10)
# a) alias pairs
ap = collections.Counter((S[i]['a'], RR[k][2]) for i, k in res['xa_exact'] + res['xa_near'])
print('alias pairs', len(ap)); print(ap.most_common(40))
# b) site_only
mt = {}  # repo idx -> site id
for i, k in res['exact'] + res['near'] + res['xa_exact'] + res['xa_near']: mt[k] = i
bt = collections.defaultdict(list)
for k, i in mt.items(): bt[(len(RR[k][3]), RR[k][3][:4])].append(k); bt[(len(RR[k][3]), RR[k][3][-4:])].append(k)
sd = collections.Counter(); snew = []
for i in res['site_only']:
    t = nz(''.join(S[i]['p']))
    c = [k for k in bt.get((len(t), t[:4]), []) + bt.get((len(t), t[-4:]), []) if near(RR[k][3], t)]
    if c: sd[S[i]['c']] += 1
    else: snew.append(i)
print('site_only that dup another site rec', sum(sd.values()), sd.most_common())
print('site_only new', len(snew), collections.Counter(S[i]['c'] for i in snew).most_common())
# c) repo_only
ba = collections.defaultdict(list)
for k, i in mt.items(): ba[(RR[k][2], len(RR[k][3]))].append(k)
ro = collections.Counter(); rnew = []; rx = []
for k in res['repo_only']:
    r = RR[k]; c = [m for m in ba.get((r[2], len(r[3])), []) if near(RR[m][3], r[3])]
    if c: ro['dup_same_author' + ('_exact' if any(RR[m][3] == r[3] for m in c) else '_near')] += 1; continue
    c = [m for m in bt.get((len(r[3]), r[3][:4]), []) + bt.get((len(r[3]), r[3][-4:]), []) if near(RR[m][3], r[3])]
    if c: ro['dup_other_author'] += 1; rx.append((k, c[0])); continue
    rnew.append(k)
print('repo_only', ro, 'new', len(rnew), collections.Counter(RR[k][0].split('/')[0] for k in rnew).most_common())
import random; random.seed(3)
for k, m in random.sample(rx, min(10, len(rx))): print('RX', RR[k][0], RR[k][4], '| matched', RR[m][0], RR[m][4])
for k in random.sample(rnew, 10): print('RN', RR[k][0], RR[k][4], RR[k][3][:16])
json.dump({'snew': snew, 'rnew': rnew, 'rx': rx}, open(P + '/shici/build/consist/cls.json', 'w'))
