import { handler, q, json } from '../../../lib/turso.js';
// 统计在建库时预先算好存进 meta（by_era），避免每次 GROUP BY 全表扫描 88 万行
export const onRequest = handler(async () => {
  const meta = Object.fromEntries((await q('SELECT k, v FROM meta')).map((r) => [r.k, r.v]));
  return json({ data: { works: +meta.works, authors: +meta.authors, source: meta.source, by_era: JSON.parse(meta.by_era || '[]') } }, 200);
});
