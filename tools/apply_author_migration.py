#!/usr/bin/env python3
"""应用 authors 表统一迁移到 live Turso 库（shijian-v2）。
分阶段、可重跑（各阶段均幂等）、每阶段后校验。先备份再执行。
用法：python3 tools/apply_author_migration.py [--phase N] [--dry-run]
  --phase N  只跑第 N 阶段（1..5）；不指定则全跑
  --dry-run  只打印语句数，不执行
阶段：1 插入新作者行；2 重映射 works.author_id；3 更新 keeper 作者行；
     4 删除孤儿作者行；5 更新 meta；每阶段后自动校验。
"""
import argparse
import json
import sys
import time

sys.path.insert(0, '/home/hatch/workspace/custom-connectors/custom.turso/bin')
sys.path.insert(0, '/home/hatch/workspace/work/shijian/tools')
import turso as T

ORG, DB = 'jisu', 'shijian-v2'
PLAN = '/home/hatch/workspace/work/shijian/build/consist/author-migration-plan-2026-11-07.json'
OLD_AUTHORS = '/home/hatch/workspace/work/shijian/build/consist/authors-backup-2026-11-07.json'
BATCH = 50


def run_stmts(host, tok, stmts, label):
    """Run statements in batches of BATCH; abort on first error with context."""
    total_aff = 0
    for i in range(0, len(stmts), BATCH):
        chunk = stmts[i:i + BATCH]
        try:
            res = T.pipeline_exec(host, tok, chunk)
        except Exception as e:
            print(f'[{label}] batch {i // BATCH + 1} FAILED: {e}', flush=True)
            raise
        for j, r in enumerate(res):
            if not r['ok']:
                print(f'[{label}] stmt {i + j} FAILED: {r["error"]}', flush=True)
                print('  sql:', chunk[j][0], 'args:', chunk[j][1], flush=True)
                raise SystemExit(f'migration aborted at {label} stmt {i + j}')
            total_aff += r['affected']
        print(f'[{label}] batch {i // BATCH + 1}: {len(chunk)} stmts, affected {sum(r["affected"] for r in res)}', flush=True)
    return total_aff


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', type=int, choices=[1, 2, 3, 4, 5])
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    plan = json.load(open(PLAN))
    old = {r[0]: r for r in json.load(open(OLD_AUTHORS))['rows']}
    host, tok = T.get_db_client(ORG, DB)
    print('connected to', host, flush=True)

    new_authors = plan['new_authors']
    orphans = plan['orphans']
    remap = plan['remap']

    def do(phase, fn):
        if args.phase and args.phase != phase:
            return
        print(f'--- phase {phase} ---', flush=True)
        fn()
        verify(phase)

    def verify(phase):
        if args.dry_run:
            return
        if phase >= 1:
            n = query_rows(host, tok, 'SELECT count(*) AS n FROM authors')[0]['n']
            print(f'[verify] authors count: {n}', flush=True)
        if phase >= 2:
            bad = query_rows(host, tok, 'SELECT count(*) AS n FROM works w LEFT JOIN authors a ON a.id = w.author_id WHERE a.id IS NULL')[0]['n']
            print(f'[verify] works with missing author: {bad}', flush=True)
            if bad:
                raise SystemExit('works point at missing authors, aborting')
        if phase >= 3:
            n0 = query_rows(host, tok, 'SELECT count(*) AS n FROM authors WHERE works = 0')[0]['n']
            print(f'[verify] authors with works=0: {n0}', flush=True)
        if phase >= 4:
            badw = query_rows(host, tok, 'SELECT count(*) AS n FROM authors a WHERE a.works != (SELECT count(*) FROM works w WHERE w.author_id = a.id)')[0]['n']
            print(f'[verify] authors with wrong works count: {badw}', flush=True)
            if badw:
                raise SystemExit('authors.works inconsistent with works table, aborting')
            n0 = query_rows(host, tok, 'SELECT count(*) AS n FROM authors WHERE works = 0')[0]['n']
            print(f'[verify] authors with works=0: {n0}', flush=True)
            if n0:
                raise SystemExit('authors with works=0 remain after orphan delete, aborting')

    # Phase 1: insert new author rows (only 10)
    def p1():
        # new ids are the ones not present in the old authors table
        stmts = [('INSERT OR IGNORE INTO authors(id, name, dynasty, era, intro, works) VALUES (?,?,?,?,?,?)', r)
                 for r in new_authors if r[0] not in old]
        print(f'phase 1: {len(stmts)} new author rows', flush=True)
        if args.dry_run:
            return
        run_stmts(host, tok, stmts, 'phase1')

    # Phase 2: remap works.author_id by (old_id, dynasty)
    def p2():
        stmts = [('UPDATE works SET author_id=? WHERE author_id=? AND dynasty=?', [nid, aid, d])
                 for aid, d, nid, n in remap]
        print(f'phase 2: {len(stmts)} update groups, {sum(r[3] for r in remap)} works', flush=True)
        if args.dry_run:
            return
        run_stmts(host, tok, stmts, 'phase2')

    # Phase 3: update keeper author rows whose fields changed
    def p3():
        stmts = []
        for r in new_authors:
            oid = r[0]
            if oid not in old:
                continue
            o = old[oid]
            # old: [id, name, dynasty, era, intro, works]
            if (o[1], o[2], o[3], o[4], o[5]) != (r[1], r[2], r[3], r[4], r[5]):
                stmts.append(('UPDATE authors SET name=?, dynasty=?, era=?, intro=?, works=? WHERE id=?',
                              [r[1], r[2], r[3], r[4], r[5], oid]))
        print(f'phase 3: {len(stmts)} keeper rows to update', flush=True)
        if args.dry_run:
            return
        run_stmts(host, tok, stmts, 'phase3')

    # Phase 4: delete orphan author rows
    def p4():
        print(f'phase 4: {len(orphans)} orphan rows to delete', flush=True)
        if args.dry_run:
            return
        for i in range(0, len(orphans), 400):
            ch = orphans[i:i + 400]
            ph = ','.join('?' * len(ch))
            run_stmts(host, tok, [(f'DELETE FROM authors WHERE id IN ({ph})', ch)], 'phase4')

    # Phase 5: update meta
    def p5():
        print('phase 5: update meta authors count', flush=True)
        if args.dry_run:
            return
        run_stmts(host, tok, [("UPDATE meta SET v=(SELECT count(*) FROM authors) WHERE k='authors'", [])], 'phase5')
        rows = query_rows(host, tok, "SELECT v FROM meta WHERE k='authors'")
        print('[verify] meta authors:', rows[0]['v'], flush=True)

    do(1, p1)
    do(2, p2)
    do(3, p3)
    do(4, p4)
    do(5, p5)
    print('migration done', flush=True)


if __name__ == '__main__':
    main()
