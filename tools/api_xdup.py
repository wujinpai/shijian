import sqlite3, re, json, collections, opencc
cc = opencc.OpenCC('t2s')
db = sqlite3.connect('/tmp/api.db')
N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
g = collections.defaultdict(list)
for i, t, a, c in db.execute('select id,title,author,content from w'):
    b = cc.convert(N.sub('', c or ''))
    if len(b) >= 10: g[b].append((i, t, a))
grp = [v for v in g.values() if len({x[2] for x in v}) > 1]
print('api groups', len(grp), 'extra', sum(len(v) - 1 for v in grp))
json.dump({k: v for k, v in g.items() if len({x[2] for x in v}) > 1}, open('/workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/shici/build/attrib/api_groups.json', 'w'), ensure_ascii=False)
