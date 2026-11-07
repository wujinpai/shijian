# chinese-classics (github.com/wujinpai/chinese-classics) -> SQLite file for Turso upload.
# Output: shici/build/classics.db  (tables authors, works, works_fts[contentless FTS5 over CJK bigrams], meta)
import json, os, re, sqlite3, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dyn_norm import normalize_works, gn, grp

from paths import PARENT as ROOT
SRC = f'{ROOT}/chinese-classics'
OUT = '/tmp/classics.db'  # build on local disk: sqlite corrupts on JuiceFS

ERAS = ['先秦', '秦汉', '魏晋南北朝', '隋', '唐', '五代', '宋', '辽金', '元', '明', '清', '近代', '现代']
KIND = {'诗': '诗', '词': '词', '曲': '曲'}
NORM = re.compile(r'[^\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003134f?□\ufffd]')
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003134f]+')

def grams(text):
    out = []
    for seg in CJK.findall(text or ''):
        if len(seg) == 1: out.append(seg)
        else: out.extend(seg[i:i + 2] for i in range(len(seg) - 1))
        out.append('|')  # segment break keeps phrases from matching across punctuation
    return ' '.join(out).replace('|', 'zz')

def dirs():
    ds = [d for d in os.listdir(SRC) if os.path.isdir(f'{SRC}/{d}') and d not in ('scripts', '名篇索引') and not d.startswith('.')]
    def key(d):
        for i, e in enumerate(ERAS):
            if d.startswith(e) and d[len(e):] in ('诗', '词', '曲', ''): return (i, '诗词曲'.find(d[len(e):] or '诗'))
        return (99, 0)
    return sorted(ds, key=key)

PACK = os.environ.get('CC_PACK') or f'{ROOT}/shici/build/cc'  # load.py 的 buyi 用 build/cc（旧快照）；Turso 重建用 CC_PACK=build/cc2
def pack():
    import gzip; os.makedirs(PACK, exist_ok=True)
    for d in dirs():
        out = f'{PACK}/{d}.json.gz'
        if os.path.exists(out): continue
        rows = [json.load(open(f)) | {'_f': os.path.basename(f)[:-5]} for f in sorted(glob.glob(f'{SRC}/{d}/*.json'))]
        tmp = out + '.part'; gzip.open(tmp, 'wt').write(json.dumps(rows, ensure_ascii=False)); os.replace(tmp, out); print('packed', d, len(rows), flush=True)

def files(d):
    import gzip
    return json.loads(gzip.open(f'{PACK}/{d}.json.gz', 'rt').read())

def unify_authors(A, W):
    """作者表统一（与站点 load.py / emit.py 同一规则，见 tools/dyn_norm.py）：
    作者按 (人名, 朝代) 分组，朝代经 DYN_NORM + 按作者合并相邻/零星朝代 + 站点标签覆盖。
    典籍按书作者分组（章作者只是异名变体）。返回重建后的 (A, W)，W 的 author_id 已重映射。"""
    import collections as _collections
    _agg = _collections.Counter()
    _era_c = _collections.defaultdict(_collections.Counter)
    _intro = {}
    for _r in A:
        _g = gn(_r[1])
        if _r[4] and (_g not in _intro or _r[5] > _intro[_g][1]):
            _intro[_g] = (_r[4], _r[5])
    for _w in W:
        if _w[6] == '典籍':
            _ga, _gd = A[_w[2] - 1][1], A[_w[2] - 1][2]
        else:
            _ga, _gd = _w[3], _w[4]
        _agg[(_ga, _gd)] += 1
    _target, _map = normalize_works([(a, d, n) for (a, d), n in _agg.items()])
    for _w in W:
        if _w[6] == '典籍':
            _ga, _gd = A[_w[2] - 1][1], A[_w[2] - 1][2]
        else:
            _ga, _gd = _w[3], _w[4]
        _era_c[(gn(_ga), grp(_map[(_ga, _gd)]))][_w[5]] += 1
    _newA = []
    _key2aid = {}
    for _i, ((_name, _dyn), _cnt) in enumerate(sorted(_target.items(), key=lambda kv: -kv[1]), 1):
        _key2aid[(_name, _dyn)] = _i
        _newA.append([_i, _name, _dyn, _era_c[(_name, _dyn)].most_common(1)[0][0], _intro.get(_name, (None, 0))[0], _cnt])
    for _w in W:
        if _w[6] == '典籍':
            _ga, _gd = A[_w[2] - 1][1], A[_w[2] - 1][2]
        else:
            _ga, _gd = _w[3], _w[4]
        _w[2] = _key2aid[(gn(_ga), grp(_map[(_ga, _gd)]))]
    return _newA, W


