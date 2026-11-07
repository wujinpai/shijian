# 版本号集中应用（v43）：读 tools/version.json，写回各文件。
# 用法：python3 tools/bump.py          # 按 version.json 应用（幂等）
#       python3 tools/bump.py --inc     # 全部 +1 后应用（发新版时用）
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'app', 'site')
VPATH = os.path.join(ROOT, 'tools', 'version.json')


def rep(path, pairs):
    s = open(path, encoding='utf-8').read()
    for pat, new in pairs:
        s2, n = re.subn(pat, new, s)
        assert n == 1, f'{path}: {pat} matched {n} times'
        s = s2
    open(path, 'w', encoding='utf-8').write(s)


def main():
    v = json.load(open(VPATH))
    if '--inc' in sys.argv:
        for k in ('dv', 'shell', 'data', 'appjs', 'appcss'):
            v[k] += 1
        json.dump(v, open(VPATH, 'w'), ensure_ascii=False, indent=1)
        print('bumped:', {k: v[k] for k in ('dv', 'shell', 'data', 'appjs', 'appcss')})
    rep(os.path.join(SITE, 'app.js'), [
        (r"const DV = 'v=\d+'", f"const DV = 'v={v['dv']}'"),
    ])
    rep(os.path.join(SITE, 'sw.js'), [
        (r"shici-shell-v\d+", f"shici-shell-v{v['shell']}"),
        (r"shici-data-v\d+", f"shici-data-v{v['data']}"),
        (r"/app\.js\?v=\d+", f"/app.js?v={v['appjs']}"),
        (r"/app\.css\?v=\d+", f"/app.css?v={v['appcss']}"),
    ])
    rep(os.path.join(SITE, 'index.html'), [
        (r"/app\.js\?v=\d+", f"/app.js?v={v['appjs']}"),
        (r"/app\.css\?v=\d+", f"/app.css?v={v['appcss']}"),
        (r"/data/meta\.json\?v=\d+", f"/data/meta.json?v={v['dv']}"),
    ])
    print('applied:', v)


if __name__ == '__main__':
    main()
