# 给 Turso 库里典籍篇章的 FTS 标题列加上书名（弟子规·总叙 可按「弟子规」搜到）
import json, os, sys, urllib.request, re
sys.path.insert(0, os.path.dirname(__file__))
CJK = re.compile(r'[\u3400-\u9fff\U00020000-\U0003134f]+')
def grams(text):
    out = []
    for seg in CJK.findall(text or ''):
        if len(seg) == 1: out.append(seg)
        else: out.extend(seg[i:i + 2] for i in range(len(seg) - 1))
        out.append('|')
    return ' '.join(out).replace('|', 'zz')
URL = 'https://shijian-v2-jisu.aws-ap-northeast-1.turso.io/v2/pipeline'
TOK = open(os.path.join(os.path.dirname(__file__), '../../.secrets/turso-v2-full')).read().strip()
def arg(v): return {'type': 'null'} if v is None else {'type': 'integer', 'value': str(v)} if isinstance(v, int) else {'type': 'text', 'value': v}
def run(stmts):
    body = {'requests': [{'type': 'execute', 'stmt': {'sql': s, 'args': [arg(a) for a in a_]}} for s, a_ in stmts] + [{'type': 'close'}]}
    r = urllib.request.Request(URL, json.dumps(body).encode(), {'authorization': 'Bearer ' + TOK, 'content-type': 'application/json'})
    res = json.load(urllib.request.urlopen(r, timeout=120))['results']
    for x in res:
        if x['type'] == 'error': raise SystemExit(x['error'])
    return res
def rows(res):
    r = res['response']['result']; cols = [c['name'] for c in r['cols']]
    return [dict(zip(cols, [c.get('value') for c in row])) for row in r['rows']]
if sys.argv[1:] == ['count']:
    print(rows(run([("SELECT count(*) n FROM works w WHERE w.era IN ('先秦','唐','宋','明','清','秦汉','魏晋南北朝') AND w.kind='典籍' AND w.book IS NOT NULL AND w.book<>w.title", [])])[0])); raise SystemExit
allw = rows(run([("SELECT w.id, w.title, w.book FROM works w WHERE w.era IN ('先秦','唐','宋','明','清','秦汉','魏晋南北朝') AND w.kind='典籍' AND w.book IS NOT NULL AND w.book<>w.title", [])])[0])
print('works', len(allw), flush=True); done = 0
for k in range(0, len(allw), 100):
    part = {int(r['id']): r for r in allw[k:k + 100]}
    g = rows(run([("SELECT id, title gt, body gb FROM works_grams WHERE id IN (%s)" % ','.join(map(str, part)), [])])[0])
    st = []
    for x in g:
        rid = int(x['id']); r = part[rid]; nt = grams(r['book'] + '·' + r['title'])
        if x['gt'] == nt: continue
        st.append(("INSERT INTO works_fts(works_fts, rowid, title, body) VALUES('delete', ?, ?, ?)", [rid, x['gt'], x['gb']]))
        st.append(("UPDATE works_grams SET title=? WHERE id=?", [nt, rid]))
        st.append(("INSERT INTO works_fts(rowid, title, body) VALUES (?, ?, ?)", [rid, nt, x['gb']]))
    if st: run(st)
    done += len(st) // 3; print('done', done, flush=True)
print('total', done)
