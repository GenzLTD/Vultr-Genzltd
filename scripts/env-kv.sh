#!/usr/bin/env sh
# =============================================================
# env-kv.sh — .env 双写策略（照 overseas 管线 + #19 seed_kv）
#
#   set_kv  非密钥配置，每轮对齐（空值跳过）
#   seed_kv 密钥 / 运行时真值，仅当键缺失时写，永不覆盖
#
#   用法（在已 export ENV_FILE 的环境里）:
#     . scripts/env-kv.sh
#     set_kv DEPLOY_REGION SG
#     seed_kv STRIPE_WEBHOOK_SECRET "$STRIPE_WEBHOOK_SECRET"
# =============================================================

set_kv() {
  _key="$1"
  _val="$2"
  [ -n "$_val" ] || return 0
  [ -n "${ENV_FILE:-}" ] || { echo "ENV_FILE unset" >&2; return 1; }
  if grep -q "^${_key}=" "$ENV_FILE" 2>/dev/null; then
    awk -v key="$_key" -v val="$_val" '
      BEGIN { done=0 }
      index($0, key "=")==1 { print key "=" val; done=1; next }
      { print }
      END { if (!done) print key "=" val }
    ' "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$_key" "$_val" >> "$ENV_FILE"
  fi
}

seed_kv() {
  _key="$1"
  _val="$2"
  [ -n "$_val" ] || return 0
  [ -n "${ENV_FILE:-}" ] || { echo "ENV_FILE unset" >&2; return 1; }
  grep -q "^${_key}=" "$ENV_FILE" 2>/dev/null && return 0
  printf '%s=%s\n' "$_key" "$_val" >> "$ENV_FILE"
}
