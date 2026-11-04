#!/usr/bin/env bash
# =============================================================
# rotate-ethos-remote.sh — 一次性把 SG 后端 .env 的 ETHOS_AUTH_SECRET
# 强制替换为新值，并重建 backend / gfcc-kernel 使新钥生效。
#
# 背景：deploy.yml 的 bootstrap 用 seed_kv，语义是「仅当键缺失才写，
#       永不覆盖」，所以改 GH secret 不会影响机器上的既有值。换钥必须
#       走这个显式覆盖通道。
#
# 参数：$1 = 期望的值哈希前 16 位（写完立即自校验，不符则回滚）
#       $2 = 新钥文件路径（64 位十六进制，允许尾部换行）
#
# 安全：全程不打印密钥明文，只打印长度与 sha256 前 16 位；
#       失败时用备份回滚 .env，不留半改状态。
# =============================================================
set -euo pipefail

EXPECT="${1:-}"
KEYFILE="${2:-/tmp/ethos_new.key}"
ENVF="${ENVF:-/opt/looma-zervi/backend/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/looma-zervi/docker/docker-compose.yml}"
PROJECT="${PROJECT:-looma-zervi}"

fail() { echo "REFUSE: $*"; exit 1; }

[ -f "$KEYFILE" ] || fail "key file missing: $KEYFILE"
[ -f "$ENVF" ] || fail "env file missing: $ENVF"

NEW=$(tr -d '\r\n' < "$KEYFILE")
[ "${#NEW}" -eq 64 ] || fail "key length ${#NEW} != 64"
case "$NEW" in *[!0-9a-f]*) fail "key is not lowercase hex" ;; esac

hash_of() { printf '%s' "$1" | sha256sum | cut -c1-16; }
read_key() {
  sed -n 's/^ETHOS_AUTH_SECRET=//p' "$1" | head -1 | tr -d '"' | tr -d "'" | tr -d ' '
}

echo "===== 0. 变更前 ====="
OLD=$(read_key "$ENVF")
echo "old_len=${#OLD} old_hash=$(hash_of "$OLD")"
echo "new_len=${#NEW} new_hash=$(hash_of "$NEW")"
echo "expect=${EXPECT:-<unset>}"

BK="/root/ethos-backup-sg-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BK"
cp -a "$ENVF" "$BK/backend.env"
chmod 600 "$BK/backend.env"
echo "backup=$BK"

echo "===== 1. 写入 ====="
if grep -q '^ETHOS_AUTH_SECRET=' "$ENVF"; then
  sed -i "s|^ETHOS_AUTH_SECRET=.*|ETHOS_AUTH_SECRET=${NEW}|" "$ENVF"
  echo "mode=replace"
else
  printf 'ETHOS_AUTH_SECRET=%s\n' "$NEW" >> "$ENVF"
  echo "mode=append"
fi

NOW=$(read_key "$ENVF")
if [ -n "$EXPECT" ] && [ "$(hash_of "$NOW")" != "$EXPECT" ]; then
  echo "REFUSE: written hash $(hash_of "$NOW") != expect $EXPECT -> rollback"
  cp -a "$BK/backend.env" "$ENVF"
  exit 1
fi
echo "written_len=${#NOW} written_hash=$(hash_of "$NOW")"

echo "===== 2. 镜像预检 ====="
IMG=$(sed -n 's/^GFCC_KERNEL_IMAGE=//p' "$ENVF" | head -1 | tr -d '"' | tr -d "'")
echo "kernel_image=${IMG:-<unset>}"
if [ -n "$IMG" ]; then
  docker image inspect "$IMG" >/dev/null 2>&1 || fail "image missing locally: $IMG"
  echo "image_present=YES"
fi

echo "===== 3. 重建 backend 与 gfcc-kernel ====="
COMPOSE="docker compose --env-file $ENVF -f $COMPOSE_FILE -p $PROJECT"
$COMPOSE up -d --no-deps --no-build --force-recreate gfcc-kernel backend 2>&1 | tail -8
sleep 12

B=$(docker ps --format '{{.Names}}' | grep -E 'looma-backend' | head -1)
K=$(docker ps --format '{{.Names}}' | grep -iE 'gfcc[_-]kernel' | head -1)
echo "backend_container=${B:-<none>} kernel_container=${K:-<none>}"
[ -n "$B" ] || fail "backend container not running after recreate"

echo "===== 4. 生效核验 ====="
BV=$(docker exec "$B" printenv ETHOS_AUTH_SECRET 2>/dev/null | tr -d '\r\n')
echo "backend_env_len=${#BV} backend_env_hash=$(hash_of "$BV")"
if [ -n "$K" ]; then
  KV=$(docker exec "$K" printenv ETHOS_AUTH_SECRET 2>/dev/null | tr -d '\r\n')
  echo "kernel_env_len=${#KV} kernel_env_hash=$(hash_of "$KV")"
  [ "$(hash_of "$BV")" = "$(hash_of "$KV")" ] && echo "hash_equal=YES" || echo "hash_equal=NO"
fi
echo "anon_me=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:5211/circle/api/me)"
echo "kernel_health=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:5211/health)"
echo "backend_health=$(docker exec "$B" curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:5200/health 2>/dev/null || echo n/a)"

rm -f "$KEYFILE"
echo "key_cleaned=YES"
echo "DONE"
