import collections
# Stage 1: load chinese-poetry repo, convert to Simplified, normalize, assign ids.
# Output: build/corpus.json  (list of records) + build/meta_raw.json
import json, glob, os, re, math, sys
import opencc

from paths import PARENT, BUILD
SRC = os.path.join(PARENT, 'shici-data')
OUT = BUILD
os.makedirs(OUT, exist_ok=True)
cc = opencc.OpenCC('t2s.json')
def s(x):
    if x is None: return None
    if isinstance(x, str): return cc.convert(x)
    if isinstance(x, list): return [s(i) for i in x]
    if isinstance(x, dict): return {k: s(v) for k, v in x.items()}
    return x
def J(p): return json.load(open(os.path.join(SRC, p), encoding='utf-8'))
def natkey(p):
    m = re.findall(r'\d+', os.path.basename(p)); return int(m[0]) if m else 0

PUNCT = re.compile(r'[，。？！；、：,.?!;:“”"‘’\'「」『』（）()《》\s—…·]+')
CJK = re.compile(r'[\u3400-\u9fff\U00020000-\U0002ffff]')
def clauses(paras):
    out = []
    for p in paras:
        for c in PUNCT.split(p):
            c = ''.join(CJK.findall(c))
            if c: out.append(c)
    return out
def first_clause(paras, maxlen=14):
    for p in paras:
        for c in re.split(r'[，。？！；：,.?!;:]', p):
            c = c.strip()
            if c: return c[:maxlen]
    return ''
GENRE_ORDER = ['五言绝句', '七言绝句', '五言律诗', '七言律诗', '五言长篇', '七言长篇', '四言', '六言', '杂言', '残句']
def shi_genre(paras):
    cl = clauses(paras)
    if not cl: return '杂言'
    L = set(len(c) for c in cl); n = len(cl)
    if n <= 2: return '残句'
    if len(L) == 1:
        l = L.pop()
        if l == 5: return '五言绝句' if n == 4 else '五言律诗' if n == 8 else '五言长篇' if n > 8 else '杂言'
        if l == 7: return '七言绝句' if n == 4 else '七言律诗' if n == 8 else '七言长篇' if n > 8 else '杂言'
        if l == 4: return '四言'
        if l == 6: return '六言'
    return '杂言'

def rankscore(r):
    if not r: return 0.0
    v = [math.log10(1 + (r.get(k) or 0)) for k in ('baidu', 'so360', 'bing', 'google')]
    v.sort(); return (v[1] + v[2]) / 2  # median-ish, robust to one noisy engine

colls = []  # dicts: code,name,dyn,desc,items(list of rec), sort
def C(code, name, dyn, desc, items, sort='orig', prose=False, genres_order=None):
    colls.append(dict(code=code, name=name, dyn=dyn, desc=desc, items=items, sort=sort, prose=prose, genres_order=genres_order))

def rec(title, author, paras, genre='', extra=None):
    r = {'t': title or '无题', 'a': author or '佚名', 'p': [x for x in paras if x and x.strip()], 'g': genre}
    if extra: r['x'] = {k: v for k, v in extra.items() if v}
    return r

# ---- 诗经
items = []
for x in s(J('诗经/shijing.json')):
    items.append(rec(x['title'], '佚名', x['content'], x['chapter'], {'s': f"{x['chapter']}·{x['section']}"}))
C('shijing', '诗经', '先秦', '中国最早的诗歌总集，收录西周初年至春秋中叶的诗歌三百零五篇，分风、雅、颂三部分。', items)

# ---- 楚辞
items = [rec(x['title'], x['author'], x['content'], x['section']) for x in s(J('楚辞/chuci.json'))]
C('chuci', '楚辞', '先秦', '战国时期以屈原为代表的楚地诗歌，西汉刘向辑录成集。', items)

# ---- 论语
items = [rec(x['chapter'], '孔子及其弟子', x['paragraphs'], '论语') for x in s(J('论语/lunyu.json'))]
C('lunyu', '论语', '先秦', '记录孔子及其弟子言行的语录体著作，共二十篇。', items, prose=True)

# ---- 四书（大学、中庸、孟子）
items = []
d = s(J('四书五经/daxue.json')); items.append(rec('大学', '曾子（传）', d['paragraphs'], '大学'))
d = s(J('四书五经/zhongyong.json')); items.append(rec('中庸', '子思（传）', d['paragraphs'], '中庸'))
for x in s(J('四书五经/mengzi.json')): items.append(rec('孟子·' + x['chapter'], '孟子', x['paragraphs'], '孟子'))
C('sishu', '四书', '先秦', '《大学》《中庸》《孟子》（《论语》另列）。', items, prose=True)

# ---- 曹操
items = [rec(x['title'], '曹操', x['paragraphs'], '') for x in s(J('曹操诗集/caocao.json'))]
C('caocao', '曹操诗集', '汉魏', '东汉末年曹操的诗歌作品。', items)

# ---- 水墨唐诗 (prologue = 赏析) — indexed for attaching to 全唐诗 too
shuimo = s(J('水墨唐诗/shuimotangshi.json'))
shuimo_map = {(x['author'], x['title']): x['prologue'] for x in shuimo}
# ---- 唐诗三百首 tags (by id)
t300 = s(J('全唐诗/唐诗三百首.json'))
t300_ids = {x['id']: x.get('tags') or [] for x in t300}

