set -e
cd "$(dirname "$0")/.."
pip install -q opencc >/dev/null 2>&1 || true
[ -d /tmp/cc/chinese-classics ] || (mkdir -p /tmp/cc && git clone -q --depth 1 https://github.com/wujinpai/chinese-classics.git /tmp/cc/chinese-classics)
(cd /tmp/cc/chinese-classics && git log --oneline | head -1)
python3 -u tools/api_sync.py apply 2>&1 | tail -4
cat build/consist/api_sync_progress.json
