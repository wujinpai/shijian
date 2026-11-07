# 朝代归一：与站点 load.py 同一套规则（DYN_NORM + 按作者合并相邻/零星朝代）。
# 用途：API 构建（turso_build.py / api_sync.py）与 authors 表迁移，与站点保持同一作者标签。
# 来源：tools/load.py 的 DYN_NORM / GENERIC / ADJ / NOMERGE / ndyn 与按作者合并逻辑；
# 人名归一 gn 取自 tools/repo_canon.py（GX / STDV / PFX），此处内联以免依赖 opencc。
# 注意：若 load.py 或 repo_canon.py 改了这些表，此处须同步改。
import re
from collections import Counter

DYN_NORM = {'唐代': '唐', '宋代': '宋', '明代': '明', '清代': '清', '元代': '元', '汉代': '汉', '隋代': '隋', '西汉': '汉', '东汉': '汉', '两汉': '汉',
            '春秋': '先秦', '战国': '先秦', '周': '先秦', '秦': '先秦', '三国': '魏晋', '晋': '魏晋', '西晋': '魏晋', '东晋': '魏晋', '北宋': '宋', '南宋': '宋',
            '金朝': '金', '辽朝': '辽', '宋末元初': '宋', '唐末宋初': '五代', '宋末金初': '宋', '金末元初': '金', '元末明初': '元', '明末清初': '明', '近代': '近现代', '现代': '近现代', '当代': '近现代'}
GENERIC = {'历代', '辽金元', '先秦至隋', '先秦两汉', '汉魏', ''}
ADJ = {frozenset(p) for p in [('先秦', '汉'), ('汉', '魏晋'), ('魏晋', '南北朝'), ('南北朝', '隋'), ('隋', '唐'), ('唐', '五代'), ('辽', '金'), ('宋', '金'),
                               ('宋', '元'), ('金', '元'), ('元', '明'), ('明', '清'), ('清', '近现代')]}
NOMERGE = {'佚名', '无名氏', '不详', '阙名', '失名',
           # v45：站点把以下作者的朝代分开，规则会误并，逐人豁免（与 load.py 同步）。
           # 陈毅：清代陈毅（古渔）/元帅陈毅（近现代）/宋人陈毅三人同名；
           # 李好古、释子温：宋/元分属不同人；孙光宪：唐 112/宋 2 站点分开；
           # 李世民：唐/隋/隋末唐初三键分开；王谟：王謩（唐）与王谟（隋）异体分立；
           # 贾岛：宋 1 首（句）站点单独成键，零星规则会并入唐 420。
           '陈毅', '李好古', '释子温', '孙光宪', '李世民', '王谟', '贾岛'}

GX = {'陶潜': '陶渊明', '金履详': '金履祥', '无名氏': '佚名', '不详': '佚名', '阙名': '佚名', '作者未详': '佚名', '初惟深': '方惟深',
 '刘向 撰': '刘向', '西晋·李密': '李密', '胡[证]': '胡证', '宋徽宗': '赵佶', '宋孝宗': '赵昚', '宋真宗': '赵恒', '宋度宗': '赵禥', '赵祺': '赵禥',
 '宋理宗': '赵昀', '宋光宗': '赵惇', '宋仁宗': '赵祯', '宋宁宗': '赵扩', '宋神宗': '赵顼', '玄宗皇帝李隆基': '李隆基', '南唐嗣主李璟': '李璟',
 '宋蒲寿宬': '蒲寿宬', '释仲殊': '仲殊', '章怀太子': '李贤', '释士圭': '释士珪', '释慧勤': '释慧懃', '叶廷圭': '叶廷珪',
 '刘骘': '刘隲', '钱协': '钱勰', '戴炳': '戴昺', '赵汝燧': '赵汝𬭼', '茜桃': '蒨桃', '杨崇': '杨崈', '王崇': '王崈', '王侃': '王偘', '何称': '何偁',
 '陈称': '陈偁', '蔡楠': '蔡柟', '吴汝一': '吴汝弌', '李鼗': '李鞉', '冷应澄': '冷应澂', '孙俟': '孙竢', '王晰': '王晳', '释知炳': '释知昺'}
