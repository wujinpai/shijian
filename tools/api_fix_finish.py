# api_fix apply 的后半段（异名归并 + 统计），按 author_id 走索引，可重复执行
import json, os
import tq
from paths import BUILD
P = json.load(open(os.path.join(BUILD, 'attrib', 'api_plan.json'))); AL = P['alias']
n = 0
for old, new in AL.items():
    o = tq.q('select id, dynasty from authors where name=?', old)
    if not o: continue
    t = tq.q('select id from authors where name=? order by works desc limit 1', new)
    if t: tid = int(t[0]['id'])
    else:
        tq.run([('UPDATE authors SET name=? WHERE id=?', [new, int(o[0]['id'])])]); tid = int(o[0]['id']); o = o[1:]
    for r in o:
        tq.run([('UPDATE works SET author=?, author_id=? WHERE author_id=?', [new, tid, int(r['id'])])])
    tq.run([('UPDATE works SET author=? WHERE author_id=?', [new, tid])]); n += 1
print('aliases applied', n, flush=True)
tq.run([('UPDATE authors SET works=(SELECT count(*) FROM works WHERE author_id=authors.id)', []),
        ('DELETE FROM authors WHERE works=0', []),
        ("UPDATE meta SET v=(SELECT count(*) FROM works) WHERE k='works'", []),
        ("UPDATE meta SET v=(SELECT count(*) FROM authors) WHERE k='authors'", []),
        ("UPDATE meta SET v=(SELECT json_group_array(json_object('era', era, 'kind', kind, 'n', n)) FROM (SELECT era, kind, count(*) n FROM works GROUP BY era, kind)) WHERE k='by_era'", [])])
print(tq.q('select k, substr(v,1,60) v from meta'))
