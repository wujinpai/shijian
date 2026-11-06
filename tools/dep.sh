set -e
cd /workspace/projects/d6a0e27a-ed6d-41d5-9b29-1ad9cc158e03/shici
cd app && rm -f /tmp/app.zip && zip -qr -1 /tmp/app.zip . -x 'node_modules/*' '.edgeone/*' '.env' && cd ..
ls -la /tmp/app.zip
timeout 1100 npx -y edgeone@latest makers deploy /tmp/app.zip -n shijian -a global --skip-ai-gateway-sync -t "$EDGEONE_API_TOKEN" > deploy-run.txt 2>&1 || true
grep -E "Deployment ID|Deploy Success|rror|failed" deploy-run.txt | tail -4
