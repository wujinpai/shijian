import tq, sqlite3, os
db = sqlite3.connect('/tmp/api.db')
db.execute('CREATE TABLE IF NOT EXISTS w(id INTEGER PRIMARY KEY, title, author, author_id, dynasty, famous, content)')
last = db.execute('select coalesce(max(id),-1) from w').fetchone()[0]
while True:
    rows = tq.q('select id,title,author,author_id,dynasty,famous,content from works where id>? order by id limit 8000', last)
    if not rows: break
    db.executemany('insert into w values (?,?,?,?,?,?,?)', [(int(r['id']), r['title'], r['author'], r['author_id'], r['dynasty'], r['famous'], r['content']) for r in rows]); db.commit()
    last = int(rows[-1]['id']); print(last, flush=True)
print('done', db.execute('select count(*) from w').fetchone())
