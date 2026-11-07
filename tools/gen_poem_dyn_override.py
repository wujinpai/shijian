#!/usr/bin/env python3
"""生成 tools/poem_dyn_override.json：v45 逐首朝代修正的耐久覆盖表。
来源：build/consist/v45-unify-plan2.json 的 final corrections（1,972 首，已用全文配对验证与站点一致）。
键：(gn(作者), 标题, sha1(nz(全文))[:16]) —— 全文哈希可区分同题同首句的不同诗；
nz 为自包含实现（去非汉字 + 异体归一，不依赖 opencc），与 poem_dyn_override.py 同函数。
条目：a=gn 作者，t=标题，h=全文哈希，f=正文前 16 汉字（可读性），d=目标朝代，
e=目标 era（仅当修正同时改 era 时才有），id=Turso works id，old=原朝代。
陈毅 11 首不在仓库中（api_sync 的 gone 风险，见 HISTORY.md v45），条目永不命中，仅作记录。
"""
import json, os, sys, hashlib, subprocess, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dyn_norm import gn
from poem_dyn_override import nz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONS = os.path.join(ROOT, 'build', 'consist')
TURSO = '/home/hatch/workspace/custom-connectors/custom.turso/bin/turso.py'

def tq(sql):
    out = subprocess.run(['python3', TURSO, 'query', '--org', 'jisu', '--db', 'shijian-v2',
                          '--sql', sql], capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stdout + out.stderr)
    d = json.loads(out.stdout)
    return [dict(zip(d['cols'], r)) for r in d['rows']]

def main():
    plan = json.load(open(os.path.join(CONS, 'v45-unify-plan2.json')))
    corr = plan['corrections']
    print('corrections:', len(corr))
    ids = sorted({c['id'] for c in corr})
    by_id = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        for r in tq("SELECT id, author, title, content FROM works WHERE id IN (%s)" % ','.join(map(str, chunk))):
            by_id[r['id']] = r
    print('fetched contents:', len(by_id))
    missing = [i for i in ids if i not in by_id]
    assert not missing, missing
    entries = []
    seen = {}
    for c in corr:
        r = by_id[c['id']]
        assert r['author'] == c['author'] and r['title'] == c['title'], (c, r)
        text = nz(r['content'] or '')
        h = hashlib.sha1(text.encode()).hexdigest()[:16]
        key = (gn(c['author']), c['title'], h)
        e = {'a': key[0], 't': key[1], 'h': h, 'f': text[:16], 'd': c['new_dynasty'],
             'id': c['id'], 'old': c['old_dynasty']}
        if c['new_era'] != c['old_era']:
            e['e'] = c['new_era']
        if key in seen:
            assert seen[key]['d'] == e['d'], ('key collision with different target', key, seen[key], e)
            continue  # 同诗重复条目（不应出现）去重
        seen[key] = e
        entries.append(e)
    entries.sort(key=lambda e: (e['a'], e['t'], e['h']))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'poem_dyn_override.json')
    json.dump(entries, open(out, 'w'), ensure_ascii=False, indent=0)
    print('entries:', len(entries), '->', out)
    print('with era change:', sum(1 for e in entries if 'e' in e))
    print('authors:', len({e['a'] for e in entries}))

if __name__ == '__main__':
    main()
