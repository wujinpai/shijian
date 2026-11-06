# 仓库统一（2026-11-06，用户：仓库为唯一数据源；仓库/站点/API/关于页一致、不重复）
# 在 /tmp/cc/chinese-classics 上改（JuiceFS 太慢），改完 commit/push。
#   python3 repo_canon.py plan   → build/consist/repo_plan.json + 统计
#   python3 repo_canon.py apply  → 改写仓库文件
# 规则：
#  1. 正文为空或不足 4 个汉字的条目删除（站点同删）。
#  2. 站点每条配到仓库一条：正文全同 → 同作者近似（同长、差≤10%）→ 异作者近似 → 同作者同题兜底。
#  3. 作者名冲突：同人异写（异体字表 STDV、显式表 GX）先统一；其余默认按仓库（仓库已按 v34 规则判定），
#     例外：仓库名含 ?■□（ 或为截断、仓库名是 佚名/两汉乐府 而站点是具名作者、仓库名疑似误析（仓库 ≤8 篇且站点作者 ≥50 篇）、
#     站点名为仓库没有的同长一字异写（站点保留原字）→ 用站点名，作品移到该作者文件。
#  4. 去重：正文全同（不论作者）或同作者近似 → 一组只留一条。优先：典籍章节 > 有站点对应且作者一致 > 有站点对应 > 缺字少 > 先出现。
#  5. 站点有、仓库无的篇目补进仓库。
import json, os, re, sys, collections, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('REPO_READ', '/tmp/cc/chinese-classics')
from canon_lib import *
RW = os.environ['REPO_READ']
GEN = {'无名氏', '不详', '作者未详', '阙名', '佚名'}
GX = {'陶潜': '陶渊明', '金履详': '金履祥', '无名氏': '佚名', '不详': '佚名', '阙名': '佚名', '作者未详': '佚名', '初惟深': '方惟深'}
# v36 同人异名（tools/alias_merge.py 已在仓库归一）
GX.update({'刘向 撰': '刘向', '西晋·李密': '李密', '胡[证]': '胡证', '宋徽宗': '赵佶', '宋孝宗': '赵昚', '宋真宗': '赵恒', '宋度宗': '赵禥', '赵祺': '赵禥',
  '宋理宗': '赵昀', '宋光宗': '赵惇', '宋仁宗': '赵祯', '宋宁宗': '赵扩', '宋神宗': '赵顼', '玄宗皇帝李隆基': '李隆基', '南唐嗣主李璟': '李璟',
  '宋蒲寿宬': '蒲寿宬', '释仲殊': '仲殊', '章怀太子': '李贤', '释士圭': '释士珪', '释慧勤': '释慧懃', '叶廷圭': '叶廷珪',
  '刘骘': '刘隲', '钱协': '钱勰', '戴炳': '戴昺', '赵汝燧': '赵汝𬭼', '茜桃': '蒨桃', '杨崇': '杨崈', '王崇': '王崈', '王侃': '王偘', '何称': '何偁',
  '陈称': '陈偁', '蔡楠': '蔡柟', '吴汝一': '吴汝弌', '李鼗': '李鞉', '冷应澄': '冷应澂', '孙俟': '孙竢', '王晰': '王晳', '释知炳': '释知昺'})
STDV = dict(zip('隠浄頼玨嵒閴謩鼇箎僊瓌雝靁磵逈眘葊檝譡', '隐净赖珏岩阒谟鳌篪仙瑰雍雷涧迥昚庵楫谠'))
PFX = re.compile(r'^[^：:（(]{1,6}[：:]\s*')
def gn(n):
    n = PFX.sub('', (n or '').strip()).strip() or '佚名'
    return GX.get(n) or ''.join(STDV.get(c, c) for c in n)
BAD = re.compile(r'[?？■□{}\[\]（(]')
COLL_DIR = {'tang': '唐诗', 'songshi': '宋诗', 'songci': '宋词', 'mingshi': '明诗', 'qingshi': '清诗', 'yuanqu': '元曲', 'jinyuan': '元诗',
            'xiantang': '魏晋南北朝诗', 'jiuti': '近代诗', 'xinshi': '现代诗', 'huajian': '五代词', 'nantang': '五代词'}

