#!/usr/bin/env python3
"""为缺简介的作者从中文维基百科（CC BY-SA 4.0）取导言作简介，Wikidata（CC0）辅助校验。
不使用其它来源，不调用任何 AI 模型。可续跑：所有 API 响应缓存到 build/wiki_cache.json。

用法：
  python3 tools/wiki_bios.py fetch [秒数上限]   # 抓取（按作品数从多到少），可多次续跑
  python3 tools/wiki_bios.py build              # 由缓存生成 build/wiki_bios.json + 统计
  python3 tools/wiki_bios.py apply              # 写入 site/data（只补原本无 b 的作者）
"""
import json, os, re, sys, time, urllib.parse, urllib.request, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = ROOT + '/app/site'
CACHE = ROOT + '/build/wiki_cache.json'
OUT = ROOT + '/build/wiki_bios.json'
STATS = ROOT + '/build/wiki_bios_stats.json'
UA = 'shijian-bot/1.0 (https://shijian.jisu.cn)'
WP = 'https://zh.wikipedia.org/w/api.php'
WD = 'https://www.wikidata.org/w/api.php'

try:
    import opencc
    CC = opencc.OpenCC('t2s')
    t2s = CC.convert
except Exception:  # pragma: no cover
    t2s = lambda s: s

grp = lambda d: '唐' if d in ('唐', '五代') else d

# ---------------- 缓存 ----------------
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {'q': {}, 'links': {}, 'wd': {}, 'done': []}
for k in ('q', 'links', 'wd', 'done'):
    cache.setdefault(k, [] if k == 'done' else {})
_last = [0.0]


def save():
    tmp = CACHE + '.tmp'
    json.dump(cache, open(tmp, 'w'), ensure_ascii=False)
    os.replace(tmp, CACHE)


def get(url, params):
    for attempt in range(5):
        dt = time.time() - _last[0]
        if dt < 0.34:
            time.sleep(0.34 - dt)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url + '?' + urllib.parse.urlencode(params), headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            time.sleep(2 + attempt * 3)
    raise RuntimeError('request failed: ' + url)


def wp_query(titles):
    """查询一批标题（≤20），把每个原始标题映射到页面信息，存 cache['q'][title]。"""
    titles = [t for t in titles if t not in cache['q']]
    if not titles:
        return
    d = get(WP, {'action': 'query', 'format': 'json', 'formatversion': 2, 'prop': 'extracts|pageprops|info',
                 'exintro': 1, 'explaintext': 1, 'exlimit': 20, 'redirects': 1, 'converttitles': 1,
                 'variant': 'zh-cn', 'titles': '|'.join(titles)})
    q = d.get('query', {})
    m = {t: t for t in titles}
    for key in ('normalized', 'converted', 'redirects'):
        for r in q.get(key, []):
            for t, cur in m.items():
                if cur == r['from']:
                    m[t] = r['to']
    pages = {p['title']: p for p in q.get('pages', [])}
    for t in titles:
        p = pages.get(m[t])
        if not p or p.get('missing') or p.get('invalid'):
            cache['q'][t] = None
        else:
            pp = p.get('pageprops', {})
            cache['q'][t] = {'title': p['title'], 'x': p.get('extract', ''), 'dis': 'disambiguation' in pp,
                             'qid': pp.get('wikibase_item'), 'redir': m[t] != t}


def wp_links(title):
    if title in cache['links']:
        return cache['links'][title]
    out, cont = [], {}
    while True:
        d = get(WP, {'action': 'query', 'format': 'json', 'formatversion': 2, 'prop': 'links', 'plnamespace': 0,
                     'pllimit': 'max', 'titles': title, 'variant': 'zh-cn', **cont})
        for p in d.get('query', {}).get('pages', []):
            out += [l['title'] for l in p.get('links', [])]
        if 'continue' in d:
            cont = d['continue']
        else:
            break
    cache['links'][title] = out
    return out


