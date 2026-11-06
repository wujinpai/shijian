import { json } from '../../../lib/turso.js';
// 未定义的接口：返回 JSON 404（浏览器访问显示本站 404 页）
export const onRequest = ({ request }) => {
  if ((request.headers.get('accept') || '').includes('text/html')) return new Response(null, { status: 302, headers: { location: '/404' } });
  return json({ error: { code: 'not_found', message: '没有这个接口，见 https://shijian.jisu.cn/api' } }, 404, 0);
};