# ---- 全唐诗
items = []
files = sorted(glob.glob(SRC + '/全唐诗/poet.tang.*.json'), key=natkey)
for f in files:
    n = natkey(f)
    raw = s(json.load(open(f)))
    rk = json.load(open(f'{SRC}/rank/poet/poet.tang.rank.{n}.json'))
    for i, x in enumerate(raw):
        r = rk[i] if i < len(rk) and rk[i].get('title') and s(rk[i]['title']) == x['title'] else None
        ex = {}
        if x.get('id') in t300_ids: ex['tg'] = t300_ids[x['id']]; ex['sel'] = '唐诗三百首'
        pr = shuimo_map.get((x['author'], x['title']))
        if pr: ex['pr'] = pr
        it = rec(x['title'], x['author'], x['paragraphs'], shi_genre(x['paragraphs']), ex)
        it['_pop'] = rankscore(r) + (3 if 'sel' in ex else 0) + (1 if pr else 0)
        it['_uid'] = x.get('id')
        items.append(it)
for x in s(J('全唐诗/唐诗补录.json')):
    it = rec(x['title'] or first_clause(x['paragraphs']), x['author'], x['paragraphs'], shi_genre(x['paragraphs']), {'n': [x['notes']] if x.get('notes') else None}); it['_pop'] = 0; items.append(it)
C('tang', '全唐诗', '唐', '清康熙年间彭定求等奉敕编校，收唐、五代诗近五万首；本站据 chinese-poetry 数据收录。', items, sort='genre_pop', genres_order=GENRE_ORDER)

# ---- 花间集
items = []
for f in sorted(glob.glob(SRC + '/五代诗词/huajianji/huajianji-*-juan.json'), key=lambda p: (99 if '-x-' in p else natkey(p))):
    for x in s(json.load(open(f))):
        items.append(rec(x['title'], x['author'], x['paragraphs'], x.get('rhythmic', ''), {'n': x.get('notes')}))
pre = s(J('五代诗词/huajianji/huajianji-0-preface.json'))
for x in pre:
    items.insert(0, rec('花间集序', '欧阳炯', x.get('paragraphs') or [], '序', {'n': x.get('notes')}))
C('huajian', '花间集', '五代', '后蜀赵崇祚编，中国文学史上第一部文人词选集，收温庭筠、韦庄等十八家词五百首。', items)

# ---- 南唐二主词
nt = s(J('五代诗词/nantang/poetrys.json'))
items = [rec(x.get('title') or x.get('rhythmic'), x['author'], x['paragraphs'], x.get('rhythmic', ''), {'n': x.get('notes')}) for x in nt]
intro = s(J('五代诗词/nantang/intro.json'))
C('nantang', '南唐二主词', '五代', ''.join(intro['desc'][:1]), items)
nantang_auth = {a['name']: a['desc'] for a in s(J('五代诗词/nantang/authors.json'))}

# ---- 全宋诗
items = []
files = sorted(glob.glob(SRC + '/全唐诗/poet.song.*.json'), key=natkey)
for f in files:
    n = natkey(f)
    raw = s(json.load(open(f)))
    try: rk = json.load(open(f'{SRC}/rank/poet/poet.song.rank.{n}.json'))
    except Exception: rk = []
    for i, x in enumerate(raw):
        r = rk[i] if i < len(rk) and rk[i].get('title') and s(rk[i]['title']) == x['title'] else None
        it = rec(x['title'], x['author'], x['paragraphs'], shi_genre(x['paragraphs']))
        it['_pop'] = rankscore(r)
        items.append(it)
C('songshi', '全宋诗', '宋', '北京大学古文献研究所编纂的宋代诗歌总集；本站据 chinese-poetry 数据收录。', items, sort='genre_pop', genres_order=GENRE_ORDER)

# ---- 全宋词
s300 = s(J('宋词/宋词三百首.json'))
s300_keys = {(x['author'], x['rhythmic'], (x['paragraphs'] or [''])[0]) for x in s300}
items = []
files = sorted(glob.glob(SRC + '/宋词/ci.song.*.json'), key=natkey)
files = [f for f in files if re.search(r'ci\.song\.\d+\.json$', f)]
for f in files:
    n = natkey(f)
    raw = s(json.load(open(f)))
    try: rk = json.load(open(f'{SRC}/rank/ci/ci.song.rank.{n}.json'))
    except Exception: rk = []
    for i, x in enumerate(raw):
        r = rk[i] if i < len(rk) and rk[i].get('author') and s(rk[i]['author']) == x['author'] else None
        paras = x['paragraphs']
        fc = first_clause(paras)
        ex = {'tg': x.get('tags')}
        if (x['author'], x['rhythmic'], (paras or [''])[0]) in s300_keys: ex['sel'] = '宋词三百首'
        it = rec(f"{x['rhythmic']}·{fc}" if fc else x['rhythmic'], x['author'], paras, x['rhythmic'], ex)
        it['_pop'] = rankscore(r) + (3 if 'sel' in ex else 0)
        items.append(it)
C('songci', '全宋词', '宋', '唐圭璋编纂的宋代词作总集，收词人一千三百三十余家、词作约两万首。', items, sort='pop')

