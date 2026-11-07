import re
# Stage 2: write static data shards into site/data
import json, os, math, hashlib, collections, shutil, random
from paths import BUILD as B, DATA as D
for sub in ('p', 's', 'a', 'l'):
    shutil.rmtree(f'{D}/{sub}', ignore_errors=True); os.makedirs(f'{D}/{sub}', exist_ok=True)
C = json.load(open(B + '/corpus.json'))
M = json.load(open(B + '/meta_raw.json'))
BIOS = json.load(open(B + '/bios.json'))
# 合集篇数按实际记录数（canon 去重后 id 段里有空位；段长仍用 mc/ext）
_n = collections.Counter(r['c'] for r in C)
for _m in M['colls']:
    _m.setdefault('mc', _m['count']); _m['count'] = _n.get(_m['code'], 0)
# 维基百科补充简介（tools/wiki_bios.py 生成；仅用于原本无简介的作者，带出处 bw/bt）
WIKI = json.load(open(B + '/wiki_bios.json')) if os.path.exists(B + '/wiki_bios.json') else {}
# CBDB 模板简介（build/cb_bios.json，CC BY-NC-SA 4.0；仅补无简介/占位作者，带 bc=CBDB personid）
CBB = json.load(open(B + '/cb_bios.json')) if os.path.exists(B + '/cb_bios.json') else {}
PS, CH, AB = 500, 2000, 256
FAMOUS_SONG = set('苏轼 陆游 王安石 杨万里 黄庭坚 范成大 欧阳修 梅尧臣 苏舜钦 林逋 晏殊 秦观 陈与义 朱熹 文天祥 辛弃疾 李清照 姜夔 刘克庄 戴复古 曾巩 苏辙 叶绍翁 赵师秀 翁卷 卢梅坡 程颢 王令 张俞 雷震 志南 林升 范仲淹 寇准 晏几道 周邦彦 柳永 岳飞 陈师道 张耒 晁补之 汪藻 吕本中 曾几 尤袤 萧德藻 严羽 谢枋得 郑思肖 汪元量'.split())

def dump(path, obj):
    with open(path, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))

# 大分片按字节切子分片（与 tools/split_big_shards.py 同规则，上限 600KB），边界记入 M['psplit']
MAX_SHARD = 600 * 1024
def dump_shard(k, lst):
    raw = json.dumps(lst, ensure_ascii=False, separators=(',', ':'))
    if len(raw.encode('utf-8')) <= MAX_SHARD:
        dump(f'{D}/p/{k}.json', lst)
        return
    bounds, chunks, cur, cur_bytes = [0], [], [], 0
    for i, r in enumerate(lst):
        b = len(json.dumps(r, ensure_ascii=False).encode('utf-8')) if r else 4
        if cur and cur_bytes + b > MAX_SHARD:
            chunks.append(cur); bounds.append(i); cur, cur_bytes = [], 0
        cur.append(r); cur_bytes += b
    if cur: chunks.append(cur)
    for sub, ch in enumerate(chunks): dump(f'{D}/p/{k}-{sub}.json', ch)
    plain = f'{D}/p/{k}.json'
    if os.path.exists(plain): os.remove(plain)
    M.setdefault('psplit', {})[str(k)] = bounds

def first_line(p):
    for x in p:
        x = x.strip()
        if x: return x[:26]
    return ''

# pop byte
pop = bytearray(M['total_ids'])
for r in C:
    v = r.get('_pop', 0)
    if r['c'] == 'songshi' and r['a'] in FAMOUS_SONG: v += 1.5
    if r['c'] not in ('tang', 'songshi', 'songci', 'yuanqu', 'xinshi', 'jiuti', 'jinyuan', 'mingshi', 'qingshi', 'buyi'): v += 4.5  # curated small collections rank above the giant ones
    pop[r['i']] = max(1, min(255, int(v * 22)))
coll_dyn0 = {m['code']: m['dyn'] for m in M['colls']}
DL = [''] + sorted({r.get('d') or coll_dyn0[r['c']] for r in C}); DI = {d: i for i, d in enumerate(DL)}
dyb = bytearray(M['total_ids'])
for r in C: dyb[r['i']] = DI[r.get('d') or coll_dyn0[r['c']]]
import base64; json.dump({'b': base64.b64encode(bytes(pop)).decode(), 'dl': DL, 'db': base64.b64encode(bytes(dyb)).decode()}, open(D + '/pop.json', 'w'))

# poem shards
shards = collections.defaultdict(list)
for r in C:
    k = r['i'] // PS
    rel = r['i'] - k * PS
    lst = shards[k]
    while len(lst) < rel: lst.append(None)
    row = [r['t'], r['a'], r['g'], r['p']]
    x = dict(r.get('x') or {})
    if x: row.append(x)
    lst.append(row)
