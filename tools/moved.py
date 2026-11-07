# 旧「历代补遗」id（790000–867999）→ 并入各合集后的新 id。输出 app/site/data/moved.json（下标 = 旧 id - 790000，0 = 无）
import json
from paths import ROOT as R
old = json.load(open(R + '/build/buyi_old_ids.json'))
C = json.load(open(R + '/build/corpus.json'))
key = {}
for r in C:
    if r['i'] >= 868000: key.setdefault((r['t'], r['a'], ''.join(r['p'])[:40]), r['i'])
arr = [0] * 78000; hit = 0
for i, k in old.items():
    n = key.get(tuple(k))
    if n: arr[int(i) - 790000] = n; hit += 1
json.dump(arr, open(R + '/app/site/data/moved.json', 'w'), separators=(',', ':'))
print('moved', hit, 'of', len(old))