# ---- 元曲
items = []
for x in s(J('元曲/yuanqu.json')):
    t = x['title']; g = t.split('・')[-1].split('·')[-1] if ('・' in t or '·' in t) else ''
    items.append(rec(t.replace('・', '·'), x['author'], x['paragraphs'], g))
C('yuanqu', '元曲', '元', '元代杂剧与散曲作品选录。', items)

# ---- 纳兰性德
items = []
for x in s(J('纳兰性德/纳兰性德诗集.json')):
    t = x['title']; g = t.split('·')[0] if '·' in t else ''
    items.append(rec(t, x.get('author') or '纳兰性德', x['para'], g))
C('nalan', '纳兰性德', '清', '清代词人纳兰性德的词作。', items)

# ---- 水墨唐诗 (own collection, with 赏析)
items = [rec(x['title'], x['author'], x['paragraphs'], shi_genre(x['paragraphs']), {'pr': x['prologue']}) for x in shuimo]
C('shuimo', '水墨唐诗', '唐', '唐诗精选，每首附简要赏析。', items)

# ---- 幽梦影
items = []
for x in s(J('幽梦影/youmengying.json')):
    items.append(rec(first_clause([x['content']], 16), '张潮', [x['content']], '幽梦影', {'cm': x.get('comment')}))
C('youmeng', '幽梦影', '清', '清代张潮的清言小品集，附时人评语。', items, prose=True)

# ---- 古文观止
gw = s(J('蒙学/guwenguanzhi.json'))
items = []
for vol in gw['content']:
    for x in vol['content']:
        au = (x.get('author') or '').strip()
        dyn, _, name = au.partition('：')
        if not name: name, dyn = dyn, ''
        items.append(rec(x['chapter'], name.strip() or '佚名', x['paragraphs'], vol['title'], {'src': x.get('source'), 'ad': dyn.strip()}))
C('guwen', '古文观止', '清', ''.join(gw['abstract'][:2]), items, prose=True)

# ---- 蒙学
items = []
def book(fn): return s(J('蒙学/' + fn))
d = book('sanzijing-traditional.json'); items.append(rec('三字经（传统版）', '王应麟', d['paragraphs'], '三字经'))
d = book('sanzijing-new.json'); items.append(rec('三字经（新版）', '王应麟', d['paragraphs'], '三字经'))
d = J('蒙学/qianziwen.json'); items.append(rec('千字文', '周兴嗣', s(d['paragraphs']), '千字文', {'py': d.get('spells')}))
d = book('baijiaxing.json'); items.append(rec('百家姓', '佚名', d['paragraphs'], '百家姓', {'og': [[o['surname'], o['place']] for o in d.get('origin', [])]}))
d = book('dizigui.json')
for c in d['content']: items.append(rec('弟子规·' + c['chapter'], '李毓秀', c['paragraphs'], '弟子规', {'ad': '清'}))
d = book('qianjiashi.json')
for grp in d['content']:
    for x in grp['content']:
        au = x.get('author') or ''
        m = re.match(r'（(.+?)）(.*)', au); ad, name = (m.group(1), m.group(2)) if m else ('', au)
        paras = x.get('paragraphs') or []
        if paras and isinstance(paras[0], dict):
            flat = []
            for sub in paras: flat += ([sub.get('subchapter') and '〔' + sub['subchapter'] + '〕'] if sub.get('subchapter') else []) + sub.get('paragraphs', [])
            paras = flat
        items.append(rec(x['chapter'], name or '佚名', paras, '千家诗', {'ad': ad, 's': grp['type']}))
d = book('shenglvqimeng.json')
for vol in d['content']:
    for x in vol['content']: items.append(rec('声律启蒙·' + x['chapter'], '车万育', x['paragraphs'], '声律启蒙', {'ab': d.get('abstract'), 's': vol['title']}))
d = book('youxueqionglin.json')
for vol in d['content']:
    for x in vol['content']: items.append(rec('幼学琼林·' + x['chapter'], '程登吉', x['paragraphs'], '幼学琼林', {'ab': d.get('abstract'), 's': vol['title'], 'f': 1, 'ad': '明'}))
d = book('zengguangxianwen.json')
for x in d['content']: items.append(rec('增广贤文·' + x['chapter'], '佚名', x['paragraphs'], '增广贤文', {'ab': d.get('abstract')}))
d = book('zhuzijiaxun.json'); items.append(rec('朱子家训', '朱柏庐', d['paragraphs'], '朱子家训', {'ad': '清'}))
d = book('wenzimengqiu.json')
for x in d['content']: items.append(rec('文字蒙求·' + x['title'], '王筠', x['paragraphs'], '文字蒙求', {'ab': d.get('abstract'), 'f': 1}))
C('mengxue', '蒙学', '历代', '三字经、千字文、百家姓、弟子规、千家诗、声律启蒙、幼学琼林、增广贤文、朱子家训、文字蒙求等传统启蒙读物。', items)


# ---- 近现代（yuxqiu/modern-poetry 的 China-modern-poetry，Apache-2.0；只收中国部分，剔除外国诗译作）
MP = os.path.join(PARENT, 'modern-poetry', 'China-modern-poetry')
def mp_load(sub):
    out = []
    for f in sorted(glob.glob(f'{MP}/{sub}/*.json'), key=natkey):
        if 'author' in os.path.basename(f): continue
        out += json.load(open(f, encoding='utf-8'))
    return s(out)
