# 拆超大 p/ 分片（v43）：典籍长文分片（如 p/796.json 2.4MB）打开一篇要先下整个分片。
# 按字节切成每片 <= MAX_BYTES 的子分片 p/{k}-{sub}.json，边界记入 meta.json 的 psplit，
# 前端 poem() 按 psplit 查子分片。原分片删除。
# 用法：python3 tools/split_big_shards.py [--max-kb 600]  （在仓库根运行）
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'app', 'site')
DATA = os.path.join(SITE, 'data')
MAX_BYTES = int(sys.argv[sys.argv.index('--max-kb') + 1]) * 1024 if '--max-kb' in sys.argv else 600 * 1024


def dump(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def main():
    meta_path = os.path.join(DATA, 'meta.json')
    m = json.load(open(meta_path))
    psplit = m.get('psplit') or {}
    pdir = os.path.join(DATA, 'p')
    for f in sorted(os.listdir(pdir)):
        if not f.endswith('.json') or '-' in f[:-5]:
            continue
        k = int(f[:-5])
        path = os.path.join(pdir, f)
        if os.path.getsize(path) <= MAX_BYTES:
            continue
        rows = json.load(open(path))
        # 按字节切分：累计行，直到接近上限
        bounds, chunks, cur, cur_bytes = [0], [], [], 0
        for i, r in enumerate(rows):
            b = len(json.dumps(r, ensure_ascii=False).encode('utf-8')) if r else 4  # 字节数，非字符数
            if cur and cur_bytes + b > MAX_BYTES:
                chunks.append(cur)
                bounds.append(i)
                cur, cur_bytes = [], 0
            cur.append(r)
            cur_bytes += b
        if cur:
            chunks.append(cur)
        if len(chunks) < 2:
            continue
        for sub, ch in enumerate(chunks):
            dump(os.path.join(pdir, f'{k}-{sub}.json'), ch)
        os.remove(path)
        psplit[str(k)] = bounds
        sizes = [os.path.getsize(os.path.join(pdir, f'{k}-{s}.json')) // 1024 for s in range(len(chunks))]
        print(f'p/{k}.json {os.path.getsize(path) // 1024 if os.path.exists(path) else "?"}KB -> {len(chunks)} chunks {sizes}KB bounds={bounds}')
    m['psplit'] = psplit
    dump(meta_path, m)
    print('psplit:', psplit)


if __name__ == '__main__':
    main()
