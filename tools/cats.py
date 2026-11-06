# 关于页「收录合集」：按 chinese-classics 仓库各目录统计篇数（作品数 + 典籍章节数），写入 app/site/data/meta.json 的 cats
# 仓库已与本站同步（tools/repo_sync.py），在 emit.py 之后运行；重跑 emit 必须再跑本脚本
import json, glob, os, collections
R = os.path.dirname(os.path.abspath(__file__)) + '/..'; REPO = os.environ.get('REPO_READ', R + '/../chinese-classics')
ORDER = ['先秦诗', '秦汉诗', '魏晋南北朝诗', '隋诗', '唐诗', '唐词', '五代诗', '五代词', '宋诗', '宋词', '辽金诗', '辽金词', '元诗', '元词', '元曲', '明诗', '明词', '清诗', '清词', '近代诗', '现代诗']
cnt = collections.Counter()
for f in glob.glob(REPO + '/*/*.json'):
    d = os.path.basename(os.path.dirname(f))
    if d in ('scripts', '名篇索引'): continue
    j = json.load(open(f, encoding='utf-8'))
    cnt[d] += len(j.get('works', [])) + len(j.get('chapters', []))
cats = [[c, cnt[c]] for c in ORDER if cnt[c]] + [[c, v] for c, v in sorted(cnt.items()) if c not in ORDER]
out = {'repo': 'chinese-classics', 'cats': cats, 'total': sum(cnt.values())}
p = R + '/app/site/data/meta.json'; m = json.load(open(p)); m['cats'] = out
json.dump(m, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(out, ensure_ascii=False))