for k, lst in shards.items(): dump(f'{D}/p/{k}.json', lst)

# stub chunks
chunks = collections.defaultdict(list)
for r in C:
    k = r['i'] // CH; rel = r['i'] - k * CH
    lst = chunks[k]
    while len(lst) < rel: lst.append(None)
    st = [r['t'], r['a'], first_line(r['p']), r['g']]
    sel = (r.get('x') or {}).get('sel')
    if sel: st.append(sel)
    lst.append(st)
for k, lst in chunks.items(): dump(f'{D}/s/{k}.json', lst)

# authors
def grp(d): return '唐' if d in ('唐', '五代') else d
coll_dyn = {m['code']: m['dyn'] for m in M['colls']}
authors = collections.OrderedDict()
for r in C:
    d = r.get('d') or coll_dyn[r['c']]
    key = grp(d) + '|' + r['a']
    a = authors.get(key)
    if not a:
        a = authors[key] = {'n': r['a'], 'd': d, 'g': grp(d), 'L': []}
    a['L'].append([r['i'], r['t'], first_line(r['p'])[:16], r.get('_pop', 0)])
# 异名归并后（tools/attrib_fix.py），简介按旧名回查
_AL = json.load(open(B + '/attrib/decisions.json'))['alias'] if os.path.exists(B + '/attrib/decisions.json') else {}
INV = collections.defaultdict(list)
for o, n in _AL.items(): INV[n].append(o)
REF = {}
idx = []
buckets = collections.defaultdict(dict)
BIG = 400
bigc = 0
for key, a in authors.items():
    a['L'].sort(key=lambda e: -e[3])
    L = [e[:3] for e in a['L']]
    bio = BIOS.get(key, '')
    if not bio:
        for old in INV.get(a['n'], []):
            bio = BIOS.get(a['g'] + '|' + old, '')
            if bio: break
    if a['n'] in ('佚名', '无名氏', '孔子及其弟子'): bio = ''
    wx = {}
    wk = key
    if not bio and wk not in WIKI:
        for old in INV.get(a['n'], []):
            if a['g'] + '|' + old in WIKI: wk = a['g'] + '|' + old; break
    if not bio and wk in WIKI and a['n'] not in ('佚名', '无名氏'):
        bio = WIKI[wk]['b']; wx = {'bw': WIKI[wk]['url'], 'bt': WIKI[wk]['title']}
    if (not bio or re.fullmatch(r'-+|无传。?', bio.strip())) and key in CBB and a['n'] not in ('佚名', '无名氏'):
        bio = CBB[key]['b']; wx = {'bc': CBB[key]['cb']}
    cnt = len(L)
    if cnt > BIG:
        fid = f'x{bigc}'; bigc += 1
        pages = [L[i:i + 500] for i in range(0, cnt, 500)]
        for pi, pg in enumerate(pages):
            dump(f'{D}/a/{fid}-{pi}.json', {'n': a['n'], 'd': a['d'], 'b': bio if pi == 0 else '', **(wx if pi == 0 else {}), 'L': pg, 'pages': len(pages)})
        ref = fid
    else:
        h = int(hashlib.md5(key.encode()).hexdigest(), 16) % AB
        buckets[h][key] = {'n': a['n'], 'd': a['d'], 'b': bio, **wx, 'L': L}
        ref = h
    idx.append([a['n'], a['d'], cnt, ref, 1 if bio else 0]); REF[key] = ref
for h, obj in buckets.items(): dump(f'{D}/a/{h}.json', obj)
# rewrite poem shards with author ref + dynasty
shards = collections.defaultdict(list)
for r in C:
    k = r['i'] // PS; rel = r['i'] - k * PS
    lst = shards[k]
    while len(lst) < rel: lst.append(None)
    d = r.get('d') or coll_dyn[r['c']]
    lst.append([r['t'], r['a'], r['g'], r['p'], r.get('x') or 0, REF[grp(d) + '|' + r['a']], d])
for k, lst in shards.items(): dump_shard(k, lst)

idx.sort(key=lambda e: (-e[2]))
dump(D + '/authors.json', idx)

# curated lists
for code, name, desc in (('ts300', '唐诗三百首', '清代蘅塘退士孙洙编选的唐诗选本，本站据数据集标注，自《全唐诗》中检出。'),
                         ('sc300', '宋词三百首', '近代朱祖谋（上彊村民）编选的宋词选本，本站自《全宋词》中检出。')):
    L = [[r['i'], r['t'], r['a'], first_line(r['p']), r['g']] for r in C if (r.get('x') or {}).get('sel') == name]
    dump(f'{D}/l/{code}.json', L)
    M.setdefault('lists', []).append({'code': code, 'name': name, 'desc': desc, 'count': len(L)})
