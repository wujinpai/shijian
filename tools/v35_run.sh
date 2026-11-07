# v35 统一：从 GitHub 拉干净仓库(1648f126) → 计划 → 改仓库 → 站点 canon（报站点独有）→ 补进仓库 → 通行本文字回写仓库 → 再 canon 校验
set -e
cd "$(dirname "$0")/.."
pip install -q opencc >/dev/null 2>&1 || true
if [ "$FRESH" = 1 ] || [ ! -d /tmp/cc/chinese-classics ]; then rm -rf /tmp/cc && mkdir -p /tmp/cc && git clone -q --depth 3 https://github.com/wujinpai/chinese-classics.git /tmp/cc/chinese-classics; (cd /tmp/cc/chinese-classics && git checkout -q 1648f126); rm -f /tmp/repo_cache.pkl; fi
[ "$PLAN" = 1 ] && python3 -u tools/repo_canon.py plan | grep -v '^MV\|^RN'
[ "$NOAPPLY" = 1 ] || python3 -u tools/repo_canon.py apply
rm -f build/consist/textfix.json build/consist/unpaired.json
CANON_STRICT=1 python3 -u tools/canon.py > build/consist/canon.log 2>&1 || true
grep -v '^XNEAR\|^ADD\|^LOOSE' build/consist/canon.log
[ -f build/consist/unpaired.json ] && python3 -u tools/repo_canon.py addsite && CANON_STRICT=1 python3 -u tools/canon.py > build/consist/canon.log 2>&1
python3 -u tools/repo_canon.py textfix
CANON_STRICT=1 python3 -u tools/canon.py > build/consist/canon2.log 2>&1
grep -v '^XNEAR\|^ADD\|^LOOSE' build/consist/canon2.log
