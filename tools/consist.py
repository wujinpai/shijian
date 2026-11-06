# 三方一致性比对：站点 corpus.json / 仓库 chinese-classics / API（/tmp/api.db 由 api_dump.py 导出）
# 键：(作者, 正文汉字简体)；输出 build/consist/*.json
import json, glob, os, re, collections, sqlite3, sys, opencc
P = os.path.dirname(os.path.abspath(__file__)) + '/../..'
cc = opencc.OpenCC('t2s'); N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
_T = {}
def _c(x):
    out = []
    for ch in x:
        v = _T.get(ch)
        if v is None:
            v = cc.convert(ch); _T[ch] = v
        out.append(v)
    return ''.join(out)
nz = lambda s: _c(N.sub('', s or ''))
cc_convert = _c
os.makedirs(P + '/shici/build/consist', exist_ok=True)
def save(n, o): json.dump(o, open(P + f'/shici/build/consist/{n}.json', 'w'), ensure_ascii=False)
site = collections.Counter(); siteT = collections.Counter(); sitemap = {}
for r in json.load(open(P + '/shici/build/corpus.json')):
    t = nz(''.join(r['p'])); k = (_c(r['a']), t); site[k] += 1; siteT[t] += 1; sitemap.setdefault(k, (r['i'], r['t'], r['c']))
repo = collections.Counter(); repoT = collections.Counter(); repomap = {}; chap = 0; kinds = collections.Counter()
for f in glob.glob(P + '/chinese-classics/*/*.json'):
    d = os.path.basename(os.path.dirname(f))
    if d in ('scripts', '名篇索引'): continue
    j = json.load(open(f, encoding='utf-8'))
    a = _c((j.get('author') or '').strip()) or '佚名'
    for w in j.get('works', []):
        t = nz(''.join(w.get('paragraphs') or [])); k = (a, t); repo[k] += 1; repoT[t] += 1; repomap.setdefault(k, (f.split('chinese-classics/')[1], w.get('title')))
    chap += len(j.get('chapters', []))
print('site', sum(site.values()), 'repo works', sum(repo.values()), 'repo chapters', chap)
so = [(k, sitemap[k]) for k in site if k not in repo]; ro = [(k, repomap[k]) for k in repo if k not in site]
print('site-only keys', len(so), ' of which text in repo under other author', sum(1 for k, _ in so if k[1] in repoT))
print('repo-only keys', len(ro), ' of which text on site under other author', sum(1 for k, _ in ro if k[1] in siteT))
print('dup within site', sum(v - 1 for v in site.values() if v > 1), 'dup within repo', sum(v - 1 for v in repo.values() if v > 1))
save('site_only', so[:200000]); save('repo_only', ro[:200000])
if os.path.exists('/tmp/api.db'):
    db = sqlite3.connect('/tmp/api.db'); api = collections.Counter(); apimap = {}
    for i, a, c in db.execute('select id, author, content from w'):
        k = (_c(a or '佚名'), nz(c)); api[k] += 1; apimap.setdefault(k, i)
    ao = [(k, apimap[k]) for k in api if k not in repo]; ra = [(k, repomap[k]) for k in repo if k not in api]
    print('api', sum(api.values()), 'api-only keys', len(ao), 'repo-not-in-api keys', len(ra), 'dup within api', sum(v - 1 for v in api.values() if v > 1))
    save('api_only', ao); save('repo_not_api', ra)