def main():
    if os.path.exists(OUT): os.remove(OUT)
    db = sqlite3.connect(OUT)
    db.executescript('''
    PRAGMA page_size=4096; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-400000;
    CREATE TABLE authors(id INTEGER PRIMARY KEY, name TEXT NOT NULL, dynasty TEXT, era TEXT, intro TEXT, works INTEGER DEFAULT 0);
    CREATE TABLE works(id INTEGER PRIMARY KEY, title TEXT NOT NULL, author_id INTEGER, author TEXT, dynasty TEXT, era TEXT,
      kind TEXT, book TEXT, chapter TEXT, section TEXT, rhythmic TEXT, source TEXT, content TEXT NOT NULL, notes TEXT, famous INTEGER DEFAULT 0);
    CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
    ''')
    famous = {(x['title'], x['author']) for x in json.load(open(f'{SRC}/名篇索引/唐诗三百首.json'))}
    aid = 0; wid = 0; A = []; W = []; F = []; AK = {}; SEEN = {}; dups = 0
    for d in dirs():
        era = next((e for e in ERAS if d.startswith(e)), d)
        kind = KIND.get(d[len(era):], '诗')
        for j in files(d):
            if 'chapters' in j:  # 典籍单行本
                book = j.get('title') or j['_f']
                aid += 1; A.append([aid, j.get('author', ''), j.get('dynasty', era), era, None, 0]); n = 0
                for c in j['chapters']:
                    body = '\n'.join(c.get('paragraphs') or [])
                    if not body.strip(): continue
                    wid += 1; n += 1
                    t = c.get('chapter') or book
                    W.append([wid, t, aid, c.get('author', '').strip() or j.get('author', ''), j.get('dynasty', era), era, '典籍', book,
                              c.get('chapter'), c.get('section'), None, c.get('source'), body, None, 0])
                    F.append((wid, grams(t if t == book else book + '·' + t), grams(body)))  # 标题索引带书名
                A[-1][5] = n
                continue
            name = j.get('author', '') or j['_f']
            key = (name, era)  # 同一作者的诗、词、曲分在不同目录，合并为一位作者
            if key in AK: cur = AK[key]; cur[4] = cur[4] or j.get('author_desc') or None
            else:
                aid += 1; cur = AK[key] = [aid, name, j.get('dynasty', era), era, j.get('author_desc') or None, 0]; A.append(cur)
            n = cur[5]
            for w in j.get('works', []):
                body = '\n'.join(w.get('paragraphs') or [])
                if not body.strip(): continue
                # 源数据里同一作者同题、正文相同或只差个别异体字/缺字（≤10%）的重复条目只收一次；保留缺字（?□）较少的版本
                nt = NORM.sub('', body); bad = sum(nt.count(c) for c in '?□\ufffd')
                grp = SEEN.setdefault((name, w.get('title', ''), len(nt)), [])
                hit = next((g for g in grp if sum(x != y for x, y in zip(g[0], nt)) <= max(1, len(nt) // 10)), None)
                if hit:
                    dups += 1
                    if bad < hit[1]:
                        hit[1] = bad; W[hit[2]][12] = body
                    hit[3].append(body)  # 异文也进全文索引：搜「床前明月光」仍能找到《静夜思》
                    F[hit[2]] = (F[hit[2]][0], F[hit[2]][1], ' zz '.join(grams(b) for b in hit[3]))
                    continue
                grp.append([nt, bad, len(W), [body]])
                wid += 1; n += 1
                ann = [a for a in (w.get('annotations') or []) if a]
                W.append([wid, w.get('title', ''), cur[0], name, j.get('dynasty', era), era, kind, None, w.get('chapter'), w.get('section'),
                          w.get('rhythmic'), None, body, json.dumps(ann, ensure_ascii=False) if ann else None,
                          1 if (w.get('title'), name) in famous else 0])
                F.append((wid, grams(w.get('title', '')), grams(body)))
            cur[5] = n
    # v45 逐首朝代覆盖：重建时不把已修正的朝代改回去（见 tools/poem_dyn_override.py）。
    # 典籍按书作者分组，书的作者行朝代须同步改（仅当与章节原朝代一致时）。
    from poem_dyn_override import apply_override
    for _w in W:
        _nd, _ne = apply_override(_w[3], _w[1], _w[4], _w[5], _w[12])
        if (_nd, _ne) != (_w[4], _w[5]):
            if _w[6] == '典籍' and A[_w[2] - 1][2] == _w[4]:
                A[_w[2] - 1][2] = _nd
            _w[4], _w[5] = _nd, _ne
    A, W = unify_authors(A, W)
    aid = len(A)
    print('authors unified', aid, 'works', wid, flush=True)
    db.executemany('INSERT INTO authors VALUES (?,?,?,?,?,?)', A)
    db.executemany('INSERT INTO works VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', W)
    db.commit()
    db.executescript('''
    CREATE INDEX works_author ON works(author_id);
    CREATE INDEX works_era_kind ON works(era, kind);
    CREATE INDEX works_title ON works(title);
    CREATE INDEX authors_name ON authors(name);
    CREATE TABLE works_grams(id INTEGER PRIMARY KEY, title TEXT, body TEXT);
    CREATE VIRTUAL TABLE works_fts USING fts5(title, body, content='works_grams', content_rowid='id', columnsize=0, detail=full, tokenize="unicode61 remove_diacritics 0");
    ''')
    db.executemany('INSERT INTO works_grams VALUES (?,?,?)', F); db.commit(); del F
    db.execute("INSERT INTO works_fts(works_fts) VALUES('rebuild')"); db.commit()
    db.execute("INSERT INTO works_fts(works_fts) VALUES('optimize')")
    db.executemany('INSERT INTO meta VALUES (?,?)', [('works', str(wid)), ('authors', str(aid)), ('source', 'github.com/wujinpai/chinese-classics')])
    db.commit()
    db.close()
    print('dups skipped', dups, 'works', wid, 'authors', aid, 'MB', os.path.getsize(OUT) // 2**20)

def fts():
    import pickle
    F = pickle.load(open('/tmp/fts_rows.pkl', 'rb'))
    db = sqlite3.connect(OUT)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-400000;')
    db.execute("INSERT INTO works_fts(works_fts, rank) VALUES('automerge', 0)")
    for i in range(0, len(F), 50000):
        db.executemany('INSERT INTO works_fts(rowid, title, body) VALUES (?,?,?)', F[i:i + 50000]); db.commit(); print('fts', i, flush=True)
    db.execute("INSERT INTO works_fts(works_fts) VALUES('optimize')"); db.commit()
    db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA wal_checkpoint(TRUNCATE)'); db.execute('VACUUM'); db.close()
    print('MB', os.path.getsize(OUT) // 2**20)

if __name__ == '__main__':
    pack() if sys.argv[1:] == ['pack'] else main()