def plan():
    E = load_repo(); print('E', len(E), flush=True)
    C = json.load(open(B + '/corpus.pre_canon.json' if os.path.exists(B + '/corpus.pre_canon.json') else B + '/corpus.json'))
    SR = [(r['i'], gn(s2(r['a'])), nz(''.join(r['p'])), r['t'], r['c']) for r in C]
    rcnt = collections.Counter(gn(e[3]) for e in E); scnt = collections.Counter(s[1] for s in SR)
    rnames = set(rcnt); snames = set(scnt)
    empty_e = [k for k, e in enumerate(E) if len(e[5]) < 4]
    empty_s = [s[0] for s in SR if len(s[2]) < 4]
    live = [k for k, e in enumerate(E) if len(e[5]) >= 4]
    ex = collections.defaultdict(list); ba = collections.defaultdict(list); bt2 = collections.defaultdict(list)
    for k in live: e = E[k]; ex[e[5]].append(k); ba[(gn(e[3]), len(e[5]))].append(k)
    # --- 站点配对
    pair = {}; left = []
    for s in SR:
        if len(s[2]) < 4: continue
        c = ex.get(s[2])
        if c: pair[s[0]] = sorted(c, key=lambda k: (gn(E[k][3]) != s[1], E[k][0] != 'c'))[0]; continue
        c = [k for k in ba.get((s[1], len(s[2])), []) if near(E[k][5], s[2])]
        if c: pair[s[0]] = sorted(c, key=lambda k: E[k][4] != s[3])[0]; continue
        left.append(s)
    L = set(len(s[2]) for s in left)
    bt = collections.defaultdict(list)
    for k in live:
        e = E[k]
        if len(e[5]) in L: bt[(len(e[5]), e[5][:4])].append(k); bt[(len(e[5]), e[5][-4:])].append(k)
    tk = collections.defaultdict(list)
    for k in live: tk[(gn(E[k][3]), re.sub(r'\s+', '', s2(E[k][4])))].append(k)
    left2 = []
    for s in left:
        t = s[2]; c = [k for k in set(bt.get((len(t), t[:4]), []) + bt.get((len(t), t[-4:]), [])) if near(E[k][5], t)]
        if c: pair[s[0]] = c[0]; continue
        c = tk.get((s[1], re.sub(r'\s+', '', s2(s[3]))))
        if c: pair[s[0]] = c[0]; continue
        left2.append(s)
    print('site paired', len(pair), 'unpaired', len(left2), 'empty site', len(empty_s), 'empty repo', len(empty_e), flush=True)
    S = {s[0]: s for s in SR}
    bye = collections.defaultdict(list)
    for i, k in pair.items(): bye[k].append(i)
    # --- 作者判定（每个仓库条目）
    PRI = {c: 0 for c in ('shijing', 'chuci', 'caocao', 'huajian', 'nantang', 'nalan', 'lunyu', 'sishu', 'dianji', 'guwen', 'youmeng')}
    PRI.update({'mengxue': 2, 'shuimo': 2})
    def decide(k):
        e = E[k]; ra = gn(e[3])
        if e[0] == 'c': return ra, None
        ss = bye.get(k)
        if not ss: return ra, None
        sas = [S[i][1] for i in ss]
        if ra in sas: return ra, None
        sa = sorted(ss, key=lambda i: PRI.get(S[i][4], 1))[0]; sa = S[sa][1]
        why = None
        if BAD.search(ra) and not BAD.search(sa): why = 'repo_bad'
        elif BAD.search(sa): why = None
        elif ra.startswith(sa) and len(sa) < len(ra): why = None  # 站点截断
        elif sa.startswith(ra) and len(ra) < len(sa): why = 'repo_trunc'
        elif ra in ('佚名', '两汉乐府', '郊庙朝会歌辞') and sa != '佚名': why = 'repo_generic'
        elif sa == '佚名': why = None
        elif rcnt[ra] <= 8 and scnt[sa] >= 50: why = 'repo_junk'
        elif len(sa) == len(ra) and sum(x != y for x, y in zip(sa, ra)) == 1 and sa not in rnames: why = 'site_variant'
        return (sa, why) if why else (ra, None)
    CA = {}; whyc = collections.Counter(); moves = []
    for k in live:
        a, why = decide(k); CA[k] = a
        if why: whyc[why] += 1
        if a != E[k][3] and E[k][0] == 'w': moves.append((k, a, why))
    print('author decisions', whyc, 'works whose file author changes', len(moves), flush=True)
    # --- 去重聚类
    par = {}
    def f(x):
        while par.get(x, x) != x: par[x] = par.get(par[x], par[x]); x = par[x]
        return x
    def u(a, b):
        a, b = f(a), f(b)
        if a != b: par[b] = a
    for t, ks in ex.items():
        for k in ks[1:]: u(ks[0], k)
    bca = collections.defaultdict(list)
    for k in live: bca[(CA[k], len(E[k][5]))].append(k)
    for ks in bca.values():
        if len(ks) < 2: continue
        for x in range(len(ks)):
            for y in range(x + 1, len(ks)):
                if len(E[ks[x]][5]) >= 10 and near(E[ks[x]][5], E[ks[y]][5]): u(ks[x], ks[y])
    # 站点两条配到不同仓库条目、但站点两条本身是同一首（异作者近似） → 也并
    grp = collections.defaultdict(list)
    for k in live: grp[f(k)].append(k)
    def bad(k): return len(re.findall(r'[?？□■]', E[k][5]))
    dele = list(empty_e); keepmap = {}; retitle = {}
    for g, ks in grp.items():
        if len(ks) < 2: continue
        bn = lambda k: os.path.basename(E[k][1])[:-5]
        chap = [k for k in ks if E[k][0] == 'c']
        if len(chap) > 1:  # 两部典籍都收（如 礼记·大学 与 大学）：留书名即篇名的那部
            chap.sort(key=lambda k: bn(k) != E[k][4])
        ks.sort(key=lambda k: (E[k][0] != 'c', not (E[k][0] == 'c' and bn(k) == E[k][4]),
                               bool(BAD.search(CA[k]) or '\ufffd' in CA[k] or len(CA[k]) < 2), CA[k] == '佚名',
                               not any(S[i][1] == CA[k] for i in bye.get(k, [])), not bye.get(k), bad(k), k))
        for k in ks[1:]: dele.append(k); keepmap[k] = ks[0]
        if E[ks[0]][0] == 'w':
            tt = [re.sub(r'\s+', ' ', E[k][4]).strip() for k in ks if CA[k] == CA[ks[0]] and E[k][0] == 'w']
            best = max(tt, key=lambda t: len(re.sub(r'\s', '', t)))
            if best != E[ks[0]][4]: retitle[ks[0]] = best
    # 合抄重复：一条正文恰为同作者另几条正文首尾相接（如「芙蓉楼送辛渐二首」整组与其一、其二分条并存）→ 删合抄那条
    ds0 = set(dele); bya = collections.defaultdict(list)
    for k in live:
        if k not in ds0: bya[CA[k]].append(k)
    ncomb = 0
    for a, ks in bya.items():
        if len(ks) < 3: continue
        tx = {}
        for k in ks: tx.setdefault(E[k][5], k)
        heads = collections.defaultdict(list)
        for t, k in tx.items(): heads[t[:6]].append(t)
        for t, k in tx.items():
            if len(t) < 30: continue
            def split(s, depth):
                if not s: return []
                for h in heads.get(s[:6], []):
                    if h != t and s.startswith(h):
                        r = split(s[len(h):], depth + 1)
                        if r is not None: return [h] + r
                return None
            parts = split(t, 0)
            core = re.sub(r'\s|杂曲歌辞|相和歌辞|郊庙歌辞|琴曲歌辞|舞曲歌辞|横吹曲辞|鼓吹曲辞|清商曲辞|近代曲辞|新乐府辞', '', E[k][4])[:4]
            if parts and len(parts) >= 2 and core and all(len(x) >= 20 and core in E[tx[x]][4] for x in parts):
                dele.append(k); keepmap[k] = tx[parts[0]]; ncomb += 1
    print('combined (整组合抄) deletions', ncomb)
    print('repo deletions', len(dele), '(empty', len(empty_e), ')', flush=True)
    # 站点无对应的仓库条目（去重后仍留）
    ds = set(dele)
    rnew = [k for k in live if k not in ds and not bye.get(k)]
    print('repo kept but not on site', len(rnew), collections.Counter(E[k][1].split('/')[0] for k in rnew).most_common(10))
    adds = [(s[0], s[1], s[3], s[4]) for s in left2]
    json.dump({'E_keys': [[e[0], e[1], e[2]] for e in E], 'dele': dele, 'keepmap': keepmap, 'moves': moves, 'adds': adds,
               'rnew': rnew, 'retitle': retitle, 'empty_s': empty_s, 'whyc': whyc}, open(B + '/consist/repo_plan.json', 'w'), ensure_ascii=False)
    import random; random.seed(5)
    for k, a, why in random.sample(moves, min(25, len(moves))): print('MV', E[k][1], E[k][4], '->', a, why)
    for k in rnew[:15]: print('RN', E[k][1], E[k][4], E[k][5][:16])
    for s in left2[:20]: print('ADD', s[0], s[1], s[3], s[4], s[2][:16])

