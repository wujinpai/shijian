# Stage 3: bigram inverted index over title + full text (+ title unigrams), sharded by hash.
import json, os, re, sys, shutil, zlib
import numpy as np
B = '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/shici/build'
D = '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/shici/app/site/data/i'
S = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
DRY = '--dry' in sys.argv
C = json.load(open(B + '/corpus.json'))
CJK = re.compile(r'[\u3400-\u9fff]+')
tok = {}
pairs = []  # token_id << 20 | poem_id
def tid(t):
    v = tok.get(t)
    if v is None: v = tok[t] = len(tok)
    return v
for r in C:
    i = r['i']; seen = set()
    title = r['t']
    for seg in CJK.findall(title):
        for ch in seg: seen.add('^' + ch)
        for k in range(len(seg) - 1): seen.add(seg[k:k + 2])
    for p in r['p']:
        for seg in CJK.findall(p):
            for k in range(len(seg) - 1): seen.add(seg[k:k + 2])
    for t in seen: pairs.append((tid(t) << 20) | i)
arr = np.array(pairs, dtype=np.uint64); del pairs
arr.sort()
toks = (arr >> np.uint64(20)).astype(np.int64)
ids = (arr & np.uint64((1 << 20) - 1)).astype(np.int64)
print('tokens', len(tok), 'postings', len(arr))
inv = [None] * len(tok)
for t, v in tok.items(): inv[v] = t
# boundaries
bnd = np.flatnonzero(np.diff(toks)) + 1
starts = np.concatenate([[0], bnd]); ends = np.concatenate([bnd, [len(toks)]])
A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
def enc(a):
    d = np.diff(a, prepend=0)
    out = []
    for v in d.tolist():
        v = int(v)
        while v >= 32:
            out.append(A[32 | (v & 31)]); v >>= 5
        out.append(A[v])
    return ''.join(out)
def h(t):
    return zlib.crc32(t.encode('utf-8')) % S
shards = [dict() for _ in range(S)]
total = 0
MAXP = 60000  # cap postings per token (very common bigrams): keep highest-id-order prefix? keep all but cap
for s0, e0 in zip(starts.tolist(), ends.tolist()):
    t = inv[toks[s0]]
    a = ids[s0:e0]
    code = enc(a)
    shards[h(t)][t] = code
    total += len(code) + len(t.encode()) * 1 + 6
print('approx bytes', total, 'per shard', total // S)
if not DRY:
    shutil.rmtree(D, ignore_errors=True); os.makedirs(D)
    sizes = []
    for k, obj in enumerate(shards):
        s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
        open(f'{D}/{k}.json', 'w', encoding='utf-8').write(s); sizes.append(len(s.encode()))
    sizes.sort(); print('shard sizes min/med/max', sizes[0], sizes[len(sizes) // 2], sizes[-1], 'sum', sum(sizes))