def wd_fetch(qids):
    qids = [q for q in dict.fromkeys(qids) if q and q not in cache['wd']]
    for i in range(0, len(qids), 50):
        b = qids[i:i + 50]
        d = get(WD, {'action': 'wbgetentities', 'format': 'json', 'ids': '|'.join(b), 'props': 'claims'})
        for q in b:
            e = d.get('entities', {}).get(q, {})
            c = e.get('claims', {})

            def vals(p):
                r = []
                for s in c.get(p, []):
                    v = s.get('mainsnak', {}).get('datavalue', {}).get('value')
                    if v is not None:
                        r.append(v)
                return r

            def yr(p):
                for v in vals(p):
                    if isinstance(v, dict) and 'time' in v:
                        m = re.match(r'([+-])0*(\d+)-', v['time'])
                        if m:
                            y = int(m.group(2))
                            return -y if m.group(1) == '-' else y
                return None

            cache['wd'][q] = {'p31': [v.get('id') for v in vals('P31') if isinstance(v, dict)],
                              'b': yr('P569'), 'd': yr('P570')}


# ---------------- 校验规则 ----------------
ERA = {
    '唐': r'唐(朝|代|末|初|人|国|·|中叶|玄宗|肃宗|代宗|德宗|宪宗|穆宗|文宗|武宗|宣宗|懿宗|僖宗|昭宗|太宗|高宗)|[盛中晚初南]唐|武周|贞观|开元|天宝|大历|贞元|元和|长庆|宝历|大和|开成|会昌|大中|咸通|乾符|广明|中和|光启|天复|天祐',
    '五代': r'五代|十国|后[梁唐晋汉周]|南唐|前蜀|后蜀|吴越|南汉|闽国|唐(末|朝)',
    '宋': r'宋(朝|代|末|初|人|·)|[北南]宋|建隆|太平兴国|咸平|景德|天圣|景祐|庆历|皇祐|嘉祐|治平|熙宁|元丰|元祐|绍圣|元符|崇宁|大观|政和|宣和|建炎|绍兴|隆兴|乾道|淳熙|绍熙|庆元|嘉泰|开禧|嘉定|宝庆|绍定|端平|嘉熙|淳祐|宝祐|开庆|景定|咸淳|德祐',
    '辽': r'辽(朝|代|国)|契丹',
    '金': r'金(朝|代|国|末|初|人|·|、元|元)|金[太熙海世章卫宣哀]宗|天会|天眷|皇统|天德|贞元|正隆|大定|明昌|承安|泰和|大安|崇庆|贞祐|兴定|元光|正大|天兴',
    '元': r'元(朝|代|末|初|人|·)|蒙古|大元|宋末元初|中统|至元|元贞|大德|至大|皇庆|延祐|至治|泰定|致和|天历|至顺|元统|至正',
    '明': r'明(朝|代|末|初|中叶|中期|季|人|·|太祖|成祖|仁宗|宣宗|英宗|代宗|景帝|宪宗|孝宗|武宗|世宗|穆宗|神宗|光宗|熹宗|思宗)|南明|晚明|大明|明清|洪武|建文|永乐|洪熙|宣德|正统|景泰|天顺|成化|弘治|正德|嘉靖|隆庆|万历|泰昌|天启|崇祯|弘光|隆武|永历',
    '清': r'清(朝|代|末|初|中叶|中期|季|人|·|太宗|世祖|圣祖|世宗|高宗|仁宗|宣宗|文宗|穆宗|德宗)|晚清|前清|大清|明末清初|满洲|[满汉]军|旗人|顺治|康熙|雍正|乾隆|嘉庆|道光|咸丰|同治|光绪|宣统',
    '近现代': r'民国|中华人民共和国|近代|现代|当代|清末|晚清|光绪|宣统|辛亥|同盟会|南社|新文化',
    '南北朝': r'南北朝|南朝|北朝|刘宋|南齐|萧齐|南梁|萧梁|南陈|北魏|东魏|西魏|北齐|北周|[宋齐梁陈](朝|代)|[宋齐梁陈][武文明孝废少前后简元宣]帝|元魏|拓跋|太和|永明|天监|普通|大同|太清|天嘉|太建',
    '魏晋': r'魏晋|曹魏|三国|[西东]晋|晋(朝|代|人|国|·|[武惠怀愍元明成康穆哀简安恭]帝|简文帝|孝武帝)|魏(国|朝|·)|蜀汉|东吴|孙吴|十六国|前秦|后秦|前燕|后燕|南燕|前凉|后凉|北凉|西凉|东汉末|汉末|建安|正始|太康|永嘉|咸和|太元|义熙',
    '汉': r'汉(朝|代|末|初|·)|[西东前后]汉|新朝|王莽|汉[高惠文景武昭宣元成哀平光明章和殇安顺冲质桓灵献]帝',
    '隋': r'隋(朝|代|末|初|·)|隋[文炀恭]帝|开皇|仁寿|大业|北周|南陈|陈朝',
    '先秦': r'先秦|春秋|战国|[西东]?周(朝|代)|西周|东周|商朝|殷商|夏朝|[楚鲁齐晋秦燕赵韩魏宋卫郑吴越]国',
}
ERA['隋末唐初'] = ERA['隋'] + '|' + ERA['唐']
CORE = {'先秦': (-1100, -221), '汉': (-206, 220), '魏晋': (190, 420), '南北朝': (420, 589), '隋': (581, 618),
        '隋末唐初': (581, 650), '唐': (618, 907), '五代': (907, 979), '宋': (960, 1279), '辽': (907, 1125),
        '金': (1115, 1234), '元': (1234, 1368), '明': (1368, 1644), '清': (1644, 1912), '近现代': (1912, 2030)}
