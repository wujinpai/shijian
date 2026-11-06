# 统一数据（2026-11-06，用户：仓库为唯一数据源，站点/API/关于页一致、不重复）
# 公共函数：读仓库（作品 + 典籍章节），文本归一，配对。
import json, glob, os, re, pickle, collections, opencc
P = '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03'
REPO = os.environ.get('REPO_READ', P + '/chinese-classics'); SH = P + '/shici'; B = SH + '/build'
cc = opencc.OpenCC('t2s'); N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
class _T(dict):
    def __missing__(s, o): v = cc.convert(chr(o)); s[o] = v; return v
_TB = _T()
def s2(x): return (x or '').translate(_TB)
def nz(x): return N.sub('', x or '').translate(_TB)
def near(a, b): return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= max(1, len(a) // 10)
SKIP = ('scripts', '名篇索引')
def repo_files():
    for f in sorted(glob.glob(REPO + '/*/*.json')):
        if os.path.basename(os.path.dirname(f)) in SKIP: continue
        yield f
def load_repo(cache=True):
    """返回 E 列表：(kind 'w'|'c', relpath, idx, author, title, text)；按文件 mtime 缓存。"""
    cp = '/tmp/repo_cache.pkl'
    old = pickle.load(open(cp, 'rb')) if cache and os.path.exists(cp) else {}
    new = {}; E = []
    for f in repo_files():
        rp = f[len(REPO) + 1:]; mt = os.path.getmtime(f)
        if rp in old and old[rp][0] == mt: ent = old[rp][1]
        else:
            j = json.load(open(f, encoding='utf-8')); ent = []
            a = s2((j.get('author') or '').strip()) or '佚名'
            for n, w in enumerate(j.get('works', [])): ent.append(('w', rp, n, a, w.get('title') or '', nz(''.join(w.get('paragraphs') or []))))
            for n, c in enumerate(j.get('chapters', [])): ent.append(('c', rp, n, s2((c.get('author') or '').strip()) or a, c.get('chapter') or '', nz(''.join(c.get('paragraphs') or []))))
        new[rp] = (mt, ent); E += ent
    pickle.dump(new, open(cp, 'wb'))
    return E
