import json, glob, collections, re
B = 'build/attrib'
KW = re.compile('异名|残名|讹|异写|通行名|补全|同一人|同人|写法|形近|误字|脱字|缺字|乱码|本名|帝号|法名')
pairs = collections.Counter()
G1 = {}
for f in glob.glob(B + '/batch*.json'):
    for g in json.load(open(f)): G1[g['g']] = [i['a'] for i in g['items']]
for f in glob.glob(B + '/out*.json'):
    for o in json.load(open(f)):
        if o.get('disputed') or not KW.search(o.get('basis', '')): continue
        for a in G1[o['g']]:
            if a != o['author']: pairs[(a, o['author'])] += 1
G2 = {g['g']: [i['a'] for i in g['items']] for g in json.load(open(B + '/groups2.json'))}
for f in glob.glob(B + '/o2_*.json'):
    for o in json.load(open(f)):
        if o.get('disputed') or not KW.search(o.get('basis', '')): continue
        for a in G2[o['g']]:
            if a != o['author']: pairs[(a, o['author'])] += 1
C = json.load(open('build/corpus.json')); cnt = collections.Counter(r['a'] for r in C)
olds = collections.defaultdict(set)
for (a, b) in pairs: olds[a].add(b)
res = {}
for a, bs in olds.items():
    if len(bs) > 1: print('CONFLICT', a, bs); continue
    b = next(iter(bs)); res[a] = b
json.dump(res, open(B + '/alias_auto.json', 'w'), ensure_ascii=False, indent=0)
print(len(res))
for a, b in sorted(res.items(), key=lambda x: -cnt.get(x[0], 0))[:80]: print(a, '→', b, cnt.get(a, 0), cnt.get(b, 0))
