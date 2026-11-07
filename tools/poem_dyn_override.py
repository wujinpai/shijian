# 逐首朝代覆盖表（v45）：防止 turso_build / api_sync 下次重建时把已修正的朝代改回去。
# 数据文件 tools/poem_dyn_override.json 由 tools/gen_poem_dyn_override.py 从
# build/consist/v45-unify-plan2.json 生成（1,972 首，全文配对验证与站点一致）。
# 键为 (gn(作者), 标题, sha1(nz(全文))[:16])；nz 自包含（去非汉字 + 异体归一），
# 不依赖 opencc，与生成脚本共用同一函数——生成与应用必须用同一 nz，否则哈希对不上。
import json, os, re, hashlib

STDV = dict(zip('隠浄頼玨嵒閴謩鼇箎僊瓌雝靁磵逈眘葊檝譡', '隐净赖珏岩阒谟鳌篪仙瑰雍雷涧迥昚庵楫谠'))
_N = re.compile(r'[^\u3400-\u9fff\U00020000-\U0003134f]')

def nz(x):
    return _N.sub('', x or '').translate(str.maketrans(STDV))

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'poem_dyn_override.json')

def _load():
    try:
        data = json.load(open(_PATH, encoding='utf-8'))
    except FileNotFoundError:
        return {}
    return {(e['a'], e['t'], e['h']): (e['d'], e.get('e')) for e in data}

OVERRIDE = _load()

def apply_override(author, title, dynasty, era, content):
    """命中则返回 (目标朝代, 目标 era)；未命中原样返回。
    era 只在条目带 e 时才改（修正时 era 随 dynasty 走的那些首）。"""
    from dyn_norm import gn
    h = hashlib.sha1(nz(content or '').encode()).hexdigest()[:16]
    hit = OVERRIDE.get((gn(author), title, h))
    if not hit:
        return dynasty, era
    d, e = hit
    return d, (e if e else era)
