// 按需 AI 释义 / 作者简介：用户点按钮才调用 Makers Models 内置模型。
// 结果按 URL 由站点节点缓存（shijian.jisu.cn 规则 60 天）+ 函数实例内存缓存，同一首诗/作者只生成一次。
// 密钥取项目环境变量 MAKERS_MODELS_KEY，代码里不放密钥。
const MODEL = '@makers/deepseek-v4-flash';
const CORS = { 'access-control-allow-origin': '*' };
const MEM = new Map();
const hits = new Map();
function limited(ip, max = 8, win = 60000) {
  const t = Date.now(); let h = hits.get(ip);
  if (!h || t > h.r) { h = { n: 0, r: t + win }; hits.set(ip, h); }
  if (hits.size > 5000) for (const [k, v] of hits) if (t > v.r) hits.delete(k);
  return ++h.n > max;
}
const ipOf = (req) => req.headers.get('eo-connecting-ip') || (req.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'x';
export const out = (obj, status = 200) => new Response(JSON.stringify(obj), { status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': status === 200 ? 'public, max-age=2592000' : 'no-store', ...CORS } });
const DATA = new Map();
export async function data(origin, path) {
  if (DATA.has(path)) return DATA.get(path);
  const p = fetch(origin + path).then((r) => { if (!r.ok) throw new Error('data ' + r.status); return r.json(); });
  DATA.set(path, p); p.catch(() => DATA.delete(path));
  if (DATA.size > 200) DATA.delete(DATA.keys().next().value);
  return p;
}
async function chat(env, system, user, maxTokens) {
  const key = env.MAKERS_MODELS_KEY; if (!key) throw new Error('model env missing');
  const base = (env.AI_GATEWAY_BASE_URL || 'https://ai-gateway.edgeone.link/v1').replace(/\/$/, '');
  const body = { model: MODEL, temperature: 0.3, max_tokens: maxTokens, thinking: { type: 'disabled' }, messages: [{ role: 'system', content: system }, { role: 'user', content: user }] };
  const go = (b) => fetch(base + '/chat/completions', { method: 'POST',
    headers: { authorization: 'Bearer ' + key, 'content-type': 'application/json' }, body: JSON.stringify(b) });
  let r = await go(body);
  if (r.status === 400) { delete body.thinking; r = await go(body); }  // 不支持关闭思考时退回
  if (!r.ok) throw new Error('model ' + r.status);
  const j = await r.json(); const t = (((j.choices || [])[0] || {}).message || {}).content || '';
  return t.replace(/\*\*|^#+\s*/gm, '').trim();
}
export function aiHandler(build, miss = '没有这一篇') {
  return async (ctx) => {
    const req = ctx.request, env = ctx.env || (globalThis.process && globalThis.process.env) || {};
    if (req.method !== 'GET') return out({ error: '只支持 GET' }, 405);
    const url = new URL(req.url); const key = url.pathname + url.search;
    if (MEM.has(key)) return out(MEM.get(key));
    if (limited(ipOf(req))) return out({ error: '请求太频繁，请稍后再试' }, 429);
    let job;
    try { job = await build(url, url.origin); } catch (e) { return out({ error: '数据读取失败' }, 502); }
    if (!job) return out({ error: miss }, 404);
    try {
      const text = await chat(env, job.system, job.user, job.max || 900);
      if (!text) return out({ error: '生成失败，请重试' }, 502);
      const o = { text, model: MODEL, ai: true }; MEM.set(key, o); if (MEM.size > 3000) MEM.delete(MEM.keys().next().value);
      return out(o);
    } catch (e) { return out({ error: '生成失败，请稍后重试' }, 502); }
  };
}
