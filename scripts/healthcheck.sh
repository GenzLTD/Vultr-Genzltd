#!/usr/bin/env bash
# =============================================================
# healthcheck.sh — 健康检查（在目标机上执行，退出码即门禁）
#
#   照 szbolent-cn 的实践：
#     - 每项都带有限重试，容忍容器启动时间（默认 12 次 × 5s = 60s）
#     - 任一项失败 → 退出码非 0 → CI 判失败
#
#   本机专属断言：端口收内网（不得出现 0.0.0.0:5200/6379/8000）
#
#   用法: bash scripts/healthcheck.sh
# =============================================================
set -uo pipefail
fail=0

# check <名称> <命令/函数名> [重试次数=12] [间隔秒=5]
check() {
  local name="$1" cmd="$2" tries="${3:-12}" delay="${4:-5}" i=1
  while [ "$i" -le "$tries" ]; do
    if eval "$cmd" >/dev/null 2>&1; then
      printf '  \033[32m✓\033[0m %s\n' "$name"
      return 0
    fi
    [ "$i" -lt "$tries" ] && sleep "$delay"
    i=$((i + 1))
  done
  printf '  \033[31m✗\033[0m %s（重试 %s 次仍失败）\n' "$name" "$tries"
  fail=1
}

# 端口收内网：不得有任何 0.0.0.0 发布的业务端口
ports_are_loopback_only() {
  local bad
  bad="$(docker ps --format '{{.Names}}|{{.Ports}}' | grep -E '0\.0\.0\.0:(5200|6379|8000)' || true)"
  [ -z "$bad" ]
}

# redis / chromadb / backend 均应处于 running
container_running() {
  [ "$(docker inspect -f '{{.State.Status}}' "$1" 2>/dev/null)" = "running" ]
}

printf '\033[1m=== 健康检查 ===\033[0m\n'

# --- 链路 ---
check "宿主 nginx :80 → /health（经 Host: api.genz.ltd）" \
      'curl -sf -o /dev/null -H "Host: api.genz.ltd" http://127.0.0.1/health'
check "backend :5200 直连 /health" \
      'curl -sf -o /dev/null http://127.0.0.1:5200/health'
check "redis 应答 PONG" \
      'docker exec looma-redis redis-cli ping | grep -q PONG'

# --- 容器 ---
check "容器 looma-backend running"  'container_running looma-backend'
check "容器 looma-redis running"    'container_running looma-redis'
check "容器 looma-chromadb running" 'container_running looma-chromadb'

# --- 安全断言（本次变更的核心目的）---
check "端口收内网：无 0.0.0.0:5200/6379/8000" 'ports_are_loopback_only'

if [ "$fail" -eq 0 ]; then
  printf '\033[32m=== 全部健康 ===\033[0m\n'
else
  printf '\033[31m=== 有服务异常 ===\033[0m\n'
fi
exit "$fail"
