import json, re, collections, opencc
cc = opencc.OpenCC('t2s')
N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
nz = lambda s: cc.convert(N.sub('', s))
dec = json.load(open('build/attrib/decisions.json'))
dk = {nz(d['text']) for d in dec['groups']}
api = json.load(open('build/attrib/api_groups.json'))
print('api matched by site decisions', sum(1 for k in api if k in dk), 'unmatched', sum(1 for k in api if k not in dk))
C = json.load(open('build/corpus.json'))
g = collections.defaultdict(list)
for r in C:
    b = nz(''.join(r['p']))
    if len(b) >= 10: g[b].append((r['i'], r['t'], r['a']))
site = {k: v for k, v in g.items() if len({x[2] for x in v}) > 1}
print('site remaining groups (t2s)', len(site))
allk = set(site) | {k for k in api if k not in dk}
print('new groups total', len(allk))
out = []
for k in allk:
    out.append({'key': k, 'site': site.get(k, []), 'api': api.get(k, [])})
json.dump(out, open('build/attrib/groups2.json', 'w'), ensure_ascii=False)