YR = {'先秦': (-2000, -200), '汉': (-230, 240), '魏晋': (160, 430), '南北朝': (380, 600), '隋': (540, 640),
      '隋末唐初': (540, 680), '唐': (590, 920), '五代': (860, 990), '宋': (940, 1300), '辽': (890, 1135),
      '金': (1090, 1250), '元': (1190, 1380), '明': (1320, 1664), '清': (1590, 1935), '近现代': (1830, 2030)}
PERSON = re.compile(r'诗人|词人|文人|文学家|作家|散文家|戏曲|剧作家|曲家|书法家|画家|篆刻|学者|经学家|史学家|理学家|思想家|哲学家|'
                    r'官员|政治人物|政治家|大臣|宰相|丞相|将领|将军|进士|举人|秀才|贡生|诸生|状元|翰林|尚书|侍郎|御史|太守|刺史|知府|知县|知州|'
                    r'僧|禅师|和尚|法师|道士|女冠|隐士|名士|布衣|遗民|藏书家|校勘|医家|医学家|皇帝|皇后|宗室|王爷|藩王|亲王|公主|妃|'
                    r'教育家|革命家|翻译家|外交官|元曲|杂剧|散曲|字[^，。]{1,6}[，。]|号[^，。]{1,6}[，。]|人物|[^\s，。、]{2,12}人[，。]')
LIT = re.compile(r'诗|词|文学|文人|作家|著有|著作|集》|曲|画家|书法|学者|僧|禅|隐士')
NONPERSON = re.compile(r'^[^。]{0,40}?(是|为)(一部|一种|一个|一座|一首|一本|中国的一个|位于)')
EXCL = re.compile(r'足球|篮球|运动员|演员|歌手|艺人|主持人|模特|偶像|电视剧|电影|游戏|动画|乐队|企业家|商人|球员|棒球|网球|排球|游泳|田径|选手')


def life_years(head):
    m = re.match(r'[^（(]{0,12}[（(]([^）)]{0,60})[）)]', head)
    if not m:
        return None, None
    parts = re.split(r'[—－–~～]|-(?=\D|$)|至', m.group(1), maxsplit=1)
    def y(t):
        mm = re.search(r'(前)?(\d{1,4})年', t) or re.search(r'(前)?(\d{3,4})', t)
        if not mm or '？' in t[:mm.start()] :
            return None
        v = int(mm.group(2))
        return -v if mm.group(1) else v
    if len(parts) < 2:
        return y(parts[0]), None
    return y(parts[0]), y(parts[1])


def years_ok(dyn, head, qid):
    b, d = life_years(head)
    w = cache['wd'].get(qid) if qid else None
    if w:
        b = b if b is not None else w['b']
        d = d if d is not None else w['d']
    if b is None or d is None or d < b:
        return False
    lo, hi = CORE.get(dyn, (-3000, 3000))
    return min(d, hi) - max(b, lo) >= 0


