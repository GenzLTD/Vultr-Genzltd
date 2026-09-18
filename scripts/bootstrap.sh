#!/usr/bin/env bash
# =============================================================
# bootstrap.sh — 首次初始化（新机器一次性，幂等可重复跑）
#
#   只做「建目录 + 体检」，不改防火墙、不改服务。
#   ufw 规则属变更集，必须走 dryrun + 授权，不在这里偷改。
# =============================================================
set -euo pipefail

# 本地 clone：默认就是本仓。生产机由 CI 传入 DEPLOY_PATH=/opt/looma-zervi。
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_PATH="${DEPLOY_PATH:-$ROOT}"

echo "[bootstrap] 体检本仓布局（不创建 /var/www/genz-web，营销站不在本机）..."
mkdir -p \
  "$DEPLOY_PATH/backend" \
  "$DEPLOY_PATH/docker" \
  "$DEPLOY_PATH/data/poetry_full" \
  "$DEPLOY_PATH/data/chroma_models"
ls -d "$DEPLOY_PATH" "$DEPLOY_PATH/backend" "$DEPLOY_PATH/docker" "$DEPLOY_PATH/nginx" 2>/dev/null

echo "[bootstrap] 容器运行时:"
if command -v docker >/dev/null 2>&1; then
  docker --version
  docker compose version 2>/dev/null || echo "  ⚠️ 缺少 docker compose 插件"
else
  echo "  ⚠️ 未找到 docker CLI"
fi

echo "[bootstrap] nginx:"
if command -v nginx >/dev/null 2>&1; then nginx -v 2>&1; else echo "  ⚠️ 未找到 nginx"; fi

echo "[bootstrap] 防火墙现状（只读，不修改）:"
if command -v ufw >/dev/null 2>&1; then
  ufw status | sed 's/^/  /'
  echo "  提示: 443 是否放行取决于 Cloudflare 回源模式，属待决事项（见 CATALOG.md §四）。"
else
  echo "  无 ufw"
fi

echo "[bootstrap] 完成。部署由 CI 执行；环境变量由 scripts/seed-env.sh 仅首次种入。"
