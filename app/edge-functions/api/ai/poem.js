import { aiHandler, data } from '../../../lib/ai.js';
// GET /api/ai/poem?id=站点篇目 id → { text }：白话释义与简析
export const onRequest = aiHandler(async (url, origin) => {
  const id = parseInt(url.searchParams.get('id'), 10); if (!(id >= 0)) return null;
  const m = await data(origin, '/data/meta.json'); const k = Math.floor(id / m.PS);
  const r = (await data(origin, `/data/p/${k}.json`))[id - k * m.PS]; if (!r) return null;
  const [t, a, g, p, x, , dyn] = r; const body = (p || []).join('\n').slice(0, 2500);
  return {
    system: '你是严谨的中国古典文学老师。用简体中文、纯文本作答，不用 Markdown 符号。只依据原文讲解，不确定的典故、背景要说明“一说”或“待考”，不要编造。',
    user: `为下面这篇作品写讲解，分两段，第一段以“释义：”开头，用白话逐句讲清大意（长篇可概括）；第二段以“赏析：”开头，150 字以内点出主旨与艺术特色。\n\n《${t}》〔${dyn || ''}〕${a}${g && g !== t ? `（${g}）` : ''}${x && x.s ? `\n篇章：${x.s}` : ''}\n${body}`,
    max: 1800,
  };
});