def era_ok(dyn, text):
    return re.search(ERA.get(dyn, re.escape(dyn)), text) is not None


def wd_ok(dyn, qid):
    """返回 (ok, reason)。无 Wikidata 信息时视为通过（由正文规则把关）。"""
    w = cache['wd'].get(qid) if qid else None
    if not w:
        return True, ''
    if w['p31'] and 'Q5' not in w['p31']:
        return False, 'wikidata非人物'
    lo, hi = YR.get(dyn, (-3000, 3000))
    b, d = w['b'], w['d']
    if b is not None and b > hi:
        return False, 'wikidata生卒年不符'
    if d is not None and d < lo:
        return False, 'wikidata生卒年不符'
    if b is not None and d is None and dyn != '近现代' and b < lo - 80:
        return False, 'wikidata生卒年不符'
    return True, ''


def judge(name, dyn, info):
    """info 为 cache['q'] 中的页面。返回 (ok, reason)。"""
    if info is None:
        return False, '无条目'
    if info['dis']:
        return False, '消歧义'
    x = t2s(info['x'] or '')
    head = x[:400]
    if len(x) < 15:
        return False, '导言过短'
    tt = t2s(re.sub(r'\s*[（(].*$', '', info['title']))
    if name not in tt and name not in head:
        alias = (tt[0] == name[0] and name[1:] in head)  # 名之淳 / 原名家达
        variant = len(tt) == len(name) and sum(a != b for a, b in zip(tt, name)) == 1 and info.get('redir')  # 异体字重定向
        shi = name.startswith('释') and tt == name[1:]
        if not (alias or variant or shi):
            return False, '重定向至他名'
    if NONPERSON.search(head):
        return False, '非人物'
    by, _ = life_years(head)
    if EXCL.search(head[:120]) and not (by is not None and by < 1880):
        return False, '同名现代人物'
    if not PERSON.search(head):
        return False, '不像传记'
    if not era_ok(dyn, head) and not years_ok(dyn, head, info.get('qid')):
        return False, '朝代不符'
    if dyn == '近现代' and not LIT.search(head):
        return False, '不像传记'  # 近现代同名者多，要求导言有文学/学术迹象
    ok, r = wd_ok(dyn, info.get('qid'))
    if not ok:
        return False, r
    return True, ''


DYNWORDS = {'唐': ['唐朝', '唐代', '唐'], '五代': ['五代', '五代十国', '南唐', '后蜀'], '宋': ['宋朝', '宋代', '北宋', '南宋', '宋'],
            '辽': ['辽朝', '辽'], '金': ['金朝', '金'], '元': ['元朝', '元代', '元'], '明': ['明朝', '明代', '明'],
            '清': ['清朝', '清代', '清'], '近现代': ['诗人', '作家', '民国', '学者'], '南北朝': ['南朝', '北朝', '南北朝', '北魏', '梁朝', '南朝梁', '南朝陈', '南朝宋', '南朝齐', '北齐', '北周'],
            '魏晋': ['晋朝', '东晋', '西晋', '三国', '曹魏'], '汉': ['汉朝', '西汉', '东汉'], '隋': ['隋朝', '隋'],
            '隋末唐初': ['隋朝', '唐朝'], '先秦': ['春秋', '战国']}


def variants(name, dyn):
    out = []
    for w in DYNWORDS.get(dyn, [dyn]) + ['诗人']:
        out.append(f'{name} ({w})')
    return list(dict.fromkeys(out))


# ---------------- 抓取 ----------------
def missing_authors():
    A = json.load(open(SITE + '/data/authors.json'))
    m = [e for e in A if not e[4] and e[0] not in ('佚名', '无名氏')]
    m.sort(key=lambda e: -e[2])
    return m


