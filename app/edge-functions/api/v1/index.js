import { json } from '../../../lib/turso.js';
// /api/v1 根：浏览器访问进入站内调试台（/api/test，单页路由），程序访问返回接口目录
export const onRequest = ({ request }) => {
  if ((request.headers.get('accept') || '').includes('text/html'))
    return new Response(null, { status: 302, headers: { location: '/api/test' } });
  return json({ name: '诗笺开放 API', version: 'v1', docs: 'https://shijian.jisu.cn/api', console: 'https://shijian.jisu.cn/api/test',
    endpoints: ['/api/v1/search?q=', '/api/v1/poems/{id}', '/api/v1/random', '/api/v1/authors?q=', '/api/v1/authors/{id}', '/api/v1/stats'] });
};