def mp_bios(sub):
    out = {}
    for f in glob.glob(f'{MP}/{sub}/author*.json'):
        for a in s(json.load(open(f, encoding='utf-8'))):
            if a.get('description'): out[a['name'].strip()] = a['description'].strip()
    return out
FOREIGN_TR = re.compile(r'^译|译法国诗人|译歌|莎士比亚招隐词')
def mp_clean_title(t): return re.sub(r'\s{2,}', '  ', (t or '').strip())
def split_sent(txt):
    return [x.strip() for x in re.findall(r'[^。！？]+[。！？」”]*', txt) if x.strip()]
CIPAI = {r['g'] for r in colls[[c['code'] for c in colls].index('songci')]['items'] if r['g']}
CIPAI |= set('浣溪纱 念奴娇 金缕曲 百字令 贺新凉 买陂塘 迈陂塘 摸鱼子 忆江南 望江南 梦江南 江南好 双调望江南 采桑子 丑奴儿 鹧鸪天 浪淘沙 减兰 减字木兰花 台城路 减字浣溪沙 摊破浣溪沙 摊破浣溪纱 浣沙溪 十六字令 鹊踏枝 一剪梅 甘州 八声甘州 春去也 琵琶仙 思嘉客 南柯子 壶中天 壶中天慢 闲中好 雨中花 六幺令 扫花游 锁窗寒 凤栖梧 菩萨鬘 湘月 西子妆 西子妆慢 陌上花 灼灼花 归国谣 琴调相思引 醉落魄 如此江山 南楼令 珍珠帘 芳草渡 庆宫春 踏莎美人 离亭燕 庆春泽慢 甘州子 绿意 倾杯 小梅花 夜飞鹊 谢秋娘 三台令 国香慢 辘轳金井 钗头凤 误佳期 江神子 罗敷媚 前调 齐天乐 疏影 暗香 高阳台 声声慢 满庭芳 水龙吟 沁园春 贺新郎 蝶恋花 临江仙 虞美人 清平乐 菩萨蛮 浣溪沙 卜算子 点绛唇 如梦令 长相思 生查子 渔家傲 西江月 踏莎行 苏幕遮 青玉案 蝶恋花 好事近 忆秦娥 风入松 祝英台近 解连环 莺啼序 霜叶飞 三姝媚 眼儿媚 惜分飞 柳梢青 太常引 捣练子 摘芳词'.split())
def is_ci(title):
    head = re.split(r'[·・\s（(，,]', title, 1)[0]
    head = re.sub(r'([一二三四五六七八九十百]+(首|阕|章|叠|解|调))?(选[一二三四五六七八九十]+)?$', '', head)
    head = re.sub(r'^(双调|中吕|仙吕|南吕|正宫|越调|商调|双调)(?=..)', '', head) if head not in CIPAI else head
    return len(head) >= 2 and head in CIPAI
mp_seen = set()
def mp_key(a, t, paras): return (a, t, ''.join(paras)[:40])
# 现当代新诗
nb = mp_bios('contemporary'); xs = mp_load('contemporary')
acnt = {}
for x in xs: acnt[x['author'].strip()] = acnt.get(x['author'].strip(), 0) + 1
items = []
for x in xs:
    a = x['author'].strip(); t = mp_clean_title(x['title']); paras = [l.rstrip() for l in x['paragraphs']]
    k = mp_key(a, t, paras)
    if k in mp_seen or not paras or FOREIGN_TR.search(t): continue
    mp_seen.add(k)
    it = rec(t, a, paras, '新诗'); it['_pop'] = math.log10(1 + acnt[a]) + (0.5 if a in nb else 0); items.append(it)
C('xinshi', '现当代新诗', '近现代', '五四以来的白话新诗，从胡适、郭沫若、徐志摩、戴望舒到北岛、顾城、海子、余光中等。', items, sort='pop')
# 近现代旧体诗词
items = []
for sub in ('modern times', 'modern'):
    for x in mp_load(sub):
        a = x['author'].strip(); t = mp_clean_title(x['title'])
        raw = x['paragraphs']; paras = split_sent(raw) if isinstance(raw, str) else raw
        k = mp_key(a, t, paras)
        if k in mp_seen or not paras or FOREIGN_TR.search(t): continue
        mp_seen.add(k)
        it = rec(t, a, paras, '词' if is_ci(t) else shi_genre(paras)); it['_pop'] = 0; items.append(it)
C('jiuti', '近现代旧体诗词', '近现代', '清末民国以来诗人以传统格律写作的诗词，收黄浚、连横、龙榆生、顾随、黄侃、钱钟书、施蛰存、张伯驹等。', items, sort='genre_pop', genres_order=GENRE_ORDER[:6] + ['词'] + GENRE_ORDER[6:])

# ---- 先唐诗（Werneror/Poetry，MIT）：先秦至隋的诗歌，去掉与诗经/楚辞/曹操诗集重复者
import csv
WP = os.path.join(PARENT, 'werneror')
def ckey(paras): return ''.join(CJK.findall(''.join(paras)))[:16]
have = set()
for c in colls:
    if c['code'] in ('shijing', 'chuci', 'caocao', 'lunyu', 'sishu', 'mengxue', 'guwen'):
        for r in c['items']: have.add(ckey(r['p']))
