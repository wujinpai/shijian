# v35：开放 API（Turso shijian-v2）按仓库增量同步，保留已有 id。
# 仓库每个条目（作品/典籍章节）对应 API 一行：已有的更新字段，没有的插入新 id，多余/重复的删除并写 merged 表（旧 id → 保留 id）。
# 需要 /tmp/api.db（api_dump.py 导出的 w 表）和 REPO_READ 指向的最终仓库。
#   python3 api_sync.py plan  → build/consist/api_sync_plan.json
#   python3 api_sync.py apply → 改 Turso
import json, os, re, sys, sqlite3, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('REPO_READ', '/tmp/cc/chinese-classics')
from canon_lib import *
from repo_canon import gn
from author_rebuild import rebuild_authors
# 与 turso_build.py 相同（ERAS/KIND 两边各一份，历史原因未合一）
ERAS = ['先秦', '秦汉', '魏晋南北朝', '隋', '唐', '五代', '宋', '辽金', '元', '明', '清', '近代', '现代']
KIND = {'诗': '诗', '词': '词', '曲': '曲'}
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003134f]+')
def grams(text):
    out = []
    for seg in CJK.findall(text or ''):
        if len(seg) == 1: out.append(seg)
        else: out.extend(seg[i:i + 2] for i in range(len(seg) - 1))
        out.append('|')
    return ' '.join(out).replace('|', 'zz')
RW = os.environ['REPO_READ']
PL = B + '/consist/api_sync_plan.json'

def repo_rows():
    famous = {(x['title'], x['author']) for x in json.load(open(f'{RW}/名篇索引/唐诗三百首.json'))}
    out = []
    for f in repo_files():
        d = os.path.basename(os.path.dirname(f)); era = next((e for e in ERAS if d.startswith(e)), d); kind = KIND.get(d[len(era):], '诗')
        j = json.load(open(f, encoding='utf-8'))
        if 'chapters' in j:
            book = j.get('title') or os.path.basename(f)[:-5]
            for c in j['chapters']:
                body = '\n'.join(c.get('paragraphs') or [])
                if not body.strip(): continue
                out.append(dict(title=c.get('chapter') or book, author=(c.get('author') or j.get('author') or '').strip(), dynasty=j.get('dynasty', era), era=era,
                                kind='典籍', book=book, chapter=c.get('chapter'), section=c.get('section'), rhythmic=None, source=c.get('source'),
                                content=body, notes=None, famous=0))
            continue
        name = j.get('author') or os.path.basename(f)[:-5]
        for w in j.get('works', []):
            body = '\n'.join(w.get('paragraphs') or [])
            if not body.strip(): continue
            ann = [a for a in (w.get('annotations') or []) if a]
            out.append(dict(title=w.get('title', ''), author=name, dynasty=j.get('dynasty', era), era=era, kind=kind, book=None, chapter=w.get('chapter'),
                            section=w.get('section'), rhythmic=w.get('rhythmic'), source=None, content=body,
                            notes=json.dumps(ann, ensure_ascii=False) if ann else None, famous=1 if (w.get('title'), name) in famous else 0, desc=j.get('author_desc')))
    # v45 逐首朝代覆盖：下次同步/重建时不把已修正的朝代改回去（见 tools/poem_dyn_override.py）。
    from poem_dyn_override import apply_override
    for r in out:
        r['dynasty'], r['era'] = apply_override(r['author'], r['title'], r['dynasty'], r['era'], r['content'])
    return out