def fetch(budget):
    t0 = time.time()
    M = missing_authors()
    done = set(cache['done'])
    todo = [e for e in M if f'{grp(e[1])}|{e[0]}' not in done]
    print('todo', len(todo), 'of', len(M), flush=True)
    step = 20
    n = 0
    while todo and time.time() - t0 < budget:
        batch, todo = todo[:step], todo[step:]
        wp_query([e[0] for e in batch])
        # 第二轮：失败或消歧义的 → 变体标题与消歧义链接
        extra = []
        for e in batch:
            info = cache['q'].get(e[0])
            ok, r = judge(e[0], e[1], info) if (info and not info['dis']) else (False, '')
            if ok or info is None:
                continue  # 无同名条目时不再猜测变体
            extra += variants(e[0], e[1])
            if info and info['dis']:
                for l in wp_links(info['title']):
                    if t2s(l).startswith(e[0]) and l != info['title'] and len(l) <= len(e[0]) + 14:
                        extra.append(l)
        extra = [t for t in dict.fromkeys(extra) if t not in cache['q']]
        for i in range(0, len(extra), 20):
            wp_query(extra[i:i + 20])
        qids = []
        for e in batch:
            for t in [e[0]] + variants(e[0], e[1]) + cand_links(e[0]):
                inf = cache['q'].get(t)
                if inf and inf.get('qid'):
                    qids.append(inf['qid'])
        wd_fetch(qids)
        for e in batch:
            cache['done'].append(f'{grp(e[1])}|{e[0]}')
        n += len(batch)
        if n % 200 == 0:
            save()
            print('done', len(cache['done']), round(time.time() - t0), 's', flush=True)
    save()
    print('saved; done', len(cache['done']), 'remaining', len(todo), flush=True)


def cand_links(name):
    inf = cache['q'].get(name)
    if inf and inf['dis']:
        return [l for l in cache['links'].get(inf['title'], []) if t2s(l).startswith(name) and l != inf['title'] and len(l) <= len(name) + 14]
    return []


# ---------------- 生成 ----------------
PAREN_DROP = re.compile(r'[（(][^（）()]*?(拼音|注音|粤拼|罗马|白话字|英语|英文|威妥玛|国际音标|IPA|日语|韩语|朝鲜语|越南语|满语|蒙古语|藏语|拉丁|旧作|又作)[^（）()]*?[）)]')
PAREN_LATIN = re.compile(r'[（(]\s*[A-Za-zĀ-ɏ\s\-·\'’,.;:ˇˊˋ˙]+\s*[）)]')
REFS = re.compile(r'\[(注\s*)?\d+\]|\[来源请求\]|\[需要引用\]|\[谁？\]|\[何时？\]')


def clean(x, limit=300):
    x = t2s(x)
    x = REFS.sub('', x)
    for _ in range(2):
        x = PAREN_DROP.sub('', x)
    x = PAREN_LATIN.sub('', x)
    x = re.sub(r'[（(]\s*[)）]', '', x)
    x = re.sub(r'[ \t]+', ' ', x)
    paras = [p.strip() for p in x.split('\n') if p.strip()]
    out = ''
    for p in paras:
        cand = (out + '\n' + p) if out else p
        if len(cand) <= limit:
            out = cand
            continue
        # 截断：在 limit 内最后一个句末标点处断开
        room = p[:limit - len(out) - (1 if out else 0)]
        cut = max(room.rfind(c) for c in '。！？；')
        if cut >= 20:
            out = (out + '\n' if out else '') + room[:cut + 1]
        break
    if not out and paras:
        p = paras[0]
        cut = max(p[:limit].rfind(c) for c in '。！？；')
        out = p[:cut + 1] if cut > 0 else p[:limit]
    out = out.rstrip('；;，,') 
    if out and out[-1] not in '。！？」』”）)':
        out += '。'
    return out


