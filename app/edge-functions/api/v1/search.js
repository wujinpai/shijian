import { handler, q, work, err, json, ftsQuery, int, WORK_COLS } from '../../../lib/turso.js';
export const onRequest = handler(async (url) => {
  const p = url.searchParams, s = (p.get('q') || '').trim();
  const fq = ftsQuery(s);
  if (!fq) return err(400, 'bad_query', 'q 至少包含一个汉字');
  const page = int(p.get('page'), 1, 1, 100), size = int(p.get('size'), 20, 1, 50);
  const col = p.get('in') === 'title' ? 'title' : p.get('in') === 'content' ? 'body' : '';
  const match = col ? `{${col}} : (${fq})` : fq;
  const where = [], args = [match];
  for (const k of ['author', 'dynasty', 'era', 'kind']) if (p.get(k)) { where.push(`w.${k} = ?`); args.push(p.get(k)); }
  const filt = where.length ? ' AND ' + where.join(' AND ') : '';
  const rows = await q(`SELECT ${WORK_COLS.split(', ').map((c) => 'w.' + c).join(', ')} FROM works_fts f JOIN works w ON w.id = f.rowid
    WHERE works_fts MATCH ?${filt} ORDER BY f.rowid LIMIT ${size + 1} OFFSET ${(page - 1) * size}`, args);
  const more = rows.length > size;
  return json({ query: s, page, size, has_more: more, data: rows.slice(0, size).map((r) => work(r, false)) });
});
