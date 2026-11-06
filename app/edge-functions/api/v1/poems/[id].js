import { handler, q, work, err, json, WORK_COLS } from '../../../../lib/turso.js';
export const onRequest = handler(async (url, ctx) => {
  const id = parseInt(ctx.params.id, 10);
  if (!(id > 0)) return err(400, 'bad_id', 'id 必须是正整数');
  const [r] = await q(`SELECT ${WORK_COLS} FROM works WHERE id = ?`, [id]);
  if (!r) {
    // 重复篇目合并后，旧 id 永久跳转到保留的那篇
    const [m] = await q('SELECT new_id FROM merged WHERE old_id = ?', [id]).catch(() => []);
    if (m) return new Response(null, { status: 301, headers: { Location: `/api/v1/poems/${m.new_id}`, 'Access-Control-Allow-Origin': '*' } });
    return err(404, 'not_found', '没有这篇作品');
  }
  return json({ data: work(r) });
});