DYN_MAP = [('先秦', '先秦'), ('秦', '先秦'), ('汉', '汉'), ('魏晋', '魏晋'), ('魏晋末南北朝初', '魏晋'), ('南北朝', '南北朝'), ('隋', '隋'), ('隋末唐初', '隋')]
ANON = {'作者未详', '阙名', '无名氏', '佚名', '两汉乐府', '汉乐府', '古辞', '乐府古辞'}
items = []; wcnt = {}
rows = []
for fn, dyn in DYN_MAP:
    for x in csv.DictReader(open(f'{WP}/{fn}.csv', encoding='utf-8')):
        rows.append((dyn, s(x['题目'].strip()), s(x['作者'].strip()), s(x['内容'].strip())))
for _, _, a, _ in rows: wcnt[a] = wcnt.get(a, 0) + 1
wseen = set(); wbest = {}
chuci_t = {r['t'] for c in colls if c['code'] == 'chuci' for r in c['items']}
AU_FIX = {'陶潜': '陶渊明'}
for dyn, t, a, body in rows:
    a = AU_FIX.get(a, a)
    if not body: continue
    paras = [y.strip() for y in re.findall(r'[^。！？]+[。！？」”]*', body) if y.strip()]
    # 两句一行（五七言），其余按句
    lines = []; buf = ''
    for y in paras:
        buf += y
        if len(clauses([buf])) >= 2 or len(buf) > 24: lines.append(buf); buf = ''
    if buf: lines.append(buf)
    k = ckey(lines); k6 = (a, t, k[:6])
    if not k or k in have or (a, k) in wseen or a in ('诗经', '屈原') or t in chuci_t: continue
    if k6 in wbest:
        o = wbest[k6]
        if len(re.findall(r'[，。？！；]', body)) > len(re.findall(r'[，。？！；]', ''.join(o['p']))): o['p'] = lines
        continue
    wseen.add((a, k))
    au = '佚名' if a in ANON else a
    it = rec(t, au, lines, dyn, {'ad': dyn}); wbest[k6] = it; it['_pop'] = math.log10(1 + wcnt.get(a, 0)) if au != '佚名' else 0.3; items.append(it)
C('xiantang', '先唐诗', '先秦至隋', '诗经、楚辞之外的先秦至隋代诗歌：汉乐府、古诗十九首、建安风骨、陶渊明、谢灵运、鲍照、庾信、南北朝民歌等。', items, sort='genre_pop', genres_order=['先秦', '汉', '魏晋', '南北朝', '隋'])

# ---- 先秦两汉典籍（维基文库，公有领域文本，繁转简、去注疏）
PC = os.path.join(PARENT, 'prose-classics')
items = []
for bk in ('道德经', '庄子', '荀子', '韩非子', '尚书', '礼记', '左传', '战国策', '史记'):
    for x in json.load(open(f'{PC}/{bk}.json', encoding='utf-8')):
        it = rec(x['title'], x['author'], x['paragraphs'], bk, {'ad': x['dynasty']}); items.append(it)
C('dianji', '先秦两汉典籍', '先秦两汉', '道德经、庄子、荀子、韩非子、尚书、礼记、左传、战国策、史记，逐篇收录正文（不含注疏）。', items, prose=True)

# ---- 金元明清诗（Werneror/Poetry，MIT）：与已有篇目按正文前 16 字去重
csv.field_size_limit(10**9)
have_all = {ckey(r['p']) for c in colls for r in c['items']}
def wp_lines(body):
    paras = [y.strip() for y in re.findall(r'[^。！？]+[。！？」”]*', body) if y.strip()]
    lines = []; buf = ''
    for y in paras:
        buf += y
        if len(clauses([buf])) >= 2 or len(buf) > 24: lines.append(buf); buf = ''
    if buf: lines.append(buf)
    return lines
WP_DYN = {'辽': '辽', '金': '金', '金末元初': '金', '元': '元', '元末明初': '明', '明_1': '明', '明_2': '明', '明_3': '明', '明_4': '明',
          '明末清初': '清', '清_1': '清', '清_2': '清', '清末民国初': '清', '清末近现代初': '清'}
def wp_coll(code, name, dyn, desc, files, famous):
    rows = []
    for fn in files:
        for x in csv.DictReader(open(f'{WP}/{fn}.csv', encoding='utf-8')):
            rows.append((s(x['题目'].strip()), s(x['作者'].strip()), s(x['内容'].strip()), WP_DYN.get(fn, dyn)))
    cnt = {}
    for _, a, _, _ in rows: cnt[a] = cnt.get(a, 0) + 1
    items = []; seen = {}
    for t, a, body, fd in rows:
        if not body: continue
        lines = wp_lines(body); k = ckey(lines)
        if len(k) < 4 or k in have_all: continue
        k6 = (a, t, k[:6])
        if k6 in seen:
            o = seen[k6]
            if len(re.findall(r'[，。？！；]', body)) > len(re.findall(r'[，。？！；]', ''.join(o['p']))): o['p'] = lines
            continue
        have_all.add(k)
        au = '佚名' if a in ANON else a
        it = rec(t, au, lines, '词' if is_ci(t) else shi_genre(lines))
        it['_fd'] = fd
        it['_pop'] = (0.3 if au == '佚名' else math.log10(1 + cnt.get(a, 0))) + (2.5 if au in famous else 0)
        seen[k6] = it; items.append(it)
    C(code, name, dyn, desc, items, sort='genre_pop', genres_order=GENRE_ORDER[:6] + ['词'] + GENRE_ORDER[6:])
