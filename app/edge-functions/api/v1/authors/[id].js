import { handler, q, err, json, int } from '../../../../lib/turso.js';
export const onRequest = handler(async (url, ctx) => {
  const id = parseInt(ctx.params.id, 10);
  if (!(id > 0)) return err(400, 'bad_id', 'id 必须是正整数');
  const [a] = await q('SELECT id, name, dynasty, era, intro, works FROM authors WHERE id = ?', [id]);
  if (!a) return err(404, 'not_found', '没有这位作者');
  const page = int(url.searchParams.get('page'), 1, 1, 10000), size = int(url.searchParams.get('size'), 50, 1, 100);
  const list = await q(`SELECT id, title, kind FROM works WHERE author_id = ? ORDER BY id LIMIT ${size} OFFSET ${(page - 1) * size}`, [id]);
  return json({ data: { ...a, page, size, list } });
});
