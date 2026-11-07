#!/bin/bash
# 旧部署脚本（v43 起请用 tools/deploy.sh：含版本应用、sitemap 生成、压缩、失败即退出）。
# 仅保留作备用；注意：部署失败不再被 || true 吞掉。
set -e
cd "$(dirname "$0")/.."
cd app && rm -f /tmp/app.zip && zip -qr -1 /tmp/app.zip . -x 'node_modules/*' '.edgeone/*' '.env' && cd ..
ls -la /tmp/app.zip
timeout 1100 npx -y edgeone@latest makers deploy /tmp/app.zip -n shijian -a global --skip-ai-gateway-sync -t "$EDGEONE_API_TOKEN" > deploy-run.txt 2>&1
grep -E "Deployment ID|Deploy Success|rror|failed" deploy-run.txt | tail -4
