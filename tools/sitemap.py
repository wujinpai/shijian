# 生成 sitemap + robots.txt（v43）
# 从站点数据枚举真实 URL：诗页（data/s/ stubs 去空位）、作者页（data/authors.json）、
# 合集/选本/固定页（data/meta.json）。诗页每 5 万条一个分片。
# 用法：python3 tools/sitemap.py  （在仓库根运行；输出到 app/site/）
import json, os, sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'app', 'site')
DATA = os.path.join(SITE, 'data')
BASE = 'https://shijian.jisu.cn'
PER_FILE = 50000


def enc(s):
    # 与前端 encodeURIComponent 对齐：不转义 - _ . ! ~ * ' ( )
    return quote(s, safe="-_.!~*'()")


def grp(d):
    return '唐' if d in ('唐', '五代') else d


def main():
    m = json.load(open(os.path.join(DATA, 'meta.json')))
    built = m.get('built') or '2026-11-06'

    # --- 诗页 id：扫 data/s/ stubs，空位为 None ---
    ids = []
    for f in sorted(os.listdir(os.path.join(DATA, 's'))):
        if not f.endswith('.json'):
            continue
        k = int(f[:-5])
        arr = json.load(open(os.path.join(DATA, 's', f)))
        for i, row in enumerate(arr):
            if row:
                ids.append(k * m['CH'] + i)
    ids.sort()
    print('poems:', len(ids), 'max_id:', ids[-1] if ids else None)

    # --- 写诗页分片 ---
    shards = []
    for n in range(0, len(ids), PER_FILE):
        part = ids[n:n + PER_FILE]
        name = f'sitemap-poems-{n // PER_FILE + 1:03d}.xml'
        with open(os.path.join(SITE, name), 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for i in part:
                f.write(f'<url><loc>{BASE}/p/{i}</loc><lastmod>{built}</lastmod></url>\n')
            f.write('</urlset>\n')
        shards.append(name)
    print('poem shards:', len(shards))

    # --- 固定页 + 合集 + 选本 + 作者页 ---
    pages = [('/', 'daily', '1.0'), ('/c', 'weekly', '0.8'), ('/authors', 'weekly', '0.8'),
             ('/said', 'weekly', '0.7'), ('/about', 'monthly', '0.5'), ('/api', 'monthly', '0.7')]
    for c in m['colls']:
        pages.append((f"/c/{c['code']}", 'weekly', '0.7'))
    for l in m.get('lists', []):
        pages.append((f"/l/{l['code']}", 'monthly', '0.7'))
    authors = json.load(open(os.path.join(DATA, 'authors.json')))
    for e in authors:
        # e = [name, dynasty, count, ref]；URL 与前端 authorHref 一致
        pages.append((f"/a/{e[3]}/{enc(grp(e[1]) + '|' + e[0])}", 'monthly', '0.6'))
    with open(os.path.join(SITE, 'sitemap-pages.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for path, freq, pri in pages:
            f.write(f'<url><loc>{BASE}{path}</loc><changefreq>{freq}</changefreq><priority>{pri}</priority></url>\n')
        f.write('</urlset>\n')
    print('pages:', len(pages))

    # --- sitemap index ---
    with open(os.path.join(SITE, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for name in shards + ['sitemap-pages.xml']:
            f.write(f'<sitemap><loc>{BASE}/{name}</loc><lastmod>{built}</lastmod></sitemap>\n')
        f.write('</sitemapindex>\n')

    # --- robots.txt ---
    with open(os.path.join(SITE, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write('User-agent: *\nAllow: /\nDisallow: /s\nDisallow: /api/test\nDisallow: /api/v1/\n\n'
                f'Sitemap: {BASE}/sitemap.xml\n')
    print('done:', len(shards) + 1, 'sitemap files + robots.txt')


if __name__ == '__main__':
    main()
