# 同人异名三方统一（用户 2026-11-06：作者名必须统一，不用问）。改仓库副本 /tmp/cc/chinese-classics。
# PAIRS: (甲, 乙[, 指定名])：同一文件夹内甲乙并为一人。未指定时取有小传(author_desc)的那个名字（全宋诗原字），都没有取作品多者。
import json, glob, os, sys, re
R = os.environ.get('REPO_READ', '/tmp/cc/chinese-classics'); os.chdir(R)
FIX = {'陶潜': '陶渊明', '不详': '佚名', '无名氏': '佚名', '初惟深': '方惟深', '胡[证]': '胡证', '刘向 撰': '刘向', '西晋·李密': '李密',
       '宋徽宗': '赵佶', '宋孝宗': '赵昚', '宋真宗': '赵恒', '宋度宗': '赵禥', '赵祺': '赵禥', '宋理宗': '赵昀', '宋光宗': '赵惇', '宋仁宗': '赵祯',
       '宋宁宗': '赵扩', '宋神宗': '赵顼', '玄宗皇帝李隆基': '李隆基', '南唐嗣主李璟': '李璟', '宋蒲寿宬': '蒲寿宬', '释仲殊': '仲殊'}
FOLDER_ONLY = {('唐诗', '章怀太子'): '李贤'}
PAIRS = [('释士珪', '释士圭'), ('赵汝譡', '赵汝谠'), ('释慧懃', '释慧勤'), ('叶廷珪', '叶廷圭'), ('刘隲', '刘骘'), ('钱勰', '钱协'), ('戴昺', '戴炳'),
         ('赵汝𬭼', '赵汝燧'), ('蒨桃', '茜桃'), ('杨崈', '杨崇'), ('王崈', '王崇'), ('王偘', '王侃'), ('何偁', '何称'), ('陈偁', '陈称'), ('蔡柟', '蔡楠'),
         ('吴汝弌', '吴汝一'), ('李鞉', '李鼗'), ('冷应澂', '冷应澄'), ('孙竢', '孙俟'), ('王晳', '王晰'), ('释知昺', '释知炳'), ('陈玨', '陈珏')]
nz = lambda ps: re.sub(r'[\s，。、！？；：“”‘’《》（）,.!?;:]', '', ''.join(ps or []))
def ld(p): return json.load(open(p, encoding='utf-8'))
def sv(p, j): open(p, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False))
log = []
def merge(folder, old, new):
    po, pn = f'{folder}/{old}.json', f'{folder}/{new}.json'
    if not os.path.exists(po) or old == new: return
    jo = ld(po)
    if os.path.exists(pn):
        jn = ld(pn); seen = {nz(w.get('paragraphs')) for w in jn['works']}; add = dup = 0
        for w in jo['works']:
            k = nz(w.get('paragraphs'))
            if k in seen: dup += 1; continue
            seen.add(k); jn['works'].append(w); add += 1
        if not (jn.get('author_desc') or '').strip() and (jo.get('author_desc') or '').strip(): jn['author_desc'] = jo['author_desc']
        jn['author'] = new; sv(pn, jn); os.remove(po); log.append(f'{folder} {old} -> {new} +{add} dup{dup}')
    else:
        jo['author'] = new; sv(pn, jo); os.remove(po); log.append(f'{folder} {old} -> {new} (rename {len(jo["works"])})')
folders = sorted(d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith(('.', 'scripts', '名篇索引')))
for d in folders:
    for f in sorted(glob.glob(f'{d}/*.json')):
        if not os.path.exists(f): continue
        j = ld(f)
        if isinstance(j, dict) and 'chapters' in j:
            ch = 0
            for c in j['chapters']:
                a = (c.get('author') or '').strip()
                if a in FIX: c['author'] = FIX[a]; ch += 1
            if (j.get('author') or '') in FIX: j['author'] = FIX[j['author']]; ch += 1
            if ch: sv(f, j); log.append(f'{f} chapters {ch}')
    for old, new in FIX.items(): merge(d, old, new)
    for (fd, old), new in FOLDER_ONLY.items():
        if fd == d: merge(d, old, new)
    for a, b in PAIRS:
        pa, pb = f'{d}/{a}.json', f'{d}/{b}.json'
        if not (os.path.exists(pa) and os.path.exists(pb)): continue
        ja, jb = ld(pa), ld(pb)
        da, db = bool((ja.get('author_desc') or '').strip()), bool((jb.get('author_desc') or '').strip())
        keep = a if da or not db else b
        if da == db: keep = a if len(ja['works']) >= len(jb['works']) else b
        merge(d, b if keep == a else a, keep)
# 名篇索引里的作者名同步
for f in glob.glob('名篇索引/*.json'):
    j = ld(f); ch = 0
    for x in (j if isinstance(j, list) else []):
        if x.get('author') in FIX: x['author'] = FIX[x['author']]; ch += 1
    if ch: sv(f, j); log.append(f'{f} {ch}')
print('\n'.join(log)); print('changes', len(log))