def build():
    M = missing_authors()
    res, reasons, owner = {}, collections.Counter(), collections.defaultdict(list)
    proc = 0
    for e in M:
        key = f'{grp(e[1])}|{e[0]}'
        if key not in set_done:
            continue
        proc += 1
        name, dyn = e[0], e[1]
        base = cache['q'].get(name)
        chosen, first_reason = None, None
        ok, r = judge(name, dyn, base)
        if ok:
            chosen = base
        else:
            first_reason = r
            cands = []
            for t in variants(name, dyn) + cand_links(name):
                inf = cache['q'].get(t)
                if inf and judge(name, dyn, inf)[0]:
                    cands.append(inf)
            uniq = {c['title']: c for c in cands}
            if len(uniq) == 1:
                chosen = next(iter(uniq.values()))
            elif len(uniq) > 1:
                # 优先标题含朝代字者
                dw = [c for c in uniq.values() if any(w in t2s(c['title']) for w in DYNWORDS.get(dyn, [dyn]))]
                if len(dw) == 1:
                    chosen = dw[0]
                else:
                    first_reason = '同名多条无法区分'
        if chosen and base and base['dis'] and chosen is not base:
            # 消歧义页上若还有同朝代的其他同名者（含红链），只有条目明显是文人、且别的同名者都不像诗人时才采用
            ct = t2s(chosen['title'])
            others = [l for l in t2s(base['x']).split('\n') if l.startswith(name) and not l.startswith(ct)]
            same = [l for l in others if era_ok(dyn, l) or re.search(ERA.get(dyn, dyn), l)]
            if any(re.search(r'诗|词人|文学|文人|作家', l) for l in same):
                chosen, first_reason = None, '同名多条无法区分'
            elif same and not LIT.search(t2s(chosen['x'])[:400]):
                chosen, first_reason = None, '同名多条无法区分'
        if not chosen:
            reasons[first_reason or '无条目'] += 1
            continue
        b = clean(chosen['x'])
        if len(b) < 15:
            reasons['导言过短'] += 1
            continue
        t = chosen['title']
        res[key] = {'b': b, 'title': t2s(t), 'url': 'https://zh.wikipedia.org/wiki/' + urllib.parse.quote(t.replace(' ', '_')),
                    'n': e[2], 'd': dyn, 'ref': e[3]}
        owner[t].append(key)
    # 同一条目被多个（不同朝代组的同名）作者认领 → 都丢弃
    for t, ks in owner.items():
        if len(ks) > 1:
            for k in ks:
                res.pop(k, None)
                reasons['同一条目被多位同名作者认领'] += 1
    json.dump(res, open(OUT, 'w'), ensure_ascii=False, indent=0)
    tiers = collections.Counter('≥50' if v['n'] >= 50 else '≥10' if v['n'] >= 10 else '<10' for v in res.values())
    st = {'processed': proc, 'filled': len(res), 'tiers': tiers, 'reasons': reasons}
    json.dump(st, open(STATS, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(st, ensure_ascii=False, indent=1))


def apply():
    W = json.load(open(OUT))
    A = json.load(open(SITE + '/data/authors.json'))
    byref = collections.defaultdict(list)
    for k, v in W.items():
        byref[v['ref']].append((k, v))
    added = set()
    for ref, items in byref.items():
        if str(ref).startswith('x'):
            fn = f'{SITE}/data/a/{ref}-0.json'
            o = json.load(open(fn))
            k, v = items[0]
            if o.get('b'):
                if o.get('bw') == v['url']:
                    added.add(k)  # 已写过（续跑）
                continue
            o['b'], o['bw'], o['bt'] = v['b'], v['url'], v['title']
            json.dump(o, open(fn, 'w'), ensure_ascii=False, separators=(',', ':'))
            added.add(k)
        else:
            fn = f'{SITE}/data/a/{ref}.json'
            o = json.load(open(fn))
            ch = False
            for k, v in items:
                a = o.get(k)
                if a is None or a.get('b'):
                    if a and a.get('bw') == v['url']:
                        added.add(k)
                    continue
                a['b'], a['bw'], a['bt'] = v['b'], v['url'], v['title']
                added.add(k)
                ch = True
            if ch:
                json.dump(o, open(fn, 'w'), ensure_ascii=False, separators=(',', ':'))
    n = 0
    for e in A:
        if f'{grp(e[1])}|{e[0]}' in added and not e[4]:
            e[4] = 1
            n += 1
    json.dump(A, open(SITE + '/data/authors.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('applied', len(added), 'authors.json flags', n)


set_done = set(cache['done'])
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'fetch'
    if cmd == 'fetch':
        fetch(float(sys.argv[2]) if len(sys.argv) > 2 else 1e9)
    elif cmd == 'build':
        build()
    elif cmd == 'apply':
        apply()
