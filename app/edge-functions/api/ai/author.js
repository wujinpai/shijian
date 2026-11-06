import { aiHandler, data } from '../../../lib/ai.js';
// GET /api/ai/author?a=作者&d=朝代 → { text }：作者简介（只接受站内有的作者）
export const onRequest = aiHandler(async (url, origin) => {
  const a = (url.searchParams.get('a') || '').trim(), d = (url.searchParams.get('d') || '').trim();
  if (!a || a.length > 30 || ['佚名', '无名氏', '不详'].includes(a)) return null;
  const list = await data(origin, '/data/authors.json');
  const hit = list.find((e) => e[0] === a && e[1] === d) || list.find((e) => e[0] === a); if (!hit) return null;
  return {
    system: '你是严谨的中国文学史学者。用简体中文、纯文本作答，不用 Markdown 符号。只写有把握的史实；生平不详就直说“生平资料较少”，绝不编造字号、籍贯、官职或作品。',
    user: `用 150 到 250 字介绍${hit[1]}代作者「${a}」：生卒年（不详可略）、字号籍贯、主要经历、文学成就与代表作。本站收录其作品 ${hit[2]} 篇。若同名者多或无可靠资料，请说明。`,
    max: 1500,
  };
}, '站内没有这位作者');
