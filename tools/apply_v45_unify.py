#!/usr/bin/env python3
"""v45 执行：把干跑验证过的 1,972 首朝代修正写入 live Turso，并重建 authors 表。
来源：build/consist/v45-unify-plan2.json（全文配对验证，预测与站点逐键一致，佚名除外）。
幂等：works UPDATE 按 id 定值重写；陈毅近现代作者行先查后插；rebuild_authors 本身幂等。
顺序：备份 -> 校验修正仍适用 -> 改 works -> 预插（陈毅，近现代）-> 重建 authors
      -> 陈毅简介归位 -> 重算 meta -> 全量校验。任一步失败即停，不继续。
用法：python3 tools/apply_v45_unify.py [--skip-backup]
写通道与 v44 修复脚本相同：custom.turso helper 的 get_db_client + pipeline_exec。
"""
import json, os, sys, collections

sys.path.insert(0, '/home/hatch/workspace/custom-connectors/custom.turso/bin')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turso as T
from dyn_norm import normalize_works, gn, grp, ndyn
from author_rebuild import rebuild_authors

ORG, DB = 'jisu', 'shijian-v2'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONS = os.path.join(ROOT, 'build', 'consist')
BATCH = 50
SKIP_BACKUP = '--skip-backup' in sys.argv


def query_rows(host, tok, sql):
    body = T.db_query(host, tok, sql)
    out = []
    for res in body.get('results', []):
        if res.get('type') == 'error':
            raise RuntimeError(res['error']['message'])
        result = res['response']['result']
        cols = [c['name'] for c in result.get('cols', [])]
        for row in result.get('rows', []):
            out.append({c: T._value(v) for c, v in zip(cols, row)})
    return out


def run_stmts(host, tok, stmts, label):
    for i in range(0, len(stmts), BATCH):
        chunk = stmts[i:i + BATCH]
        try:
            res = T.pipeline_exec(host, tok, chunk)
        except Exception as e:
            print(f'[{label}] batch {i // BATCH + 1} FAILED: {e}', flush=True)
            for j, (s, p) in enumerate(chunk):
                print('  sql:', s, 'args:', p, flush=True)
            raise
        print(f'[{label}] batch {i // BATCH + 1}: {len(chunk)} stmts, affected '
              f'{sum(r["affected"] for r in res)}', flush=True)