def apply():
    Pn = json.load(open(B + '/consist/repo_plan.json'))
    EK = Pn['E_keys']; dele = set(Pn['dele'])
    C = {r['i']: r for r in json.load(open(B + '/corpus.pre_canon.json' if os.path.exists(B + '/corpus.pre_canon.json') else B + '/corpus.json'))}
    files = {}
    def J(rp):
        if rp not in files:
            p = f'{RW}/{rp}'
            files[rp] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
        return files[rp]
    # 作者文件索引：(目录, 作者) → rp
    afile = {}
    for f in sorted(glob.glob(RW + '/*/*.json')):
        d = os.path.basename(os.path.dirname(f))
        if d in SKIP: continue
        try: j = json.load(open(f, encoding='utf-8'))
        except Exception: continue
        if isinstance(j, dict) and 'works' in j: afile.setdefault((d, gn(s2(j.get('author') or ''))), f[len(RW) + 1:])
    moved_out = collections.defaultdict(list)  # (rp, idx) 待删
    adds_to = collections.defaultdict(list)
    def target(d, a, dyn):
        rp = afile.get((d, a))
        if rp: return rp
        rp = f'{d}/{a}.json'; n = 2
        while os.path.exists(f'{RW}/{rp}') and gn(s2(json.load(open(f'{RW}/{rp}')).get('author') or '')) != a: rp = f'{d}/{a}{n}.json'; n += 1
        afile[(d, a)] = rp
        if J(rp) is None: files[rp] = {'dynasty': dyn, 'author': a, 'works': []}
        return rp
    # 典籍作者清理：「先秦：左丘明 」→ 左丘明；诗经作者统一为 佚名；文字蒙求作者字段原为小传
    j = J('清诗/古文观止.json')
    for c in j['chapters']:
        if c.get('author'): c['author'] = gn(c['author'])
    J('先秦诗/诗经.json')['author'] = '佚名'
    j = J('唐诗/文字蒙求.json')
    if len(j.get('author', '')) > 10: j['author_desc'] = j['author']; j['author'] = '王筠'; j['dynasty'] = '清'
    for k, t in Pn.get('retitle', {}).items():
        kind, rp, idx = EK[int(k)]; J(rp)['works'][idx]['title'] = t
    for k, v in Pn['keepmap'].items():
        kind, rp, idx = EK[int(k)]; kk, rp2, idx2 = EK[v]
        if kind == 'w' and kk == 'w':
            a1 = J(rp)['works'][idx].get('annotations'); w2 = J(rp2)['works'][idx2]
            if a1 and not w2.get('annotations'): w2['annotations'] = a1
            for f in ('rhythmic', 'chapter', 'section'):
                if J(rp)['works'][idx].get(f) and not w2.get(f): w2[f] = J(rp)['works'][idx][f]
    for k, a, why in Pn['moves']:
        if k in dele: continue
        kind, rp, idx = EK[k]; j = J(rp); d = rp.split('/')[0]
        w = j['works'][idx]
        adds_to[target(d, a, j.get('dynasty'))].append(w); moved_out[rp].append(idx)
    for k in dele:
        kind, rp, idx = EK[k]
        if kind == 'w': moved_out[rp].append(idx)
        else: moved_out[rp].append(('c', idx))
    for i, a, t, c in Pn['adds']:
        r = C[i]; d = COLL_DIR.get(c)
        if r['g'] == '词' or c == 'songci': d = {'宋诗': '宋词', '明诗': '明词', '清诗': '清词', '唐诗': '唐词'}.get(d, d)
        if not d: print('ADD skip', i, c); continue
        w = {'title': r['t'], 'paragraphs': r['p']}
        adds_to[target(d, a, r.get('d') or '')].append(w)
    for rp, idxs in moved_out.items():
        j = J(rp); wi = {x for x in idxs if isinstance(x, int)}; ci = {x[1] for x in idxs if isinstance(x, tuple)}
        if wi: j['works'] = [w for n, w in enumerate(j['works']) if n not in wi]
        if ci: j['chapters'] = [c for n, c in enumerate(j['chapters']) if n not in ci]
    for rp, ws in adds_to.items(): J(rp)['works'].extend(ws)
    nd = nw = 0
    for rp, j in files.items():
        p = f'{RW}/{rp}'
        if j is None: continue
        if not j.get('works') and not j.get('chapters'):
            if os.path.exists(p): os.remove(p); nd += 1
            continue
        if 'works' in j and not j['works'] and 'chapters' not in j: continue
        if 'chapters' in j and not j['chapters']: j.pop('chapters')
        if 'works' in j and not j['works'] and 'chapters' in j: j.pop('works')
        json.dump(j, open(p, 'w', encoding='utf-8'), ensure_ascii=False); nw += 1
    print('files written', nw, 'deleted', nd)

