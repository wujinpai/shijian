#!/usr/bin/env python3
"""修复 authors 统一迁移：live 库已按旧（有 bug）方案跑了 phase 1-4，
本脚本按修正方案（dyn_norm 已修 gn 分组 + 覆盖表 418 条）把差量补齐。
步骤：拉当前 live 状态 -> 与修正方案比对 -> 只应用差量 -> 校验。
幂等，可重跑。
"""
import json
import sys

sys.path.insert(0, '/home/hatch/workspace/custom-connectors/custom.turso/bin')
sys.path.insert(0, '/home/hatch/workspace/work/shijian/tools')
import turso as T
from dyn_norm import normalize_works, gn, grp

ORG, DB = 'jisu', 'shijian-v2'
PLAN = '/home/hatch/workspace/work/shijian/build/consist/author-migration-plan-2026-11-07.json'
BATCH = 50


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
        res = T.pipeline_exec(host, tok, chunk)
        for j, r in enumerate(res):
            if not r['ok']:
                print(f'[{label}] stmt {i + j} FAILED: {r["error"]}', flush=True)
                print('  sql:', chunk[j][0], 'args:', chunk[j][1], flush=True)
                raise SystemExit(f'repair aborted at {label} stmt {i + j}')
        print(f'[{label}] batch {i // BATCH + 1}: {len(chunk)} stmts, affected {sum(r["affected"] for r in res)}', flush=True)


def main():
    plan = json.load(open(PLAN))
    host, tok = T.get_db_client(ORG, DB)
    print('connected to', host, flush=True)

    # 当前 live 状态
    cur_works = [(r['author'], r['dynasty'], r['era'], r['author_id'], r['n']) for r in
                 query_rows(host, tok, 'SELECT author, dynasty, era, author_id, count(*) AS n FROM works GROUP BY author, dynasty, era, author_id')]
    cur_authors = {r['id']: r for r in
                   query_rows(host, tok, 'SELECT id, name, dynasty, era, intro, works FROM authors ORDER BY id')}
    print(f'current: {len(cur_authors)} authors, {len(cur_works)} works groups', flush=True)

    # 修正方案的目标（用当前 works 分布重算映射；分布与迁移前一致）
    rows = [(a, d, n) for a, d, e, aid, n in cur_works]
    target, mapping = normalize_works(rows)
    key_to_id = {(r[1], r[2]): r[0] for r in plan['new_authors']}
    # 目标 authors 表 = 修正方案的 new_authors（keeper id 已定）
    target_authors = {r[0]: r for r in plan['new_authors']}
    print(f'target: {len(target_authors)} authors', flush=True)

    # 1. 先补齐目标 authors 表中缺失的行（keeper id 须先存在）
    ins, upd, dele = [], [], []
    for kid, r in target_authors.items():
        if kid not in cur_authors:
            ins.append(('INSERT OR IGNORE INTO authors(id, name, dynasty, era, intro, works) VALUES (?,?,?,?,?,?)', r))
        else:
            c = cur_authors[kid]
            if (c['name'], c['dynasty'], c['era'], c['intro'], c['works']) != (r[1], r[2], r[3], r[4], r[5]):
                upd.append(('UPDATE authors SET name=?, dynasty=?, era=?, intro=?, works=? WHERE id=?',
                            [r[1], r[2], r[3], r[4], r[5], kid]))
    for cid in cur_authors:
        if cid not in target_authors:
            dele.append(cid)
    print(f'authors delta: insert {len(ins)}, update {len(upd)}, delete {len(dele)}', flush=True)
    run_stmts(host, tok, ins, 'authors-insert')

    # 2. works 重映射差量
    remap = []
    for a, d, e, aid, n in cur_works:
        nd = mapping[(a, d)]
        nid = key_to_id[(gn(a), grp(nd))]
        if nid != aid:
            remap.append(('UPDATE works SET author_id=? WHERE author_id=? AND dynasty=?', [nid, aid, d]))
    print(f'works remap delta: {len(remap)} groups', flush=True)
    run_stmts(host, tok, remap, 'works-remap')

    # 3. 更新 keeper 行字段
    run_stmts(host, tok, upd, 'authors-update')
    # 4. 删除多余行
    for i in range(0, len(dele), 400):
        ch = dele[i:i + 400]
        ph = ','.join('?' * len(ch))
        run_stmts(host, tok, [(f'DELETE FROM authors WHERE id IN ({ph})', ch)], 'authors-delete')

    # 3. meta
    run_stmts(host, tok, [("UPDATE meta SET v=(SELECT count(*) FROM authors) WHERE k='authors'", [])], 'meta')

    # 4. 校验
    n = query_rows(host, tok, 'SELECT count(*) AS n FROM authors')[0]['n']
    print(f'[verify] authors count: {n} (target {len(target_authors)})', flush=True)
    bad = query_rows(host, tok, 'SELECT count(*) AS n FROM works w LEFT JOIN authors a ON a.id = w.author_id WHERE a.id IS NULL')[0]['n']
    print(f'[verify] works with missing author: {bad}', flush=True)
    badw = query_rows(host, tok, 'SELECT count(*) AS n FROM authors a WHERE a.works != (SELECT count(*) FROM works w WHERE w.author_id = a.id)')[0]['n']
    print(f'[verify] authors with wrong works count: {badw}', flush=True)
    n0 = query_rows(host, tok, 'SELECT count(*) AS n FROM authors WHERE works = 0')[0]['n']
    print(f'[verify] authors with works=0: {n0}', flush=True)
    meta = query_rows(host, tok, "SELECT v FROM meta WHERE k='authors'")[0]['v']
    print(f'[verify] meta authors: {meta}', flush=True)
    if n != len(target_authors) or bad or badw or n0:
        raise SystemExit('verification failed')
    print('repair done', flush=True)


if __name__ == '__main__':
    main()
