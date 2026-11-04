#!/usr/bin/env bash
# =============================================================
# rotate-ethos-remote.sh — 一次性把后端 .env 的 ETHOS_AUTH_SECRET
# 强制替换为新值，并重建 backend / gfcc-kernel 使新钥生效。
# 机上若存在 /data/gfcc（GFCC AM 形态），同步覆盖 /data/gfcc/.env 并
# recreate am-gateway（issue #73：漏它会让 gateway 继续持旧钥拒新 token）。
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

BK="${BK_ROOT:-/root}/ethos-backup-sg-$(date +%Y%m%d-%H%M%S)"
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

echo "===== 3b. GFCC AM gateway（幂等：无 /data/gfcc 则跳过） ====="
# 背景（issue #73）：am-gateway 的 compose 用 /data/gfcc/.env 插值建容器；
# 只换 kernel/.env 与 backend 会让 gateway 继续持旧钥 —— 新钥 token 打
# gateway 直接 401。此处同步该文件并 recreate，使「换钥即全站生效」。
GFCC_ENV="${GFCC_ENV:-/data/gfcc/.env}"
GFCC_DIR="$(dirname "$GFCC_ENV")"
if [ ! -f "$GFCC_ENV" ]; then
  echo "gfcc_env=absent (skip gateway sync)"
else
  cp -a "$GFCC_ENV" "$BK/gfcc.env"
  chmod 600 "$BK/gfcc.env"
  if grep -q '^ETHOS_AUTH_SECRET=' "$GFCC_ENV"; then
    sed -i "s|^ETHOS_AUTH_SECRET=.*|ETHOS_AUTH_SECRET=${NEW}|" "$GFCC_ENV"
    echo "gfcc_env_mode=replace"
  else
    printf 'ETHOS_AUTH_SECRET=%s\n' "$NEW" >> "$GFCC_ENV"
    echo "gfcc_env_mode=append"
  fi
  GV=$(read_key "$GFCC_ENV")
  if [ "$(hash_of "$GV")" != "$(hash_of "$NEW")" ]; then
    cp -a "$BK/gfcc.env" "$GFCC_ENV"
    fail "gfcc .env written hash $(hash_of "$GV") != new -> rolled back"
  fi
  echo "gfcc_env_hash=$(hash_of "$GV")"

  GW=$(docker ps -a --format '{{.Names}}' | grep -E '^gfcc-am-gateway' | head -1 || true)
  if [ -z "$GW" ]; then
    echo "am_gateway=absent (env written; nothing to recreate)"
  else
    if ! (cd "$GFCC_DIR" && docker compose up -d --no-deps --force-recreate am-gateway 2>&1 | tail -3); then
      cp -a "$BK/gfcc.env" "$GFCC_ENV"
      fail "am-gateway recreate failed -> gfcc .env rolled back"
    fi
    sleep 6
    GW=$(docker ps --format '{{.Names}}' | grep -E '^gfcc-am-gateway' | head -1 || true)
    [ -n "$GW" ] || fail "am-gateway not running after recreate"
    WV=$(docker exec "$GW" printenv ETHOS_AUTH_SECRET 2>/dev/null | tr -d '\r\n')
    echo "gateway_env_len=${#WV} gateway_env_hash=$(hash_of "$WV")"
    if [ "$(hash_of "$WV")" != "$(hash_of "$NEW")" ]; then
      cp -a "$BK/gfcc.env" "$GFCC_ENV"
      (cd "$GFCC_DIR" && docker compose up -d --no-deps --force-recreate am-gateway >/dev/null 2>&1 || true)
      fail "gateway still holds old key -> gfcc .env rolled back + gateway recreated"
    fi
    echo "gateway_hash_equal=YES"

    # 生效复验：新钥应过鉴权（404/200），旧钥应 401。
    # 铸 HS256 探针 token（10 分钟、sub=rotate-probe），无 python3 则跳过本项。
    if command -v python3 >/dev/null 2>&1; then
      OLDK=$(read_key "$BK/gfcc.env")
      PROBE=$(python3 - "$NEW" "$OLDK" <<'PY'
import base64, hashlib, hmac, json, sys, time
def b64(raw): return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
def mint(sec):
    now = int(time.time())
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    p = b64(json.dumps({"sub": "rotate-probe", "tier": "pro", "iat": now, "exp": now + 600}, separators=(",", ":")).encode())
    s = b64(hmac.new(sec.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + s
print(mint(sys.argv[1])); print(mint(sys.argv[2]))
PY
) || PROBE=""
      NEWTOK=$(printf '%s' "$PROBE" | sed -n '1p')
      OLDTOK=$(printf '%s' "$PROBE" | sed -n '2p')
      # 端口映射可能是 127.0.0.1 / 0.0.0.0 / [::]（天翼即 0.0.0.0:3210）；
      # grep 无匹配 exit 1 会在 set -e -o pipefail 下杀掉脚本，必须兜底。
      GWPORT=$(docker port "$GW" 2>/dev/null | grep -oE '(127\.0\.0\.1|0\.0\.0\.0|\[::\]):[0-9]+' | head -1 | grep -oE '[0-9]+$' || true)
      if [ -n "$NEWTOK" ] && [ -n "$OLDTOK" ] && [ -n "$GWPORT" ]; then
        C_NEW=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 -H "Authorization: Bearer $NEWTOK" "http://127.0.0.1:${GWPORT}/v1/memory/health")
        C_OLD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 -H "Authorization: Bearer $OLDTOK" "http://127.0.0.1:${GWPORT}/v1/memory/health")
        echo "gateway_probe new=$C_NEW old=$C_OLD (want new!=401, old=401)"
        case "$C_NEW" in 401) fail "gateway rejects NEW key (got 401)" ;; esac
        [ "$C_OLD" = "401" ] || echo "WARN: old key not rejected (got $C_OLD) — 共钥过渡期可接受，请人工复核"
      else
        echo "gateway_probe=skipped (no python3 token or port mapping)"
      fi
    else
      echo "gateway_probe=skipped (no python3)"
    fi
  fi
fi

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
