#!/bin/bash
# 诗笺部署（v43 起的标准脚本，取代 v36_site.sh）。
# 流程：版本应用 → sitemap 生成 → 压缩 app.js/app.css（尽力而为，失败不阻断）
#      → 打包（zip 在仓库内 .deploy-tmp/，/tmp 只有 512MB 装不下）→ Makers 部署（失败即退出，不吞错）→ 清 CDN 缓存。
# 用法：EDGEONE_API_TOKEN=xxx bash tools/deploy.sh
#   发新版前先跑 python3 tools/bump.py --inc 升版本号；只改文案/修 bug 可直接部署。
set -e
cd "$(dirname "$0")/.."
export EDGEONE_PAGES_API_REGION=china
echo "== versions $(date +%T)"; python3 tools/bump.py
echo "== sitemap $(date +%T)"; python3 tools/sitemap.py
WORK="$PWD/.deploy-tmp"; mkdir -p "$WORK/site"
trap 'rm -rf "$WORK"' EXIT
MIN_OK=1
if npx -y terser app/site/app.js -c -m -o "$WORK/site/app.js" 2>/dev/null && node --check "$WORK/site/app.js"; then
  echo "minified app.js"
else echo "WARN: terser failed, shipping unminified app.js"; MIN_OK=0; fi
if npx -y clean-css-cli -o "$WORK/site/app.css" app/site/app.css 2>/dev/null; then
  echo "minified app.css"
else echo "WARN: clean-css failed, shipping unminified app.css"; MIN_OK=0; fi
ZIP="$WORK/app.zip"; rm -f "$ZIP"
if [ "$MIN_OK" = 1 ]; then
  (cd app && zip -qr -1 "$ZIP" . -x 'node_modules/*' '.edgeone/*' '.env' 'site/app.js' 'site/app.css')
  (cd "$WORK" && zip -qr "$ZIP" site/app.js site/app.css)
else
  (cd app && zip -qr -1 "$ZIP" . -x 'node_modules/*' '.edgeone/*' '.env')
fi
ls -la "$ZIP"
echo "== deploy $(date +%T)"
npx -y edgeone@latest makers deploy "$ZIP" -n shijian -a global --skip-ai-gateway-sync -t "$EDGEONE_API_TOKEN" 2>&1 | tee deploy-run.txt
grep -E "Deployment ID|Deploy Success|rror" deploy-run.txt | tail -4
python3 -c "
import sys;sys.path.insert(0,'tools');import teo;print(teo.call('CreatePurgeTask',{'ZoneId':'zone-3uu4zgt2ynxe','Type':'purge_host','Targets':['shijian.jisu.cn']})['Response'].get('JobId'))"
echo "$(date '+%F %T') deploy $(grep -o 'Deployment ID[^ ]* *[a-z0-9]*' deploy-run.txt | tail -1)" >> deploy.log
echo "== done $(date +%T)"