def main():
    plan = json.load(open(os.path.join(CONS, 'v45-unify-plan2.json')))
    corr = plan['corrections']
    print('corrections:', len(corr), flush=True)
    host, tok = T.get_db_client(ORG, DB)

    # ---- 0. 备份
    ids = sorted({c['id'] for c in corr})
    if not SKIP_BACKUP:
        id_list = ','.join(map(str, ids))
        works_bak = query_rows(host, tok,
            f'SELECT id, title, author, author_id, dynasty, era, kind, book, chapter FROM works WHERE id IN ({id_list})')
        authors_bak = query_rows(host, tok, 'SELECT id, name, dynasty, era, intro, works FROM authors ORDER BY id')
        meta_bak = query_rows(host, tok, 'SELECT k, v FROM meta')
        json.dump(works_bak, open(os.path.join(CONS, 'v45-backup-works-2026-11-07.json'), 'w'), ensure_ascii=False, indent=1)
        json.dump(authors_bak, open(os.path.join(CONS, 'v45-backup-authors-2026-11-07.json'), 'w'), ensure_ascii=False, indent=1)
        json.dump(meta_bak, open(os.path.join(CONS, 'v45-backup-meta-2026-11-07.json'), 'w'), ensure_ascii=False, indent=1)
        print(f'backup: works {len(works_bak)} authors {len(authors_bak)} meta {len(meta_bak)}', flush=True)
    else:
        print('backup skipped', flush=True)

    # ---- 0b. 校验：修正的 old 值仍与 live 一致（防数据已变）
    cur = {r['id']: r for r in query_rows(host, tok,
        f"SELECT id, dynasty, era FROM works WHERE id IN ({','.join(map(str, ids))})")}
    assert len(cur) == len(ids), (len(cur), len(ids))
    stale = [c for c in corr if cur[c['id']]['dynasty'] != c['old_dynasty'] or cur[c['id']]['era'] != c['old_era']]
    if stale:
        print('STALE corrections (live 已变，先停下人工核对）:', len(stale))
        for c in stale[:20]:
            print(' ', c, 'live:', cur[c['id']])
        raise SystemExit(1)
    print('pre-check: all corrections still apply', flush=True)

    # 陈毅现状（记下改前简介：重建会按人名把简介铺到三行，事后只清掉改前本无简介的行）
    chenyi = query_rows(host, tok, "SELECT id, name, dynasty, era, intro, works FROM authors WHERE name = '陈毅' ORDER BY id")
    print('chenyi now:', [(r['id'], r['dynasty'], r['works'], bool(r['intro'])) for r in chenyi], flush=True)
    pre_intro = {r['dynasty']: r['intro'] for r in chenyi}
    bio = pre_intro.get('清')
    print('chenyi 清 has bio:', bool(bio), flush=True)

    # ---- 1. 改 works 朝代/era
    stmts = [('UPDATE works SET dynasty=?, era=? WHERE id=?', [c['new_dynasty'], c['new_era'], c['id']]) for c in corr]
    run_stmts(host, tok, stmts, 'works-dynasty')

    # ---- 2. 预插（陈毅，近现代）：占新 id，防止重建时抢走宋的 id 12927
    existing = query_rows(host, tok, "SELECT id FROM authors WHERE name = '陈毅' AND dynasty = '近现代'")
    if existing:
        new_id = existing[0]['id']
        print('chenyi 近现代 already exists, id =', new_id, flush=True)
    else:
        max_id = query_rows(host, tok, 'SELECT max(id) AS m FROM authors')[0]['m']
        new_id = max_id + 1
        run_stmts(host, tok, [('INSERT INTO authors(id, name, dynasty, era, intro, works) VALUES (?,?,?,?,?,0)',
                               [new_id, '陈毅', '近现代', '近现代', bio])], 'chenyi-preinsert')
        print('chenyi 近现代 pre-inserted, id =', new_id, flush=True)

    # ---- 3. 重建 authors（dyn_norm 已含 v45 NOMERGE 7 人）
    def q(sql, *p):
        # rebuild_authors 用 q(sql) 无参数形式；pipeline_exec 走 run
        body = T.db_query(host, tok, sql)
        out = []
        for res in body.get('results', []):
            if res.get('type') == 'error':
                raise RuntimeError(res['error']['message'])
            result = res['response']['result']
            cols = [c['name'] for c in result.get('cols', [])]
            for row in result.get('rows', []):
                out.append({c: T._value(v) for c, v in zip(cols, row)})
        return out

    def run(stmts):
        res = T.pipeline_exec(host, tok, stmts)
        return [{} for _ in res]

    n = rebuild_authors(q, run)
    print('rebuild_authors done, authors =', n, flush=True)

    # ---- 4. 陈毅简介归位：元帅简介只留近现代行；清/宋行若改前本无简介则清空（重建会按人名把简介铺到三行）
    clear_stmts = []
    for dyn in ('清', '宋'):
        if pre_intro.get(dyn) is None:
            clear_stmts.append(('UPDATE authors SET intro=NULL WHERE name=? AND dynasty=? AND intro IS NOT NULL', ['陈毅', dyn]))
    if clear_stmts:
        run_stmts(host, tok, clear_stmts, 'chenyi-intro')
    print('chenyi intro fixed', flush=True)

    # ---- 5. 重算 meta（与 api_sync.apply 末尾相同）
    run_stmts(host, tok, [
        ("UPDATE meta SET v=(SELECT count(*) FROM works) WHERE k='works'", []),
        ("UPDATE meta SET v=(SELECT json_group_array(json_object('era', era, 'kind', kind, 'n', n)) FROM (SELECT era, kind, count(*) n FROM works GROUP BY era, kind)) WHERE k='by_era'", []),
    ], 'meta')

    # ---- 6. 全量校验
    chk = {}
    chk['authors'] = q('SELECT count(*) AS n FROM authors')[0]['n']
    chk['works'] = q('SELECT count(*) AS n FROM works')[0]['n']
    chk['orphan_author_id'] = q('SELECT count(*) AS n FROM works w LEFT JOIN authors a ON a.id = w.author_id WHERE a.id IS NULL')[0]['n']
    chk['wrong_works'] = q('SELECT count(*) AS n FROM authors a WHERE a.works != (SELECT count(*) FROM works w WHERE w.author_id = a.id)')[0]['n']
    chk['works0'] = q('SELECT count(*) AS n FROM authors WHERE works = 0')[0]['n']
    print('verify:', chk, flush=True)
    assert chk['works'] == 785947 and chk['orphan_author_id'] == 0 and chk['wrong_works'] == 0 and chk['works0'] == 0

    # gn 级逐键对照站点（佚名除外；陈毅按拆分后目标）
    agg = q('SELECT author, dynasty, COUNT(*) AS c FROM works GROUP BY author, dynasty')
    rows = [(r['author'], r['dynasty'], r['c']) for r in agg]
    target, _ = normalize_works(rows)
    pred = collections.Counter(dict(target))
    site_idx = json.load(open(os.path.join(ROOT, 'app', 'site', 'data', 'authors.json')))
    site_n = collections.Counter()
    for r in site_idx:
        site_n[(gn(r[0]), grp(ndyn(r[1])))] += r[2]
    want = collections.Counter()
    for (g, d), nn in site_n.items():
        if g != '佚名':
            want[(g, d)] = nn
    want[('陈毅', '清')] = 13
    want[('陈毅', '近现代')] = 11
    want[('陈毅', '宋')] = 2
    pred_f = {k: v for k, v in pred.items() if k[0] != '佚名'}
    mismatch = [(k, pred_f.get(k, 0), want.get(k, 0)) for k in set(pred_f) | set(want)
                if pred_f.get(k, 0) != want.get(k, 0)]
    print('live-vs-site mismatch (excl 佚名):', len(mismatch), flush=True)
    for m in sorted(mismatch, key=lambda x: -abs((x[1] or 0) - (x[2] or 0)))[:20]:
        print('  MISMATCH', m, flush=True)
    assert not mismatch, mismatch[:10]
    ch = q("SELECT id, dynasty, era, works FROM authors WHERE name = '陈毅' ORDER BY dynasty")
    print('chenyi after:', ch, flush=True)
    assert {(r['dynasty'], r['works']) for r in ch} == {('清', 13), ('近现代', 11), ('宋', 2)}
    print('V45 APPLY OK', flush=True)


if __name__ == '__main__':
    main()
