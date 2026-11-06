# 开放 API（Turso shijian-v2）异作者同文去重 + 异名归并。
# 依据：build/attrib/decisions.json（站点判定）+ build/attrib/o2_*.json（groups2.json 的判定）。
# 需要 /tmp/api.db（tools/api_dump.py 导出）和 build/attrib/api_groups.json（tools/api_xdup.py）。
# 用法：python3 api_fix.py plan   → 写 build/attrib/api_plan.json 并打印统计
#       python3 api_fix.py apply  → 按 plan 改 Turso
import json, re, sys, glob, sqlite3, collections, opencc
sys.path.insert(0, '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/shici/tools')
R = '/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/shici/build/attrib'
cc = opencc.OpenCC('t2s')
N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
nz = lambda s: cc.convert(N.sub('', s))
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003134f]+')
def grams(text):
    out = []
    for seg in CJK.findall(text or ''):
        if len(seg) == 1: out.append(seg)
        else: out.extend(seg[i:i + 2] for i in range(len(seg) - 1))
        out.append('|')
    return ' '.join(out).replace('|', 'zz')

def plan():
    D = json.load(open(R + '/decisions.json'))
    ALIAS = D['alias']
    def canon(a, n=0):
        b = ALIAS.get(a, a)
        return b if b == a or n > 5 else canon(b, n + 1)
    ALIAS = {k: canon(k) for k in ALIAS if canon(k) != k}
    final = {}
    for d in D['groups']: final[nz(d['text'])] = d
    G2 = {g['g']: g for g in json.load(open(R + '/groups2.json'))}
    api = json.load(open(R + '/api_groups.json'))
    id2key = {i: k for k, v in api.items() for i, _, _ in v}
    for f in glob.glob(R + '/o2_*.json'):
        for o in json.load(open(f)):
            ks = {id2key[it['id']] for it in G2[o['g']]['items'] if it['src'] == 'api' and it['id'] in id2key}
            for k in ks: final[k] = o
    db = sqlite3.connect('/tmp/api.db')
    P = []; miss = 0
    for k, rows in api.items():
        d = final.get(k)
        if not d: miss += 1; continue
        A = canon(d['author'])
        info = [(i, t, a, db.execute('select famous from w where id=?', (i,)).fetchone()[0]) for i, t, a in rows]
        cand = [x for x in info if canon(x[2]) == A] or info
        keep = sorted(cand, key=lambda x: (-int(x[3] or 0), x[0]))[0]
        P.append({'keep': keep[0], 'author': A, 'title': d['title'] or keep[1], 'famous': max(int(x[3] or 0) for x in info),
                  'drop': [x[0] for x in info if x[0] != keep[0]]})
    json.dump({'alias': ALIAS, 'groups': P}, open(R + '/api_plan.json', 'w'), ensure_ascii=False)
    print('api groups', len(api), 'planned', len(P), 'no decision', miss, 'drop', sum(len(p['drop']) for p in P))

def apply():
    import tq
    P = json.load(open(R + '/api_plan.json')); ALIAS = P['alias']
    db = sqlite3.connect('/tmp/api.db')
    tq.run([('CREATE TABLE IF NOT EXISTS merged(old_id INTEGER PRIMARY KEY, new_id INTEGER)', [])])
    names = set(ALIAS.values()) | {p['author'] for p in P['groups']}
    aid = {}
    for n in names:
        r = tq.q('select id, dynasty from authors where name=? order by works desc limit 1', n)
        if r: aid[n] = int(r[0]['id'])
    def author_id(n, dyn):
        if n not in aid:
            r = tq.run([('INSERT INTO authors(name, dynasty, era, works) VALUES (?,?,?,0) RETURNING id', [n, dyn, dyn])])[0]
            aid[n] = int(r[0]['id'])
        return aid[n]
    batch = []
    def flush():
        if batch: tq.run(batch); batch.clear()
    for p in P['groups']:
        k = p['keep']; dyn = db.execute('select dynasty from w where id=?', (k,)).fetchone()[0]
        title = p['title']
        batch += [("INSERT INTO works_fts(works_fts, rowid, title, body) SELECT 'delete', id, title, body FROM works_grams WHERE id=?", [k]),
                  ('UPDATE works_grams SET title=? WHERE id=?', [grams(title), k]),
                  ("INSERT INTO works_fts(rowid, title, body) SELECT id, title, body FROM works_grams WHERE id=?", [k]),
                  ('UPDATE works SET title=?, author=?, author_id=?, famous=? WHERE id=?', [title, p['author'], author_id(p['author'], dyn), p['famous'], k])]
        for d in p['drop']:
            batch += [("INSERT INTO works_fts(works_fts, rowid, title, body) SELECT 'delete', id, title, body FROM works_grams WHERE id=?", [d]),
                      ('DELETE FROM works_grams WHERE id=?', [d]), ('DELETE FROM works WHERE id=?', [d]),
                      ('INSERT OR REPLACE INTO merged VALUES (?,?)', [d, k])]
        if len(batch) > 200: flush()
    flush()
    for old, new in ALIAS.items():
        r = tq.q('select count(*) n from works where author=?', old)
        if int(r[0]['n']):
            dyn = tq.q('select dynasty from works where author=? limit 1', old)[0]['dynasty']
            tq.run([('UPDATE works SET author=?, author_id=? WHERE author=?', [new, author_id(new, dyn), old])])
    tq.run([('UPDATE authors SET works=(SELECT count(*) FROM works WHERE author_id=authors.id)', []),
            ('DELETE FROM authors WHERE works=0', []),
            ("UPDATE meta SET v=(SELECT count(*) FROM works) WHERE k='works'", []),
            ("UPDATE meta SET v=(SELECT count(*) FROM authors) WHERE k='authors'", []),
            ("UPDATE meta SET v=(SELECT json_group_array(json_object('era', era, 'kind', kind, 'n', n)) FROM (SELECT era, kind, count(*) n FROM works GROUP BY era, kind)) WHERE k='by_era'", [])])
    print(tq.q('select k, substr(v,1,60) v from meta'))

if __name__ == '__main__': {'plan': plan, 'apply': apply}[sys.argv[1]]()
