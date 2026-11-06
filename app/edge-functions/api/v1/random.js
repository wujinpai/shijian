import { handler, q, work, json, WORK_COLS } from '../../../lib/turso.js';
let MAX = 0;
export const onRequest = handler(async (url) => {
  const p = url.searchParams, where = [], args = [];
  for (const k of ['era', 'kind', 'dynasty']) if (p.get(k)) { where.push(`${k} = ?`); args.push(p.get(k)); }
  if (p.get('famous') === '1') where.push('famous = 1');
  if (!MAX) MAX = +(await q("SELECT v FROM meta WHERE k = 'max_id'"))[0].v;
  const filt = where.length ? ' AND ' + where.join(' AND ') : '';
  let [r] = await q(`SELECT ${WORK_COLS} FROM works WHERE id >= ?${filt} ORDER BY id LIMIT 1`, [1 + Math.floor(Math.random() * MAX), ...args]);
  if (!r) [r] = await q(`SELECT ${WORK_COLS} FROM works WHERE 1${filt} ORDER BY id LIMIT 1`, args);
  return json({ data: r ? work(r) : null }, 200, 0);
}, { cache: false });
