# v36 作者同人异名归一：仓库 9cee5450 → 站点重建 → 部署
set -e
cd "$(dirname "$0")/.."
export REPO_READ=/tmp/cc/chinese-classics
pip install -q opencc numpy tencentcloud-sdk-python-teo >/dev/null 2>&1 || true
rm -f /tmp/repo_cache.pkl build/consist/unpaired.json
echo "== canon $(date +%T)"; CANON_STRICT=1 python3 -u tools/canon.py > build/consist/canon3.log 2>&1 || { tail -20 build/consist/canon3.log; exit 1; }
grep -v '^XNEAR\|^ADD\|^LOOSE' build/consist/canon3.log | tail -8
echo "== emit $(date +%T)"; python3 -u tools/emit.py 2>&1 | tail -3
echo "== cats $(date +%T)"; python3 -u tools/cats.py 2>&1 | tail -2
echo "== index $(date +%T)"; python3 -u tools/index.py 2>&1 | tail -2
echo "== said $(date +%T)"; python3 -u tools/said_build.py 2>&1 | tail -3
echo "== moved $(date +%T)"; python3 -u tools/moved.py 2>&1 | tail -2
sed -i "s/const DV = 'v=15'/const DV = 'v=16'/" app/site/app.js
sed -i "s/shici-shell-v35/shici-shell-v36/; s/shici-data-v15/shici-data-v16/" app/site/sw.js
sed -i "s/app.js?v=33/app.js?v=34/g" app/site/index.html app/site/sw.js
echo "== deploy $(date +%T)"
cd app && rm -f /tmp/app.zip && zip -qr -1 /tmp/app.zip . -x 'node_modules/*' '.edgeone/*' '.env' && cd ..
npx -y edgeone@latest makers deploy /tmp/app.zip -n shijian -a global --skip-ai-gateway-sync -t "$EDGEONE_API_TOKEN" > deploy-run.txt 2>&1 || true
grep -E "Deployment ID|Deploy Success|rror" deploy-run.txt | tail -4
python3 -c "
import sys;sys.path.insert(0,'tools');import teo;print(teo.call('CreatePurgeTask',{'ZoneId':'zone-3uu4zgt2ynxe','Type':'purge_host','Targets':['shijian.jisu.cn']})['Response'].get('JobId'))"
echo "$(date '+%F %T') v36 作者归一 $(grep -o 'Deployment ID[^ ]* *[a-z0-9]*' deploy-run.txt | tail -1)" >> deploy.log
echo "== done $(date +%T)"