# 选本（v35）：千家诗、水墨唐诗的篇目与唐诗宋诗合集重复，只留一份，选本页按 x.ls 列出
for code, name, desc in (('qjs', '千家诗', '宋代谢枋得《重定千家诗》与明代王相《五言千家诗》合编的启蒙诗选。'),
                         ('shuimo', '水墨唐诗', '唐诗精选，每首附简要赏析。')):
    L = [[r['i'], r['t'], r['a'], first_line(r['p']), r['g']] for r in C if name in ((r.get('x') or {}).get('ls') or [])]
    if not L: continue
    dump(f'{D}/l/{code}.json', L)
    M.setdefault('lists', []).append({'code': code, 'name': name, 'desc': desc, 'count': len(L)})

# daily pool: curated + small classic collections
pool = [r['i'] for r in C if (r.get('x') or {}).get('sel') or r['c'] in ('shijing', 'nantang', 'shuimo', 'huajian', 'nalan')]
# 近现代：新诗取名家与有简介作者的作品，旧体取名家绝句/律诗/词，控制在约三成
MOD_FAM = set('徐志摩 戴望舒 海子 顾城 北岛 舒婷 余光中 穆旦 闻一多 艾青 郭沫若 席慕容 卞之琳 冯至 胡适 食指 郑愁予 洛夫 林徽因 何其芳 痖弦 纪弦 杨牧 西川 多多 芒克 江河 杨炼 于坚 韩东 翟永明 王小妮 欧阳江河 臧克家 朱湘 刘半农 李金发 废名 辛笛 郑敏'.split())
JIU_FAM = set('钱钟书 顾随 龙榆生 张伯驹 施蛰存 黄侃 缪钺 卢前 乔大壮 汪东 夏承焘 沈祖棻 吴宓 陈寅恪 苏曼殊 柳亚子 郁达夫 聂绀弩 启功 叶嘉莹 吕碧城 沈尹默 俞平伯 胡适 鲁迅 田遨 寇梦碧 丁宁 林庚白 黄浚 连横'.split())
mx = [r for r in C if r['c'] == 'xinshi' and r['a'] in MOD_FAM and 4 <= len(r['p']) <= 40]
mj = [r for r in C if r['c'] == 'jiuti' and r['a'] in JIU_FAM and r['g'] in ('五言绝句', '七言绝句', '五言律诗', '七言律诗', '词') and len(''.join(r['p'])) <= 140]
rnd = random.Random(20261103)
mx = rnd.sample(mx, min(500, len(mx))); mj = rnd.sample(mj, min(300, len(mj)))
pool += [r['i'] for r in mx] + [r['i'] for r in mj]
print('pool modern', len(mx), len(mj))
random.Random(20261103).shuffle(pool)
M['pool'] = pool
M['PS'] = PS; M['CH'] = CH
M['authors'] = len(idx)
M['built'] = '2026-11-06'
dump(D + '/meta.json', M)
print('shards', len(shards), 'chunks', len(chunks), 'authors', len(idx), 'big', bigc, 'buckets', len(buckets), 'pool', len(pool))

# famous authors for home page
FAM = [('唐','李白'),('唐','杜甫'),('唐','白居易'),('唐','王维'),('唐','李商隐'),('唐','杜牧'),('唐','孟浩然'),('唐','王昌龄'),('唐','刘禹锡'),('唐','韩愈'),('唐','柳宗元'),('唐','李贺'),('宋','苏轼'),('宋','李清照'),('宋','辛弃疾'),('宋','陆游'),('宋','柳永'),('宋','欧阳修'),('宋','王安石'),('宋','晏殊'),('宋','姜夔'),('宋','杨万里'),('唐','李煜'),('唐','温庭筠'),('清','纳兰性德'),('先秦','屈原'),('魏晋','曹操'),('元','关汉卿'),('元','马致远'),('近现代','徐志摩'),('近现代','戴望舒'),('近现代','海子'),('近现代','顾城'),('近现代','北岛'),('近现代','舒婷'),('近现代','余光中'),('近现代','穆旦')]
ix = {(e[1] if e[1] not in ('唐','五代') else '唐', e[0]): e for e in idx}
fam = []
for g, n in FAM:
    e = ix.get((g, n))
    if e: fam.append(e)
M['famous'] = fam
dump(D + '/meta.json', M)
print('famous', len(fam), [e[0] for e in fam])