def addsite():
    # canon.py 报出的站点独有记录（unpaired.json）补进仓库对应作者文件
    U = json.load(open(B + '/consist/unpaired.json')); C = {r['i']: r for r in json.load(open(B + '/corpus.pre_canon.json'))}
    for i, c, a, t, _ in U:
        r = C[i]; d = COLL_DIR.get(c)
        if r['g'] == '词' or c == 'songci': d = {'宋诗': '宋词', '明诗': '明词', '清诗': '清词', '唐诗': '唐词'}.get(d, d)
        a = gn(s2(a)); hit = None
        for f in glob.glob(f'{RW}/{d}/*.json'):
            j = json.load(open(f, encoding='utf-8'))
            if isinstance(j, dict) and gn(s2(j.get('author') or '')) == a and 'works' in j: hit = f; break
        if not hit:
            hit = f'{RW}/{d}/{a}.json'; j = {'dynasty': r.get('d') or '', 'author': a, 'works': []}
        j['works'].append({'title': r['t'], 'paragraphs': r['p']})
        json.dump(j, open(hit, 'w', encoding='utf-8'), ensure_ascii=False); print('added', hit, r['t'])

def textfix():
    if not os.path.exists(B + '/consist/textfix.json'): print('no textfix'); return
    T = json.load(open(B + '/consist/textfix.json')); n = 0
    files = {}
    for kind, rp, idx, paras in T:
        if rp not in files: files[rp] = json.load(open(f'{RW}/{rp}', encoding='utf-8'))
        lst = files[rp]['works' if kind == 'w' else 'chapters']; lst[idx]['paragraphs'] = paras; n += 1
    for rp, j in files.items(): json.dump(j, open(f'{RW}/{rp}', 'w', encoding='utf-8'), ensure_ascii=False)
    print('textfix', n, 'files', len(files))

if __name__ == '__main__':
    {'plan': plan, 'apply': apply, 'textfix': textfix, 'addsite': addsite}[sys.argv[1]]()