wp_coll('jinyuan', '辽金元诗', '辽金元', '辽、金、元三代及金末元初、元末明初的诗词，收元好问、赵孟頫、萨都剌、虞集、杨维桢、王冕、刘基等。',
        ['辽', '金', '金末元初', '元', '元末明初'], set('元好问 赵孟頫 萨都剌 萨都拉 虞集 杨载 范梈 揭傒斯 杨维桢 王冕 刘因 耶律楚材 倪瓒 王恽 卢挚 张养浩 马祖常 贯云石 刘基 宋濂 高启 杨基 王庭筠 党怀英 蔡松年 吴激'.split()))
wp_coll('mingshi', '明诗', '明', '明代诗词，收高启、于谦、李东阳、唐寅、文徵明、杨慎、李攀龙、王世贞、徐渭、袁宏道、陈子龙、夏完淳等。',
        ['明_1', '明_2', '明_3', '明_4', '明末清初'], set('高启 于谦 李东阳 唐寅 文徵明 祝允明 沈周 杨慎 李梦阳 何景明 李攀龙 王世贞 徐渭 袁宏道 袁中道 钟惺 谭元春 汤显祖 陈子龙 夏完淳 张煌言 戚继光 王守仁 解缙 方孝孺 杨士奇 袁凯 林鸿 张岱 钱谦益 吴伟业 顾炎武 屈大均 柳如是'.split()))
wp_coll('qingshi', '清诗', '清', '清代诗词，收钱谦益、吴伟业、王士祯、朱彝尊、查慎行、沈德潜、袁枚、赵翼、黄景仁、郑燮、龚自珍、黄遵宪等。',
        ['清_1', '清_2', '清末民国初', '清末近现代初'], set('钱谦益 吴伟业 王士祯 王士禛 朱彝尊 查慎行 沈德潜 袁枚 赵翼 蒋士铨 黄景仁 郑燮 龚自珍 魏源 林则徐 黄遵宪 谭嗣同 秋瑾 丘逢甲 康有为 梁启超 陈维崧 顾贞观 厉鹗 翁方纲 张问陶 宋琬 施闰章 吴嘉纪 屈大均 顾炎武 曹雪芹 纳兰性德 陈三立 樊增祥 王闿运 郑孝胥 文廷式 朱祖谋 况周颐 王国维'.split()))

# ---------- 补遗：chinese-classics（github.com/wujinpai/chinese-classics）中本站尚未收录的篇目（2026-11-04 用户要求「把该仓库的数据都加到站点里」）
import gzip, glob as _glob
B_CC = OUT + '/cc'
CC_DYN = {'五代': '五代', '元': '元', '先秦': '先秦', '唐': '唐', '宋': '宋', '明': '明', '清': '清', '秦汉': '汉', '辽金': '金', '近代': '近现代', '隋': '隋', '魏晋南北朝': '南北朝'}
_N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')
_site = collections.defaultdict(list); _full = set()
for c in colls:
    for r in c['items']:
        t = _N.sub('', ''.join(r['p'])); _full.add(t); _site[(r['a'], len(t))].append(t)
