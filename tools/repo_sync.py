# 同步 chinese-classics 仓库：
# 1) 仓库内部去重：同作者（简体）同题、正文（汉字）等长且差 ≤10% 视为同一篇，保留缺字少的版本，释义/词牌并入保留篇
# 2) 补入本站有、仓库没有的篇目（按朝代+体裁归入 <朝代>诗/词/曲 目录；新诗入 现代诗/；先秦两汉典籍按 schema 典籍单行本格式）
# 用法：python3 repo_sync.py  （改的是项目根 chinese-classics/ 工作区，提交推送另做）
import json, glob, os, re, collections, sys
import opencc
cv = opencc.OpenCC('t2s.json'); s = lambda x: cv.convert(x or '')
P = os.path.dirname(os.path.abspath(__file__)) + '/../..'
REPO = P + '/chinese-classics'; SH = P + '/shici'
N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
MISS = re.compile(r'[□〇?？]')
def near(a, b): return sum(x != y for x, y in zip(a, b)) <= max(1, len(b) // 10)
def txt(ps): return N.sub('', s(''.join(ps or [])))

files = {}  # path -> (obj, trailing newline)
for f in sorted(glob.glob(REPO + '/*/*.json')):
    d = os.path.basename(os.path.dirname(f))
    if d in ('scripts', '名篇索引'): continue
    raw = open(f, encoding='utf-8').read()
    ind = None
    if raw.startswith('{\n'): m = re.match(r'\{\n( +)', raw); ind = len(m.group(1)) if m else 1
    files[f] = [json.loads(raw), raw.endswith('\n'), ind]
print('files', len(files), file=sys.stderr)

# ---------- 1. 去重 ----------
seen = {}; dup = 0; changed = set(); raw_n = 0
for f, (j, *_) in files.items():
    if 'works' not in j: continue
    a = s((j.get('author') or '').strip()) or '佚名'
    keep = []
    for w in j['works']:
        k = txt(w.get('paragraphs'))
        if not k: keep.append(w); continue
        raw_n += 1
        g = seen.setdefault((a, w.get('title', ''), len(k)), [])
        hit = next((o for o in g if near(o[0], k)), None)
        if hit is None: g.append([k, w, f]); keep.append(w); continue
        dup += 1; changed.add(f); o = hit[1]
        if len(MISS.findall(''.join(w.get('paragraphs')))) < len(MISS.findall(''.join(o.get('paragraphs')))):
            o['paragraphs'] = w['paragraphs']; changed.add(hit[2])
        for fld in ('rhythmic', 'chapter', 'section', 'strains'):
            if w.get(fld) and not o.get(fld): o[fld] = w[fld]; changed.add(hit[2])
        if w.get('annotations') and not o.get('annotations'): o['annotations'] = w['annotations']; changed.add(hit[2])
    j['works'] = keep
print('raw', raw_n, 'dup', dup, file=sys.stderr)

# ---------- 2. 仓库现有正文索引 ----------
full = set(); bya = collections.defaultdict(list)
for (a, t, L), g in seen.items():
    for k, w, f in g: full.add(k); bya[(a, L)].append(k)
for f, (j, *_) in files.items():
    for c in j.get('chapters', []):
        k = txt(c.get('paragraphs'))
        if k: full.add(k)
        for p in c.get('paragraphs', []):  # 段落级（蒙学、幽梦影按条）
            kk = N.sub('', s(p))
            if len(kk) >= 8: full.add(kk)
chap_txt = '\n'.join(N.sub('', s(''.join(c.get('paragraphs', [])))) for j, *_ in files.values() for c in j.get('chapters', []))

C = json.load(open(SH + '/build/corpus.json'))
bios = json.load(open(SH + '/build/bios.json'))
cname = {m['code']: m['name'] for m in json.load(open(SH + '/build/meta_raw.json'))['colls']}
DIR = {'先秦': '先秦', '汉': '秦汉', '秦': '秦汉', '魏晋': '魏晋南北朝', '南北朝': '魏晋南北朝', '隋': '隋', '隋末唐初': '隋',
       '唐': '唐', '五代': '五代', '宋': '宋', '金': '辽金', '辽': '辽金', '元': '元', '明': '明', '清': '清', '近现代': '近代', '历代': '清'}
CI_COLL = {'songci', 'huajian', 'nantang', 'nalan'}
SHI_G = re.compile(r'(言|长篇|绝句|律诗|杂言|古风|乐府|四言|六言|^$|诗)')
def kind(r):
    if r['c'] == 'yuanqu': return '曲'
    if r['c'] in CI_COLL: return '词'
    g = r.get('g') or ''
    if g == '词': return '词'
    if r['c'] in ('jiuti', 'buyi') and not SHI_G.search(g): return '词'
    return '诗'
add = collections.defaultdict(list); dianji = collections.defaultdict(list); add_n = collections.Counter()
for r in C:
    a = r['a'] or '佚名'; k = N.sub('', ''.join(r['p']))
    if not k: continue
    if k in full or any(near(t, k) for t in bya.get((a, len(k)), [])): continue
    if len(k) >= 8 and k in chap_txt: continue
    x = r.get('x') or {}
    if r['c'] == 'dianji':
        dianji[(DIR.get(r['d'], '先秦'), r['g'], x.get('ad') or r['d'], a)].append(r); add_n['典籍'] += 1; continue
    if r['c'] == 'xinshi': d = '现代诗'
    else:
        kd = kind(r); base = DIR.get(r['d'], '清')
        d = base + kd
        if not os.path.isdir(REPO + '/' + d): d = base + '诗'
    add[(d, a, x.get('ad') or r['d'])].append(r); add_n[d] += 1
print('add', sum(add_n.values()), dict(add_n), file=sys.stderr)

def fname(x): return re.sub(r'[\\/:*?"<>|\n]', '_', x)[:80]
for (d, a, dyn), rs in add.items():
    os.makedirs(REPO + '/' + d, exist_ok=True)
    f = REPO + '/' + d + '/' + fname(a) + '.json'
    if f not in files:
        bio = bios.get(dyn + '|' + a) or bios.get(rs[0]['d'] + '|' + a) or ''
        files[f] = [{'dynasty': dyn, 'author': a, 'author_desc': bio, 'works': []}, False, None]
    j = files[f][0]
    if 'works' not in j:
        f = f[:-5] + '（补）.json'; files.setdefault(f, [{'dynasty': dyn, 'author': a, 'author_desc': '', 'works': []}, False, None]); j = files[f][0]
    for r in rs:
        w = {'title': r['t'], 'paragraphs': r['p']}
        if d.endswith('词') and '·' in r['t']: w['rhythmic'] = r['t'].split('·')[0]
        elif d.endswith('词') and r.get('g') and r['g'] not in ('词', ''): w['rhythmic'] = r['g']
        j['works'].append(w)
    changed.add(f)
for (d, book, dyn, a), rs in dianji.items():
    f = REPO + '/' + d + '诗/' + fname(book) + '.json'
    if f in files and 'chapters' in files[f][0]: j = files[f][0]
    else: files[f] = [{'title': book, 'dynasty': dyn, 'author': a, 'chapters': []}, False, None]; j = files[f][0]
    for r in rs: j['chapters'].append({'chapter': r['t'], 'paragraphs': r['p']})
    changed.add(f)

for f in changed:
    j, nl, ind = files[f]
    if 'works' in j and not j['works']: os.remove(f); continue
    open(f, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False, indent=ind) + ('\n' if nl else ''))
json.dump({'raw': raw_n, 'dup': dup, 'add': dict(add_n)}, open(SH + '/build/repo_sync.json', 'w'), ensure_ascii=False)
print('changed files', len(changed), file=sys.stderr)
