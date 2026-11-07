# Stage 3: bigram inverted index over title + full text (+ title unigrams), sharded by hash.
import json, os, re, sys, shutil, zlib
import numpy as np
from paths import BUILD as B, DATA as _DATA
D = os.path.join(_DATA, 'i')
S = int(sys.argv[1]) if len(sys.argv) > 1 else 512
DRY = '--dry' in sys.argv
C = json.load(open(B + '/corpus.json'))
# 倒排编码 token_id << BITS | poem_id：BITS 按最大 id 动态算（原写死 20 位，
# 上限 1,048,575，当前最大 id 已 948,515，只剩约 10 万余量）。前端只解 id 列表，
# 不感知位宽，故改位宽无需改 app.js；但新旧索引不可混用，重建须整库重建。
MAX_ID = max(r['i'] for r in C)
BITS = max(20, MAX_ID.bit_length())
assert MAX_ID < (1 << BITS), f'poem id {MAX_ID} exceeds {BITS}-bit index width'
print('max_id', MAX_ID, 'index bits', BITS)
CJK = re.compile(r'[\u3400-\u9fff]+')
tok = {}
pairs = []  # token_id << BITS | poem_id
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
    for t in seen: pairs.append((tid(t) << BITS) | i)
arr = np.array(pairs, dtype=np.uint64); del pairs
arr.sort()
toks = (arr >> np.uint64(BITS)).astype(np.int64)
ids = (arr & np.uint64((1 << BITS) - 1)).astype(np.int64)
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
