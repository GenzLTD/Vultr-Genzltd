#!/usr/bin/env bash
# =============================================================
# seed-env.sh — 环境变量「仅首次种入」（照 szbolent-cn 的成功实践）
#
#   铁律：本脚本永不覆盖已存在的 .env。
#   这正是 looma-zervi 旧流程「每轮发版 set_kv 重写 ~20 个键」
#   造成密钥漂移的结构性解药。
#
#   真值来源（按优先级）:
#     1) 环境变量（CI 由 GitHub Secrets 注入，或运维手工 export）
#     2) 缺失即报错退出（绝不写占位符当真值）
#
#   默认写到本仓 backend/.env（本地 clone）。生产机再显式传入路径：
#     ENV_FILE=/opt/looma-zervi/backend/.env bash scripts/seed-env.sh
#     bash scripts/seed-env.sh --print-keys     # 只打印键清单，不写文件
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/backend/.env}"
MODE="${1:-}"

# 目标机 .env 的键清单（26 键，来自现网实测）
KEYS=(
  FLASK_ENV FLASK_PORT API_REQUEST_TIMEOUT
  DATABASE_PATH POETRY_CHROMA_PATH
  CHROMA_MODE CHROMA_HOST CHROMA_PORT
  RATE_LIMIT_STORAGE_URI
  CORS_ORIGINS DEPLOY_REGION
  JWT_SECRET
  GOOGLE_REDIRECT_URI
  DEEPSEEK_API_KEY DEEPSEEK_BASE_URL DEEPSEEK_MODEL LLM_PROVIDER_ORDER
  QCC_ENABLED QCC_AUTH_TOKEN QCC_MCP_BASE_URL
  PAYMENT_STUB_MODE WECHAT_DEV_MODE
  STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET STRIPE_SUCCESS_URL STRIPE_CANCEL_URL
)

if [ "$MODE" = "--print-keys" ]; then
  printf '%s\n' "${KEYS[@]}"
  exit 0
fi

if [ -f "$ENV_FILE" ]; then
  echo "⏭  $ENV_FILE 已存在，跳过（本脚本永不覆盖）"
  echo "   如需轮换单个键，请显式手工操作并留备份，不要用本脚本。"
  exit 0
fi

echo "=== 首次种入 $ENV_FILE ==="
missing=()
tmp="$(mktemp)"; chmod 600 "$tmp"

# 无默认值、必须由外部注入的键
for k in "${KEYS[@]}"; do
  v="${!k:-}"
  if [ -z "$v" ]; then missing+=("$k"); continue; fi
  printf '%s=%s\n' "$k" "$v" >> "$tmp"
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "❌ 缺少以下变量的值（拒绝写入占位符）:" >&2
  printf '   - %s\n' "${missing[@]}" >&2
  echo "   请在 CI Secrets 或运维环境里注入后重跑。" >&2
  rm -f "$tmp"
  exit 1
fi

install -m 600 "$tmp" "$ENV_FILE"
rm -f "$tmp"
echo "✅ 已写入（权限 600，$(grep -c '=' "$ENV_FILE") 个键）"
echo "   后续发版一律不动此文件。"
