# v35 校验：站点 corpus 与仓库逐条一致、无重复；抽查名篇
import json,sys,os,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); os.environ.setdefault('REPO_READ','/tmp/cc/chinese-classics')
from canon_lib import *
from repo_canon import gn
C=json.load(open(B+'/corpus.json'))
st=collections.Counter(nz(''.join(r['p'])) for r in C)
print('site recs',len(C),'exact-text dup extra',sum(v-1 for v in st.values() if v>1))
E=load_repo(cache=False); rt=collections.Counter(e[5] for e in E)
print('repo entries',len(E),'exact-text dup extra',sum(v-1 for v in rt.values() if v>1), 'short<4', sum(1 for e in E if len(e[5])<4))
sk=collections.Counter((gn(r['a']),nz(''.join(r['p']))) for r in C); rk=collections.Counter((gn(e[3]),e[5]) for e in E)
print('site keys not in repo', sum((sk-rk).values()), 'repo keys not in site', sum((rk-sk).values()))
for x in list((sk-rk).keys())[:5]: print(' S-R', x[0], x[1][:20])
for x in list((rk-sk).keys())[:5]: print(' R-S', x[0], x[1][:20])
for t in ['床前明月光','春眠不觉晓','折戟沉沙铁未销','寒雨连江夜入吴','名花倾国两相欢','红豆生南国','白日依山尽','大江东去','寻寻觅觅']:
    print(t, [(r['i'],r['c'],r['a'],r['t']) for r in C if t in ''.join(r['p'])[:40]][:3])
