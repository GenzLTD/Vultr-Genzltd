#!/usr/bin/env sh
# =============================================================
# bootstrap-env.sh — deploy 第 2 步（在目标机执行）
#
#   .env 首次生成；随后：
#     set_kv  非密钥每轮对齐
#     seed_kv 密钥只在缺失时写（#19）——防把机器上的 Live 验签打回旧值
#
#   先于 rsync。不覆盖已有密钥。
# =============================================================
set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/opt/looma-zervi}"
STACK_DIR="${STACK_DIR:-/opt/vultr-genzltd-stack}"
ENV_FILE="${ENV_FILE:-$DEPLOY_PATH/backend/.env}"
export ENV_FILE

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/env-kv.sh"

mkdir -p "$DEPLOY_PATH/backend" "$DEPLOY_PATH/data/poetry_full" "$DEPLOY_PATH/data/chroma_models" \
         "$DEPLOY_PATH/logs" "$STACK_DIR/releases" "$STACK_DIR/scripts" \
         /var/www/saas/dist

if [ ! -f "$ENV_FILE" ]; then
  echo "=== 首次生成 $ENV_FILE ==="
  umask 077
  : > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
else
  echo "=== $ENV_FILE 已存在，只做 set_kv / seed_kv ==="
fi

# ---- 每轮对齐（无秘密）----
set_kv FLASK_ENV production
set_kv FLASK_PORT 5200
set_kv WECHAT_DEV_MODE false
set_kv PAYMENT_STUB_MODE false
set_kv DATABASE_PATH /app/data/looma.db
set_kv POETRY_CHROMA_PATH /app/poetry_data
set_kv CHROMA_MODE remote
set_kv CHROMA_HOST chromadb
set_kv CHROMA_PORT 8000
set_kv RATE_LIMIT_STORAGE_URI redis://redis:6379/1
set_kv DEPLOY_REGION SG
set_kv CORS_ORIGINS "${CORS_ORIGINS:-https://genz.ltd,https://www.genz.ltd,https://tspace.genz.ltd,https://api.genz.ltd,https://app.genz.ltd,https://tspace.szbolent.cn}"
set_kv GOOGLE_REDIRECT_URI "${GOOGLE_REDIRECT_URI:-https://api.genz.ltd/v1/auth/google/callback}"
set_kv DEEPSEEK_BASE_URL https://api.deepseek.com/v1
set_kv DEEPSEEK_MODEL deepseek-chat
set_kv LLM_PROVIDER_ORDER deepseek,openai,ollama
set_kv QCC_ENABLED true
set_kv QCC_MCP_BASE_URL "${QCC_MCP_BASE_URL:-http://1.14.202.161:8998/mcp}"
set_kv STRIPE_SUCCESS_URL https://tspace.genz.ltd/pricing?status=success
set_kv STRIPE_CANCEL_URL https://tspace.genz.ltd/pricing?status=cancel

# ---- 仅缺失时写（密钥；机器是权威）----
seed_kv JWT_SECRET "${JWT_SECRET:-}"
seed_kv DEEPSEEK_API_KEY "${DEEPSEEK_API_KEY:-}"
seed_kv OPENAI_API_KEY "${OPENAI_API_KEY:-}"
seed_kv QCC_AUTH_TOKEN "${QCC_AUTH_TOKEN:-}"
seed_kv GOOGLE_CLIENT_ID "${GOOGLE_CLIENT_ID:-}"
seed_kv GOOGLE_CLIENT_SECRET "${GOOGLE_CLIENT_SECRET:-}"
seed_kv STRIPE_SECRET_KEY "${STRIPE_SECRET_KEY:-}"
seed_kv STRIPE_WEBHOOK_SECRET "${STRIPE_WEBHOOK_SECRET:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo "REFUSE: 目标机没有 docker" >&2
  exit 1
fi

echo "=== bootstrap-env 完成（密钥未被覆盖）==="
