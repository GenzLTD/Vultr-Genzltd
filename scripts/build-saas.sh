#!/usr/bin/env sh
# =============================================================
# build-saas.sh — 打 tspace dist（与 CI saas-build 同口径）
#
#   VITE_API_BASE=""     → 浏览器走同源 /v1（nginx tspace 反代）
#   VITE_DEPLOY_REGION=SG
#   产物: frontend/packages/saas/dist
# =============================================================
set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm missing. Enable corepack: corepack enable && corepack prepare pnpm@9.15.4 --activate" >&2
  exit 1
fi

if [ -f pnpm-lock.yaml ]; then
  pnpm install --frozen-lockfile
else
  pnpm install
fi

export VITE_API_BASE="${VITE_API_BASE-}"
export VITE_DEPLOY_REGION="${VITE_DEPLOY_REGION:-SG}"
pnpm --filter @looma/saas build

DIST="$ROOT/frontend/packages/saas/dist"
if [ ! -f "$DIST/index.html" ]; then
  echo "REFUSE: $DIST/index.html missing" >&2
  exit 1
fi
echo "OK saas dist → $DIST"
