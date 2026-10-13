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
#   业务冒烟（2026-10-12 加）：/health 只证明进程活着，不证明蓝图已注册。
#   故额外断言 membership 探针、关键模块在 url_map、路由总数较上一版的掉幅，以及
#   /health.git_commit 与本次发布写入的 git_commit.txt 一致。
#
#   用法: bash scripts/healthcheck.sh
#        SMOKE_DROP_PCT=2 DEPLOY_PATH=/opt/looma-zervi bash scripts/healthcheck.sh
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

# --- 业务冒烟 ---
# /health 只证明进程活着。若 app.py 未注册某个蓝图（历史上 rsync --delete
# 用旧 app.py 覆盖就发生过），/health 仍返回 200，但会员订阅、数据导出等
# 业务已静默消失：不报错、不回滚、难排查。下面几条专门覆盖这一类故障。

DEPLOY_PATH="${DEPLOY_PATH:-/opt/looma-zervi}"
STACK_DIR="${STACK_DIR:-/opt/vultr-genzltd-stack}"
# 路由总数基线：deploy.yml 在「重建容器之前」从旧进程抓取，写到
# $STACK_DIR/baselines/endpoint-count。
# 为什么不再用绝对下限（原 150）：预发实测摘掉整块 membership 后 183 → 178，
# 仍远高于 150，断言照过 —— 对这类故障没有区分度。有意义的是「比上一版掉了多少」。
BASELINE_FILE="${SMOKE_BASELINE_FILE:-$STACK_DIR/baselines/endpoint-count}"
SMOKE_DROP_PCT="${SMOKE_DROP_PCT:-2}"

# membership 蓝图注册探针：免鉴权端点，蓝图未注册时会 404 而非 401
membership_plans_ok() {
  curl -sf --max-time 10 -o /dev/null http://127.0.0.1:5200/v1/membership/plans
}

# 关键模块必须出现在 url_map 清单里（account 无免鉴权端点，只能查清单）
endpoints_modules_ok() {
  local body
  body="$(curl -sf --max-time 10 http://127.0.0.1:5200/v1/endpoints 2>/dev/null)"
  [ -n "$body" ] || return 1
  printf '%s' "$body" | grep -q '"membership"' || return 1
  printf '%s' "$body" | grep -q '"account"' || return 1
}

# 路由总数：与上一版比，掉幅超过 SMOKE_DROP_PCT% 才算失败。
# 缺蓝图这类故障主要由「模块名必须在 url_map 里」那条抓（更敏感），总数只做补充。
endpoints_count_ok() {
  local n base limit
  n="$(curl -sf --max-time 10 http://127.0.0.1:5200/v1/endpoints 2>/dev/null \
        | grep -oE '"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) ' | wc -l | tr -d ' ')"
  [ "${n:-0}" -gt 0 ] || return 1
  base="$(tr -d ' \t\n\r' < "$BASELINE_FILE")"
  case "$base" in ''|*[!0-9]*) return 0 ;; esac
  # 允许下降 SMOKE_DROP_PCT%（整数运算）：n*100 >= base*(100-pct)
  limit=$(( base * (100 - SMOKE_DROP_PCT) ))
  [ $(( n * 100 )) -ge "$limit" ]
}

# 跑的必须是本次发布的代码：backend 以卷挂载 ../backend:/app，
# /health.git_commit 读的就是部署时写入的 git_commit.txt。
# 不一致 = 容器没起来 / 没重启，旧代码仍在对外服务。
running_commit_is_current() {
  local want got
  [ -f "$DEPLOY_PATH/backend/git_commit.txt" ] || return 1
  want="$(tr -d ' \t\n\r' < "$DEPLOY_PATH/backend/git_commit.txt")"
  [ -n "$want" ] || return 1
  # /health 返回的是紧凑 JSON（"git_commit":"xxx"，冒号后无空格），
  # 不能按格式化 JSON 匹配。按逗号 / 左花括号切行再取值，两种格式都兼容。
  got="$(curl -sf --max-time 10 http://127.0.0.1:5200/health 2>/dev/null \
        | tr ',{' '\n' | grep '"git_commit"' | head -1 | sed 's/.*: *"//; s/".*//')"
  [ -n "$got" ] || return 1
  [ "$got" = "$want" ]
}

check "业务探针：/v1/membership/plans 应答（membership 蓝图已注册）" 'membership_plans_ok'
check "路由清单含 membership / account 模块" 'endpoints_modules_ok'
if [ -f "$BASELINE_FILE" ]; then
  check "路由总数较上一版下降不超过 ${SMOKE_DROP_PCT}%（基线 $(tr -d ' \t\n\r' < "$BASELINE_FILE") 条）" 'endpoints_count_ok'
else
  printf '  \033[33m-\033[0m 无路由总数基线（%s），跳过该断言\n' "$BASELINE_FILE"
fi
check "运行的 git_commit 与本次发布一致（代码确实生效）" 'running_commit_is_current'

if [ "$fail" -eq 0 ]; then
  printf '\033[32m=== 全部健康 ===\033[0m\n'
else
  printf '\033[31m=== 有服务异常 ===\033[0m\n'
fi
exit "$fail"
