# chinese-classics 仓库：异作者同文去重 + 异名归并（与站点、API 同一套判定）
# 判定来源：build/attrib/decisions.json（站点）、o2_*.json + groups2.json、api_plan.json（近似组取保留篇正文 api_keep_text.json）
import json, glob, os, re, collections, opencc
P = os.path.dirname(os.path.abspath(__file__)) + '/../..'
REPO = P + '/chinese-classics'; A = P + '/shici/build/attrib'
cc = opencc.OpenCC('t2s'); N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
nz = lambda s: cc.convert(N.sub('', s or ''))
plan = json.load(open(A + '/api_plan.json')); AL = plan['alias']
def canon(a, n=0):
    b = AL.get(a, a); return b if b == a or n > 5 else canon(b, n + 1)
FIN = {}
for d in json.load(open(A + '/decisions.json'))['groups']: FIN[nz(d['text'])] = canon(d['author'])
G2 = {g['g']: g for g in json.load(open(A + '/groups2.json'))}
for f in glob.glob(A + '/o2_*.json'):
    for o in json.load(open(f)): FIN[nz(G2[o['g']]['text'])] = canon(o['author'])
# 近似匹配：等长、相异字 ≤ max(1, 长度/25) 视为同一首（异体字、讹字）
BK = collections.defaultdict(list)
def add(t): BK[(len(t), t[:6])].append(t); BK[(len(t), t[-6:])].append(t)
def gid(t):
    if t in FIN: return t
    for k in ((len(t), t[:6]), (len(t), t[-6:])):
        for u in BK.get(k, ()):
            if sum(x != y for x, y in zip(t, u)) <= max(1, len(t) // 25): return u
    return None
for t in FIN: add(t)
KT = json.load(open(A + '/api_keep_text.json'))
for p in plan['groups']:
    t = nz(KT.get(str(p['keep']), ''))
    if len(t) >= 10 and not gid(t): FIN[t] = p['author']; add(t)
files = {}; FMT = {}; changed = set()
for f in sorted(glob.glob(REPO + '/*/*.json')):
    d = os.path.basename(os.path.dirname(f))
    if d in ('scripts', '名篇索引'): continue
    raw = open(f, encoding='utf-8').read(); j = json.loads(raw)
    m = re.match(r'\{\n( +)', raw)
    FMT[f] = (len(m.group(1)) if m else None, raw.endswith('\n'), ', ' in raw[:300] or not raw.startswith('{"'))
    if 'works' in j: files[f] = j
# 1. 异名：文件作者改为通行名，同目录已有该作者文件则并入
ren = 0
for f in list(files):
    j = files[f]; a = (j.get('author') or '').strip(); c = canon(a)
    if c == a: continue
    nf = os.path.join(os.path.dirname(f), c.replace('/', '_') + '.json')
    if nf in files: files[nf]['works'] += j['works']
    else: j['author'] = c; files[nf] = j; FMT[nf] = FMT[f]
    changed.add(nf); del files[f]; os.remove(f); ren += 1
# 2. 同文异作者：只留判定作者名下的一份
where = collections.defaultdict(list)
for f, j in files.items():
    for w in j['works']:
        g = gid(nz(''.join(w.get('paragraphs') or [])))
        if g: where[g].append((f, w))
drop = 0
for t, lst in where.items():
    fin = FIN[t]; mine = [x for x in lst if canon(files[x[0]].get('author', '')) == fin]
    if not mine: continue          # 判定作者在仓库无此篇：不删，避免丢文
    for f, w in lst:
        if (f, w) in mine[:1]: continue
        files[f]['works'] = [x for x in files[f]['works'] if x is not w]; drop += 1; changed.add(f)
empty = 0
for f, j in files.items():
    if f not in changed: continue
    if not j['works']:
        if os.path.exists(f): os.remove(f)
        empty += 1; continue
    ind, nl, sp = FMT[f]
    out = json.dumps(j, ensure_ascii=False, indent=ind) if ind else json.dumps(j, ensure_ascii=False, separators=None if sp else (',', ':'))
    open(f, 'w', encoding='utf-8').write(out + ('\n' if nl else ''))
print('changed files', len(changed), 'alias files', ren, 'dropped works', drop, 'emptied files', empty, 'decided texts', len(FIN))