STDV = dict(zip('隠浄頼玨嵒閴謩鼇箎僊瓌雝靁磵逈眘葊檝譡', '隐净赖珏岩阒谟鳌篪仙瑰雍雷涧迥昚庵楫谠'))
PFX = re.compile(r'^[^：:（(]{1,6}[：:]\s*')

def gn(n):
    n = PFX.sub('', (n or '').strip()).strip() or '佚名'
    return GX.get(n) or ''.join(STDV.get(c, c) for c in n)

def ndyn(d):
    d = (d or '').strip().rstrip('：:')
    return DYN_NORM.get(d, d)

def grp(d):
    return '唐' if d in ('唐', '五代') else d

import json as _json
import os as _os
# 站点标签覆盖：单标签作者中仓库与站点判定不同的 417 人，取站点（shici-data）的朝代。
# 由站点 app/site/data/authors.json 生成（2026-11-07），见 tools/site_label_override.json。
# 站点重建改了作者标签后须重新生成。只用于单标签作者；多标签作者仍按规则算。
try:
    with open(_os.path.join(_os.path.dirname(__file__), 'site_label_override.json'), encoding='utf-8') as _f:
        SITE_LABEL_OVERRIDE = _json.load(_f)
except FileNotFoundError:
    SITE_LABEL_OVERRIDE = {}

def author_fix(byname):
    """按作者合并朝代（load.py 逻辑）。输入 {作者: Counter({朝代: 篇数})}（朝代已 ndyn，GENERIC 已排除）。
    返回 {(作者, 朝代): 合并后朝代}，只含被合并的条目。NOMERGE 作者不参与。"""
    fix = {}
    for a, cnt in byname.items():
        if a in NOMERGE or len(cnt) < 2:
            continue
        labs = sorted(cnt, key=lambda d: -cnt[d])
        par = {d: d for d in labs}
        def f(d):
            while par[d] != d:
                d = par[d]
            return d
        for i in labs:
            for j in labs:
                if i != j and frozenset((i, j)) in ADJ and f(i) != f(j):
                    ri, rj = f(i), f(j)
                    if cnt[ri] >= cnt[rj]:
                        par[rj] = ri
                    else:
                        par[ri] = rj
        top = labs[0]
        for d in labs[1:]:
            if cnt[d] <= 2 and cnt[top] >= 50 * cnt[d] and f(d) == d:
                par[d] = top
        for d in labs:
            if f(d) != d:
                fix[(a, d)] = f(d)
    return fix

def normalize_works(rows, apply_override=True):
    """对 works 聚合行做朝代归一。rows 为 (作者, 朝代, 篇数) 或 (作者, 朝代, era, author_id, 篇数)，
    返回 {(gn(作者), grp(归一后朝代)): 篇数} 与 {(作者, 朝代): 归一后朝代} 映射。
    人名先以 gn 归一再做朝代合并（同人异名须视为同一作者）；单朝代作者若在站点覆盖表中，以站点标签为准。
    apply_override=False 时只算规则结果（用于重新生成覆盖表）。"""
    byname = {}
    for r in rows:
        g, d, n = gn(r[0]), ndyn(r[1]), r[-1]
        if d not in GENERIC:
            byname.setdefault(g, Counter())[d] += n
    fix = author_fix(byname)
    # 每位作者（gn 后）归一后的朝代集合（用于判定单朝代覆盖）
    norm_dyn = {}
    for r in rows:
        g, d = gn(r[0]), ndyn(r[1])
        if d in GENERIC and byname.get(g):
            d = byname[g].most_common(1)[0][0]
        if (g, d) in fix:
            d = fix[(g, d)]
        norm_dyn.setdefault(g, set()).add(d)
    override = {}
    if apply_override:
        for g, ds in norm_dyn.items():
            if len(ds) == 1 and g in SITE_LABEL_OVERRIDE:
                override[g] = SITE_LABEL_OVERRIDE[g]
    out = Counter()
    mapping = {}
    for r in rows:
        g, d, n = gn(r[0]), ndyn(r[1]), r[-1]
        if d in GENERIC and byname.get(g):
            d = byname[g].most_common(1)[0][0]
        if (g, d) in fix:
            d = fix[(g, d)]
        if g in override:
            d = override[g]
        mapping[(r[0], r[1])] = d
        out[(g, grp(d))] += n
    return out, mapping
