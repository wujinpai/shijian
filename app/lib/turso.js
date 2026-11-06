// 诗笺开放 API：运行在 Edge Functions，从 Turso（libSQL over HTTP，东京）读取 chinese-classics 数据。
// 连接信息取项目环境变量 TURSO_URL、TURSO_TOKEN（只读 token），代码里不放密钥。
let TURSO_URL = '', TURSO_TOKEN = '';
function useEnv(env) {
  const e = env || (globalThis.process && globalThis.process.env) || {};
  if (e.TURSO_URL) TURSO_URL = e.TURSO_URL;
  if (e.TURSO_TOKEN) TURSO_TOKEN = e.TURSO_TOKEN;
}

const hits = new Map();
function limited(key, max = 60, windowMs = 60000) {
  const t = Date.now(); let h = hits.get(key);
  if (!h || t > h.reset) { h = { n: 0, reset: t + windowMs }; hits.set(key, h); }
  h.n++;
  if (hits.size > 5000) for (const [k, v] of hits) if (t > v.reset) hits.delete(k);
  return h.n > max;
}
const ipOf = (req) => req.headers.get('eo-connecting-ip') || (req.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'x';
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET, OPTIONS', 'access-control-allow-headers': 'content-type' };
export function json(obj, status = 200, maxAge = 5184000) {
  return new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8',
    'cache-control': maxAge ? `public, max-age=${Math.min(maxAge, 3600)}` : 'no-store', ...CORS } });
}
const err = (status, code, message) => json({ error: { code, message } }, status, 0);

const arg = (v) => v === null || v === undefined ? { type: 'null' } : typeof v === 'number' && Number.isInteger(v) ? { type: 'integer', value: String(v) } : { type: 'text', value: String(v) };
export async function q(sql, args = []) {
  if (!TURSO_TOKEN) useEnv();
  if (!TURSO_URL || !TURSO_TOKEN) throw new Error('db env missing');
  const r = await fetch(`${TURSO_URL}/v2/pipeline`, { method: 'POST',
    headers: { authorization: `Bearer ${TURSO_TOKEN}`, 'content-type': 'application/json' },
    body: JSON.stringify({ requests: [{ type: 'execute', stmt: { sql, args: args.map(arg) } }, { type: 'close' }] }) });
  if (!r.ok) throw new Error('db ' + r.status);
  const res = (await r.json()).results[0];
  if (res.type !== 'ok') throw new Error('db ' + (res.error && res.error.message));
  const { cols, rows } = res.response.result;
  return rows.map((row) => Object.fromEntries(row.map((c, i) => [cols[i].name, c.type === 'null' ? null : c.type === 'integer' ? Number(c.value) : c.value])));
}

export const WORK_COLS = 'id, title, author_id, author, dynasty, era, kind, book, chapter, section, rhythmic, source, content';
export function work(r, full = true) {
  const o = { id: r.id, title: r.title, author: r.author, author_id: r.author_id, dynasty: r.dynasty, era: r.era, kind: r.kind };
  for (const k of ['book', 'chapter', 'section', 'rhythmic', 'source']) if (r[k]) o[k] = r[k];
  const lines = (r.content || '').split('\n');
  if (full) o.paragraphs = lines; else o.excerpt = lines[0].slice(0, 60);
  o.url = `https://shijian.jisu.cn/api/v1/poems/${r.id}`;
  return o;
}

// 搜索：中文按二字组建 FTS5 索引（与 tools/turso_build.py 的 grams() 一致），短语匹配即原文连续出现。
const CJK = /[\u3400-\u9fff\uf900-\ufaff\u{20000}-\u{3134f}]+/gu;
export function ftsQuery(s) {
  const segs = String(s || '').match(CJK) || [];
  const parts = [];
  for (const seg of segs) {
    const ch = [...seg];
    if (ch.length === 1) parts.push(`${ch[0]}*`);
    else parts.push('"' + ch.slice(0, -1).map((c, i) => c + ch[i + 1]).join(' ') + '"');
  }
  return parts.join(' AND ');
}

// 实例内存缓存：Makers 的 Edge Functions 禁止 Cache API 写 CDN 缓存（put 报 forbidden cdn cache），
// zip 直传时 edgeone.json 的 caches 也不生效，所以只能在函数实例内存里缓存，命中时不读 Turso。
const MEM = new Map(), MEM_MAX = 2000, MEM_BYTES = 8e6; let memBytes = 0;
function memGet(k) { const v = MEM.get(k); if (v) { MEM.delete(k); MEM.set(k, v); } return v; }
function memSet(k, v) {
  if (v.body.length > 200000) return;
  if (MEM.has(k)) { memBytes -= MEM.get(k).body.length; MEM.delete(k); }
  MEM.set(k, v); memBytes += v.body.length;
  while (MEM.size > MEM_MAX || memBytes > MEM_BYTES) { const [k0, v0] = MEM.entries().next().value; MEM.delete(k0); memBytes -= v0.body.length; }
}
const HDR = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=86400', ...CORS };
export function handler(fn, { cache = true } = {}) {
  return async (ctx) => {
    useEnv(ctx.env);
    const req = ctx.request;
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    if (req.method !== 'GET') return err(405, 'method_not_allowed', '只支持 GET');
    if (limited(ipOf(req))) return err(429, 'rate_limited', '请求过于频繁：每个 IP 每分钟 60 次');
    const url = new URL(req.url);
    const ps = []; url.searchParams.forEach((v, k) => ps.push(encodeURIComponent(k) + '=' + encodeURIComponent(v)));
    const key = url.pathname + '?' + ps.sort().join('&');
    if (cache) { const m = memGet(key); if (m) return new Response(m.body, { status: 200, headers: { ...HDR, 'x-api-cache': 'hit' } }); }
    let res;
    try { res = await fn(url, ctx); }
    catch (e) { return err(502, 'upstream_error', '数据服务暂时不可用'); }
    if (cache && res.status === 200) {
      const body = await res.text(); memSet(key, { body });
      return new Response(body, { status: 200, headers: { ...HDR, 'x-api-cache': 'miss' } });
    }
    return res;
  };
}
export { err };
const int = (v, d, lo, hi) => { const n = parseInt(v, 10); return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : d; };
export { int };
