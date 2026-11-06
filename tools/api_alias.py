# v36：API 按仓库同人异名归一（改名/并作者）＋删掉仓库已去掉的近似重复（写 merged）。DRY=1 只打印。
import sys, os, json, re, glob, difflib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tq import q, run
import repo_canon as rc
DRY = os.environ.get('DRY') == '1'
R = os.environ.get('REPO_READ', '/tmp/cc/chinese-classics')
MAP = {k: v for k, v in rc.GX.items() if k not in ('金履详', '阙名', '作者未详')}
MAP.update({'赵汝谠': '赵汝譡', '陈珏': '陈玨'})
nz = lambda s: re.sub(r'[^\u3400-\u9fff\U00020000-\U0003ffff]', '', s or '')
# 1) 改名
st = []; touched = set(MAP.values())
for old, new in MAP.items():
    rows = q('select id,dynasty from authors where name=?', old)
    for a in rows:
        oid = int(a['id']); dy = a['dynasty']
        if old == '陈珏' and dy != '宋': continue
        t = q('select id from authors where name=? and dynasty=? order by works+0 desc', new, dy) or q('select id from authors where name=? order by works+0 desc', new)
        if t:
            tid = int(t[0]['id']); st.append(('update works set author=?, author_id=? where author_id=?', [new, tid, oid])); st.append(('delete from authors where id=?', [oid]))
            print('merge', old, oid, '->', new, tid)
        else:
            st.append(('update works set author=? where author_id=?', [new, oid])); st.append(('update authors set name=? where id=?', [new, oid]))
            print('rename', old, oid, '->', new)
if not DRY:
    for i in range(0, len(st), 100): run(st[i:i + 100])
# 2) 仓库去掉的近似重复：受影响作者在 API 有、仓库无的正文 → 删，merged 指向保留篇
repo = collections.defaultdict(set)
for f in glob.glob(R + '/*/*.json'):
    if '名篇索引' in f: continue
    j = json.load(open(f))
    if not isinstance(j, dict) or 'works' not in j: continue
    if j.get('author') in touched:
        for w in j['works']: repo[j['author']].add(nz(''.join(w.get('paragraphs') or [])))
dels = []
for name in touched:
    W = q("select id,content from works where author=? and kind<>'典籍'", name)
    keep = [(int(w['id']), nz(w['content'])) for w in W if nz(w['content']) in repo[name]]
    for w in W:
        t = nz(w['content'])
        if t in repo[name] or not t: continue
        best = max(keep, key=lambda k: difflib.SequenceMatcher(None, k[1], t, autojunk=False).ratio() if abs(len(k[1]) - len(t)) <= max(3, len(t) // 8) else 0, default=None)
        r = difflib.SequenceMatcher(None, best[1], t, autojunk=False).ratio() if best else 0
        if r >= 0.85: dels.append((int(w['id']), best[0]))
        else: print('NOMATCH', name, w['id'], t[:20])
print('dels', len(dels))
if not DRY and dels:
    st = []
    for o, n in dels:
        st += [('update merged set new_id=? where new_id=?', [n, o]), ('insert or replace into merged(old_id,new_id) values (?,?)', [o, n]),
               ("INSERT INTO works_fts(works_fts, rowid, title, body) SELECT 'delete', id, title, body FROM works_grams WHERE id=?", [o]),
               ('delete from works_grams where id=?', [o]), ('delete from works where id=?', [o])]
    for i in range(0, len(st), 100):
        try: run(st[i:i + 100])
        except Exception as e: print('ERR', str(e)[:300]); break
# 3) 计数
if not DRY:
    run([('update authors set works=(select count(*) from works w where w.author_id=authors.id)', [])])
    run([('delete from authors where works=0', [])])
    nw = q('select count(*) n from works')[0]['n']; na = q('select count(*) n from authors')[0]['n']
    run([("update meta set v=? where k='works'", [nw]), ("update meta set v=? where k='authors'", [na]),
         ("UPDATE meta SET v=(SELECT json_group_array(json_object('era', era, 'kind', kind, 'n', n)) FROM (SELECT era, kind, count(*) n FROM works GROUP BY era, kind)) WHERE k='by_era'", [])])
    print('works', nw, 'authors', na)
