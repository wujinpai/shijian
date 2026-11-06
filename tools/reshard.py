# 合并站点数据分片以减少文件数（Makers 项目文件数上限）：p 按 PS、s 按 CH 重新分组。
import json, os, sys, glob, shutil
D = sys.argv[1] if len(sys.argv) > 1 else 'app/site/data'
NPS, NCH = 500, 2000
M = json.load(open(f'{D}/meta.json'))
def regroup(sub, old, new):
    R = new // old; assert new % old == 0
    files = {int(os.path.basename(f)[:-5]): f for f in glob.glob(f'{D}/{sub}/*.json')}
    out = {}
    for k in sorted(files):
        K = k // R; base = (k - K * R) * old
        lst = out.setdefault(K, [])
        while len(lst) < base: lst.append(None)
        lst.extend(json.load(open(files[k])))
    tmp = f'{D}/{sub}.new'; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for K, lst in out.items():
        with open(f'{tmp}/{K}.json', 'w') as fh: json.dump(lst, fh, ensure_ascii=False, separators=(',', ':'))
    # 校验
    n = 0
    for k, f in files.items():
        a = json.load(open(f)); K = k // R; b = out[K]; base = (k - K * R) * old
        for i, v in enumerate(a): assert b[base + i] == v; n += 1
    shutil.rmtree(f'{D}/{sub}'); os.rename(tmp, f'{D}/{sub}')
    print(sub, len(files), '->', len(out), 'rows', n)
if M['PS'] != NPS: regroup('p', M['PS'], NPS); M['PS'] = NPS
if M['CH'] != NCH: regroup('s', M['CH'], NCH); M['CH'] = NCH
with open(f'{D}/meta.json', 'w') as fh: json.dump(M, fh, ensure_ascii=False, separators=(',', ':'))
