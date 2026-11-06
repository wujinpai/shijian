import { handler, q, err, json, int } from '../../../lib/turso.js';
export const onRequest = handler(async (url) => {
  const p = url.searchParams, name = (p.get('q') || '').trim();
  if (!name) return err(400, 'bad_query', '请提供 q（作者名）');
  const size = int(p.get('size'), 20, 1, 50);
  const rows = await q(`SELECT id, name, dynasty, era, works FROM authors WHERE name >= ? AND name < ? ORDER BY works DESC LIMIT ${size}`, [name, name + '\u{10FFFF}']);
  return json({ query: name, data: rows });
});
