# API 修正：古文观止等典籍章节作者被套上书的朝代（清），生成了「清·李白」之类的重复作者。
# 把章节归到同名真实作者；没有同名者的，改正其朝代。api_sync 之后需重跑。 DRY=1 只打印。
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tq import q, run
DRY = os.environ.get('DRY') == '1'
BOOK = '古文观止'
OVR = {'刘向': 41, '魏征': 4577, '张溥': 17518, '司马光': 5779, '刘禹锡': 1250, '贾谊': 27, '屈原': 12, '李华': 2506, '刘向 撰': 41, '西晋·李密': 382}
DYN = {'公羊高': ('战国', '先秦'), '谷梁赤': ('战国', '先秦'), '李斯': ('秦', '秦汉'), '刘恒': ('汉', '秦汉'), '刘启': ('汉', '秦汉'),
       '晁错': ('汉', '秦汉'), '路温舒': ('汉', '秦汉'), '刘秀': ('东汉', '秦汉'), '邹阳': ('汉', '秦汉'), '诸葛亮': ('三国', '魏晋南北朝'),
       '陶渊明': ('魏晋', '魏晋南北朝'), '孔稚珪': ('南北朝', '魏晋南北朝')}
W = q('select id,author,author_id from works where book=?', BOOK)
src_ids = {int(w['author_id']) for w in W}
stmts = []; moves = {}; fixes = []
for w in W:
    a, aid = w['author'], int(w['author_id'])
    if a == '佚名': continue
    tgt = OVR.get(a)
    if tgt is None and a not in DYN:
        c = q("select id,dynasty,works from authors where name=? and dynasty<>'清' order by works+0 desc", a)
        c = [x for x in c if int(x['id']) not in src_ids]
        if c: tgt = int(c[0]['id'])
    if tgt and tgt != aid:
        d = q('select dynasty,era from authors where id=?', tgt)[0]
        moves.setdefault((aid, a), tgt)
        stmts.append(('update works set author_id=?, dynasty=? where id=?', [tgt, d['dynasty'], int(w['id'])]))
    elif a in DYN:
        fixes.append((aid, a))
for aid, a in set(fixes):
    dy, er = DYN[a]
    stmts.append(('update authors set dynasty=?, era=? where id=?', [dy, er, aid]))
    stmts.append(('update works set dynasty=? where author_id=? and book=?', [dy, aid, BOOK]))
for (aid, a), t in sorted(moves.items()): print('move', aid, a, '->', t)
for aid, a in sorted(set(fixes)): print('fix', aid, a, DYN[a])
print('stmts', len(stmts))
if DRY: sys.exit()
for i in range(0, len(stmts), 100): run(stmts[i:i + 100])
ids = sorted({aid for aid, _ in moves} | {t for t in moves.values()})
run([('update authors set works=(select count(*) from works w where w.author_id=authors.id) where id in (%s)' % ','.join(map(str, ids)), [])])
gone = [int(x['id']) for x in q('select id from authors a where id in (%s) and not exists(select 1 from works w where w.author_id=a.id)' % ','.join(map(str, ids)))]
if gone:
    run([('delete from authors where id in (%s)' % ','.join(map(str, gone)), [])])
n = q('select count(*) n from authors')[0]['n']; run([("update meta set v=? where k='authors'", [n])])
print('deleted authors', gone, 'authors now', n)
