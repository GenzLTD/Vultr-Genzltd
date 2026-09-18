#!/usr/bin/env bash
# =============================================================
# plan.sh — 真机现状比对（**严格只读**，不写任何东西）
#
#   用途：动真机之前/之后，都能一眼看出「机器与期望差在哪」。
#   本脚本只执行 cat/md5sum/grep/docker ps/ufw status 之类读操作，
#   不含任何写命令，可安全在授权前后反复跑。
#
#   用法: bash scripts/plan.sh [ssh目标]      # 默认 vultr-overseas
# =============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-vultr-overseas}"
DEPLOY_PATH="/opt/looma-zervi"

BASE_COMPOSE_MD5="8aace57b5c757e70a5298add5534ef6f"
BASE_NGINX_MD5="0f505e33f8fb047f4185689b89e4c256"
md5of() { if command -v md5 >/dev/null 2>&1; then md5 -q "$1"; else md5sum "$1" | cut -d' ' -f1; fi; }

NEW_COMPOSE_MD5="$(md5of "$ROOT/compose/docker-compose.yml")"
NEW_NGINX_MD5="$(md5of "$ROOT/nginx/nginx.conf")"

printf '\033[1m=== 真机现状比对（只读） ===\033[0m\n目标: %s\n\n' "$TARGET"

ssh -o BatchMode=yes "$TARGET" "
  DP='$DEPLOY_PATH'
  echo '--- 期望值（本仓） ---'
  echo 'compose(变更后): $NEW_COMPOSE_MD5'
  echo 'compose(现网基线): $BASE_COMPOSE_MD5'
  echo 'nginx(基线):     $BASE_NGINX_MD5'
  echo
  echo '--- 机器实际 ---'
  printf 'compose: '; md5sum \${DP}/docker/docker-compose.yml 2>/dev/null | cut -d' ' -f1
  printf 'nginx:   '; md5sum /etc/nginx/nginx.conf 2>/dev/null | cut -d' ' -f1
  echo
  echo '--- 端口发布现状 ---'
  docker ps --format '{{.Names}}|{{.Ports}}'
  echo
  echo '--- ufw ---'
  ufw status 2>/dev/null | head -10
  echo
  echo '--- .env 指纹（不打印明文）---'
  E=\${DP}/backend/.env
  printf 'keys=%s ' \"\$(grep -cE '^[A-Z_0-9]+=' \$E 2>/dev/null)\"
  printf 'sha256_12=%s ' \"\$(sha256sum \$E 2>/dev/null | cut -c1-12)\"
  stat -c 'mtime=%y' \$E 2>/dev/null
  echo
  echo '--- /health ---'
  curl -s -o /dev/null -w 'http=%{http_code}\n' https://api.genz.ltd/health 2>/dev/null || echo 'http=（不可达）'
"