def _near(lst, t): return any(sum(x != y for x, y in zip(o, t)) <= max(1, len(t) // 10) for o in lst)
items = []; ccnt = collections.Counter(); _seen = {}
for fp in sorted(_glob.glob(os.path.join(B_CC, '*.json.gz'))):
    cat = os.path.basename(fp)[:-8]; kind = cat[-1]; fdyn = CC_DYN.get(cat[:-1], cat[:-1])
    for j in json.load(gzip.open(fp)):
        a0 = (j.get('author') or '').strip()
        a = s(a0) or '佚名'; a = AU_FIX.get(a, a)
        for w in j.get('works', []):
            lines = [s(x.strip()) for x in (w.get('paragraphs') or []) if x and x.strip()]
            t = s((w.get('title') or '').strip()) or '无题'
            k = _N.sub('', ''.join(lines))
            if not k: continue
            # 仓库内部重复（同作者同题、正文差 ≤10%）只收一次；本站已有（全文相同，或同作者正文差 ≤10%）不再收
            g = _seen.setdefault((a, t, len(k)), [])
            if _near(g, k): continue
            g.append(k)
            if k in _full or _near(_site.get((a, len(k)), []) + _site.get((a0, len(k)), []), k): continue
            _full.add(k); _site[(a, len(k))].append(k)
            au = '佚名' if a in ANON else a
            gname = '词' if kind == '词' else ('曲' if kind == '曲' else shi_genre(lines))
            it = rec(t, au, lines, gname); it['_cp'] = s((w.get('rhythmic') or '').strip()) or re.split(r'[·・ （(]', t)[0]; it['_fd'] = (j.get('dynasty') or '').strip() or fdyn
            if it['_fd'] in ('近代', '民国'): it['_fd'] = '近现代'
            ccnt[au] += 1; items.append(it)
for it in items: it['_pop'] = 0.3 if it['a'] == '佚名' else math.log10(1 + ccnt[it['a']])
print('buyi', len(items))
# 2026-11-04 用户要求：历代补遗不再单列，按朝代与诗词曲并入对应合集（ids 追加在旧 id 空间之后，旧补遗 id 由 moved.json 跳转）
BUYI_OLD_END = 868000
_cby = {c['code']: c for c in colls}
def _dn(d):
    d = (d or '').strip(); d = {'唐代': '唐', '宋代': '宋', '北宋': '宋', '南宋': '宋', '明代': '明', '清代': '清', '元代': '元', '金朝': '金', '辽朝': '辽', '近代': '近现代', '民国': '近现代',
                                '西汉': '汉', '东汉': '汉', '两汉': '汉', '秦汉': '汉', '三国': '魏晋', '晋': '魏晋', '西晋': '魏晋', '东晋': '魏晋', '春秋': '先秦', '战国': '先秦'}.get(d, d)
    return d
XT = ['先秦', '汉', '魏晋', '南北朝', '隋']
for it in items:
    d = _dn(it['_fd']); k = '词' if it['g'] == '词' else ('曲' if it['g'] == '曲' else '诗')
    if d.startswith('隋末') or d in ('唐', '五代') or d.startswith('唐') or d.startswith('五代'): to = 'tang'
    elif d in XT or d.startswith('南北朝') or d.startswith('魏晋'): to = 'xiantang'
    elif d.startswith('宋') or d == '北宋': to = 'songci' if k == '词' else 'songshi'
    elif d.startswith('元') and k == '曲': to = 'yuanqu'
    elif d[:1] in ('辽', '金', '元'): to = 'jinyuan'
    elif d.startswith('明'): to = 'mingshi'
    elif d.startswith('清'): to = 'qingshi'
    elif d.startswith('近') or d.startswith('现'): to = 'jiuti'
    else: raise SystemExit('buyi unmapped dynasty: ' + repr(d))
    if to == 'xiantang': it['g'] = next((x for x in XT if d.startswith(x)), '南北朝'); it.setdefault('x', {})['ad'] = it['g']
    elif to in ('songci', 'yuanqu'): it['g'] = it['_cp'] or it['g']
    it.pop('_cp', None)
    _cby[to].setdefault('ext', []).append(it)
print('buyi merged', collections.Counter(c['code'] for c in colls for _ in c.get('ext', [])).most_common())

# ---------- authors bios
bios = {}
def grp_of(dyn): return '唐' if dyn in ('唐', '五代') else dyn
for a in s(J('全唐诗/authors.tang.json')): bios.setdefault(('唐', a['name']), a.get('desc') or '')
for a in s(J('宋词/author.song.json')):
    if a.get('description'): bios[('宋', a['name'])] = a['description']
for a in s(J('全唐诗/authors.song.json')): bios.setdefault(('宋', a['name']), a.get('desc') or '')
for n, dsc in nantang_auth.items(): bios[('唐', n)] = dsc
for n, dsc in nb.items(): bios.setdefault(('近现代', n), dsc)

# ---------- ordering & ids
CH = 500  # stub chunk size; every collection starts at multiple of CH
out = []; meta = []
nid = 0
def _order(c, its):
    if c['sort'] == 'genre_pop':
        go = {g: i for i, g in enumerate(c['genres_order'])}
        its.sort(key=lambda r: (go.get(r['g'], 99), -r.get('_pop', 0)))
    elif c['sort'] == 'pop' or its is not c['items']:
        its.sort(key=lambda r: -r.get('_pop', 0))
def _assign(c, its, genres):
    global nid
    for r in its:
        r['i'] = nid; r['c'] = c['code']; r['d'] = c['dyn']
        if c['code'] in ('guwen', 'mengxue', 'xiantang', 'dianji') and r.get('x', {}).get('ad'): r['d'] = r['x']['ad']
        if c['prose']: r.setdefault('x', {})['f'] = 1
        if genres is not None:
            if not genres or genres[-1][0] != r['g'] or genres[-1][1] + genres[-1][2] != nid: genres.append([r['g'], nid, 0])
            genres[-1][2] += 1
        nid += 1
        out.append(r)
for c in colls:
    its = c['items']; _order(c, its)
    start = nid
    genres = [] if (c['sort'] in ('genre_pop',) or c['code'] in ('shijing', 'mengxue', 'sishu', 'guwen', 'dianji')) else None
    _assign(c, its, genres)
    meta.append(dict(code=c['code'], name=c['name'], dyn=c['dyn'], desc=c['desc'], start=start, count=len(its), mc=len(its), genres=genres or []))
    nid = ((nid + CH - 1) // CH) * CH
nid = max(nid, BUYI_OLD_END)  # 旧「历代补遗」id 段（790000–867749）留空，避免旧链接指向别的诗
for c, m in zip(colls, meta):
    ext = c.get('ext')
    if not ext: continue
    if c['sort'] == 'genre_pop':
        go = {g: i for i, g in enumerate(c['genres_order'])}
        ext.sort(key=lambda r: (go.get(r['g'], 99), -r.get('_pop', 0)))
    else: ext.sort(key=lambda r: -r.get('_pop', 0))
    start = nid
    _assign(c, ext, m['genres'] if m['genres'] else None)
    m['ext'] = [[start, len(ext)]]; m['count'] += len(ext)
    nid = ((nid + CH - 1) // CH) * CH
# ---------- 作者朝代归一：同名同人只留一个朝代（2026-11-04 用户要求「李白显示两个」修正）
DYN_NORM = {'唐代': '唐', '宋代': '宋', '明代': '明', '清代': '清', '元代': '元', '汉代': '汉', '隋代': '隋', '西汉': '汉', '东汉': '汉', '两汉': '汉',
            '春秋': '先秦', '战国': '先秦', '周': '先秦', '秦': '先秦', '三国': '魏晋', '晋': '魏晋', '西晋': '魏晋', '东晋': '魏晋', '北宋': '宋', '南宋': '宋',
            '金朝': '金', '辽朝': '辽', '宋末元初': '宋', '唐末宋初': '五代', '宋末金初': '宋', '金末元初': '金', '元末明初': '元', '明末清初': '明', '近代': '近现代', '现代': '近现代', '当代': '近现代'}
GENERIC = {'历代', '辽金元', '先秦至隋', '先秦两汉', '汉魏', ''}
ADJ = {frozenset(p) for p in [('先秦', '汉'), ('汉', '魏晋'), ('魏晋', '南北朝'), ('南北朝', '隋'), ('隋', '唐'), ('唐', '五代'), ('辽', '金'), ('宋', '金'),
                               ('宋', '元'), ('金', '元'), ('元', '明'), ('明', '清'), ('清', '近现代')]}
NOMERGE = {'佚名', '无名氏', '不详', '阙名', '失名',
           # v45：站点把以下作者的朝代分开，规则会误并，逐人豁免（与 dyn_norm.py 同步）。
           # 陈毅：清代陈毅（古渔）/元帅陈毅（近现代）/宋人陈毅三人同名；
           # 李好古、释子温：宋/元分属不同人；孙光宪：唐 112/宋 2 站点分开；
           # 李世民：唐/隋/隋末唐初三键分开；王谟：王謩（唐）与王谟（隋）异体分立；
           # 贾岛：宋 1 首（句）站点单独成键，零星规则会并入唐 420。
           '陈毅', '李好古', '释子温', '孙光宪', '李世民', '王谟', '贾岛'}
def ndyn(d):
    d = (d or '').strip().rstrip('：:')
    return DYN_NORM.get(d, d)
for r in out:
    r['d'] = ndyn(r.pop('_fd', None) or r['d'])
byname = collections.defaultdict(collections.Counter)
for r in out:
    if r['d'] not in GENERIC: byname[r['a']][r['d']] += 1
fix = {}
for a, cnt in byname.items():
    if a in NOMERGE or len(cnt) < 2: continue
    labs = sorted(cnt, key=lambda d: -cnt[d]); par = {d: d for d in labs}
    def f(d):
        while par[d] != d: d = par[d]
        return d
    for i in labs:
        for j in labs:
            if i != j and frozenset((i, j)) in ADJ and f(i) != f(j):
                ri, rj = f(i), f(j)
                if cnt[ri] >= cnt[rj]: par[rj] = ri
                else: par[ri] = rj
    top = labs[0]
    for d in labs[1:]:  # 名家的零星异代篇目（如全宋诗里混入的 1 首韩愈）并入主朝代
        if cnt[d] <= 2 and cnt[top] >= 50 * cnt[d] and f(d) == d: par[d] = top
    for d in labs:
        if f(d) != d: fix[(a, d)] = f(d)
moved = 0
for r in out:
    a, d = r['a'], r['d']
    if a in NOMERGE: continue
    if d in GENERIC and byname.get(a):
        r['d'] = byname[a].most_common(1)[0][0]; d = r['d']; moved += 1
    if (a, d) in fix:
        r['d'] = fix[(a, d)]; moved += 1
for r in out:
    if r['d'] == '五代' and False: pass
left = collections.Counter()
chk = collections.defaultdict(set)
for r in out:
    if r['a'] not in NOMERGE: chk[r['a']].add(r['d'])
for a, ds in chk.items():
    if len(ds) > 1: left[tuple(sorted(ds))] += 1
print('dyn fixed', moved, 'names still multi-dynasty (likely different people):', sum(left.values()))
json.dump({'left': {' / '.join(k): v for k, v in left.most_common()}, 'names': {a: sorted(ds) for a, ds in chk.items() if len(ds) > 1}},
          open(OUT + '/dyn_report.json', 'w'), ensure_ascii=False, indent=0)

json.dump({'colls': meta, 'total_ids': nid}, open(OUT + '/meta_raw.json', 'w'), ensure_ascii=False)
json.dump(out, open(OUT + '/corpus.json', 'w'), ensure_ascii=False)
json.dump({f'{k[0]}|{k[1]}': v for k, v in bios.items() if v}, open(OUT + '/bios.json', 'w'), ensure_ascii=False)
print('records', len(out), 'id space', nid)
for m in meta: print(m['code'], m['name'], m['count'], len(m['genres']))