def plan():
    Rr = repo_rows(); print('repo rows', len(Rr), flush=True)
    db = sqlite3.connect('/tmp/api.db')
    A = [(i, t, a, dy, fa, c) for i, t, a, dy, fa, c in db.execute('select id,title,author,dynasty,famous,content from w')]
    print('api rows', len(A), flush=True)
    rk = [(gn(s2(r['author'])), nz(r['content'])) for r in Rr]
    ex = collections.defaultdict(list); ba = collections.defaultdict(list)
    for k, (a, t) in enumerate(rk): ex[t].append(k); ba[(a, len(t))].append(k)
    match = {}; left = []
    for row in A:
        a, t = gn(s2(row[2])), nz(row[5])
        c = ex.get(t)
        if c: match[row[0]] = sorted(c, key=lambda k: rk[k][0] != a)[0]; continue
        c = [k for k in ba.get((a, len(t)), []) if near(rk[k][1], t)]
        if c: match[row[0]] = c[0]; continue
        left.append((row[0], a, t))
    tk = collections.defaultdict(list)
    for k, r in enumerate(Rr): tk[(rk[k][0], re.sub(r'\s+', '', s2(r['title'])))].append(k)
    Ai = {row[0]: row for row in A}
    for i, a, t in left:
        c = [k for k in ba.get((a, len(t)), []) if sum(x != y for x, y in zip(rk[k][1], t)) <= max(2, len(t) // 4)]
        if not c: c = tk.get((a, re.sub(r'\s+', '', s2(Ai[i][1]))))
        if c: match[i] = c[0]
    bye = collections.defaultdict(list)
    for i, k in match.items(): bye[k].append(i)
    keep = {}; drop = {}
    for k, ids in bye.items():
        ids.sort(key=lambda i: (gn(s2(Ai[i][2])) != rk[k][0], -int(Ai[i][4] or 0), i))
        keep[ids[0]] = k
        for i in ids[1:]: drop[i] = ids[0]
    gone = [row[0] for row in A if row[0] not in match]
    # 整组合抄（仓库已分首）：跳转到第一首
    inv = {k: i for i, k in keep.items()}
    heads = collections.defaultdict(list)
    for k, (a, t) in enumerate(rk):
        if len(t) >= 20: heads[(a, t[:8])].append(k)
    g2 = []
    for i in gone:
        a, t = gn(s2(Ai[i][2])), nz(Ai[i][5])
        c = [k for k in heads.get((a, t[:8]), []) if t.startswith(rk[k][1]) and k in inv]
        if c: drop[i] = inv[sorted(c, key=lambda k: -len(rk[k][1]))[0]]
        else: g2.append(i)
    print('gone → merged to first part', len(gone) - len(g2))
    gone = g2
    upd = []
    for i, k in keep.items():
        r = Rr[k]; row = Ai[i]
        if (row[1], row[2], row[3], row[5]) != (r['title'], r['author'], r['dynasty'], r['content']) or int(row[4] or 0) != r['famous']:
            upd.append([i, k, row[1] != r['title'] or row[5] != r['content']])
    new = [k for k in range(len(Rr)) if k not in bye]
    print('keep', len(keep), 'update', len(upd), 'drop dup', len(drop), 'drop gone', len(gone), 'insert', len(new), flush=True)
    for i in gone[:15]: print('GONE', i, Ai[i][2], Ai[i][1], nz(Ai[i][5])[:16])
    json.dump({'upd': upd, 'drop': drop, 'gone': gone, 'new': new, 'n_repo': len(Rr)}, open(PL, 'w'))

def apply():
    # 可续跑：按阶段分块，进度记在 PROG；每次最多跑 ~1000 秒
    import tq, time
    from concurrent.futures import ThreadPoolExecutor
    PROG = B + '/consist/api_sync_progress.json'
    pg = json.load(open(PROG)) if os.path.exists(PROG) else {'del': 0, 'upd': 0, 'ins': 0, 'fin': 0}
    P = json.load(open(PL)); t0 = time.time()
    tq.run([('CREATE TABLE IF NOT EXISTS merged(old_id INTEGER PRIMARY KEY, new_id INTEGER)', [])])
    def save(): json.dump(pg, open(PROG, 'w'))
    def run_chunks(name, items, mk, size=120):
        chunks = [items[x:x + size] for x in range(0, len(items), size)]
        def go(ch):
            b = [st for it in ch for st in mk(it)]
            for t in range(5):
                try: tq.run(b); return
                except Exception as e:
                    if t == 4: raise
                    time.sleep(2 + t * 3)
        with ThreadPoolExecutor(4) as ex:
            while pg[name] < len(chunks):
                if time.time() - t0 > 1000: save(); print('pause', name, pg[name], '/', len(chunks), flush=True); return False
                grp = chunks[pg[name]:pg[name] + 8]
                list(ex.map(go, grp)); pg[name] += len(grp); save()
        print('done', name, len(items), flush=True); return True
    def fts_del(i): return ("INSERT INTO works_fts(works_fts, rowid, title, body) SELECT 'delete', id, title, body FROM works_grams WHERE id=?", [i])
    dl = [(int(i), int(n)) for i, n in P['drop'].items()] + [(int(i), None) for i in P['gone']]
    # 删除按块整批：一块 400 个 id，用 IN 一次删（逐条删太慢）
    dch = [dl[x:x + 400] for x in range(0, len(dl), 400)]
    def mk_del(ch):
        ids = [i for i, n in ch]; ph = ','.join('?' * len(ids))
        out = [("INSERT INTO works_fts(works_fts, rowid, title, body) SELECT 'delete', id, title, body FROM works_grams WHERE id IN (" + ph + ")", ids),
               ('DELETE FROM works_grams WHERE id IN (' + ph + ')', ids), ('DELETE FROM works WHERE id IN (' + ph + ')', ids)]
        mm = [(i, n) for i, n in ch if n is not None]
        if mm: out.append(('INSERT OR REPLACE INTO merged VALUES ' + ','.join('(?,?)' for _ in mm), [v for p in mm for v in p]))
        return out
    pg.setdefault('del2', 0)
    if not run_chunks('del2', dch, mk_del, 1): return
    Rr = repo_rows(); assert len(Rr) == P['n_repo']
    aid = {(r['name'], r['era']): int(r['id']) for r in tq.q('select id, name, era from authors')}
    need = {(Rr[k]['author'], Rr[k]['era']): Rr[k] for k in [u[1] for u in P['upd']] + P['new']}
    for key, r in need.items():
        if key not in aid:
            x = tq.run([('INSERT INTO authors(name, dynasty, era, intro, works) VALUES (?,?,?,?,0) RETURNING id', [r['author'], r['dynasty'], r['era'], r.get('desc')])])[0]
            aid[key] = int(x[0]['id'])
    COLS = 'title, author_id, author, dynasty, era, kind, book, chapter, section, rhythmic, source, content, notes, famous'
    def vals(r): return [r['title'], aid[(r['author'], r['era'])], r['author'], r['dynasty'], r['era'], r['kind'], r['book'], r['chapter'], r['section'], r['rhythmic'], r['source'], r['content'], r['notes'], r['famous']]
    def tg(r): return grams(r['title'] if r['kind'] != '典籍' or r['title'] == r['book'] else r['book'] + '·' + r['title'])
    def mk_upd(u):
        i, k, ft = u; r = Rr[k]
        out = [('UPDATE works SET ' + ', '.join(c + '=?' for c in COLS.split(', ')) + ' WHERE id=?', vals(r) + [i])]
        if ft: out += [fts_del(i), ('UPDATE works_grams SET title=?, body=? WHERE id=?', [tg(r), grams(r['content']), i]),
                       ("INSERT INTO works_fts(rowid, title, body) SELECT id, title, body FROM works_grams WHERE id=?", [i])]
        return out
    if not run_chunks('upd', P['upd'], mk_upd, 80): return
    base = 884767  # v34 时 API 最大 id；新篇从其后编号（可重跑）
    def mk_ins(x):
        n, k = x; r = Rr[k]; nid = base + 1 + n
        return [fts_del(nid), ('INSERT OR REPLACE INTO works(id, ' + COLS + ') VALUES (?' + ',?' * 14 + ')', [nid] + vals(r)),
                ('INSERT OR REPLACE INTO works_grams VALUES (?,?,?)', [nid, tg(r), grams(r['content'])]),
                ("INSERT INTO works_fts(rowid, title, body) SELECT id, title, body FROM works_grams WHERE id=?", [nid])]
    if not run_chunks('ins', list(enumerate(P['new'])), mk_ins, 60): return
    tq.run([('UPDATE merged SET new_id=(SELECT m2.new_id FROM merged m2 WHERE m2.old_id=merged.new_id) WHERE new_id IN (SELECT old_id FROM merged)', [])] * 3)
    # 作者表统一重建（与站点同一规则，见 tools/dyn_norm.py）：替代旧的按 (人名, era) 计 works。
    rebuild_authors(tq.q, tq.run)
    tq.run([("UPDATE meta SET v=(SELECT count(*) FROM works) WHERE k='works'", []),
            ("UPDATE meta SET v=(SELECT json_group_array(json_object('era', era, 'kind', kind, 'n', n)) FROM (SELECT era, kind, count(*) n FROM works GROUP BY era, kind)) WHERE k='by_era'", [])])
    pg['fin'] = 1; save()
    print('FINISHED', tq.q('select k, substr(v,1,80) v from meta'))

if __name__ == '__main__': {'plan': plan, 'apply': apply}[sys.argv[1]]()
