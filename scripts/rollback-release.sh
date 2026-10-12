#!/usr/bin/env bash
# =============================================================
# rollback-release.sh — 回滚「代码」到上一个 release（不动 compose）
#
#   为什么不动 compose：
#     回滚 compose 的做法是恢复 $STACK_DIR/backups/docker-compose.yml.*，
#     而历史备份里的 backend 端口是 0.0.0.0:5200（公网可达）。恢复它等于
#     把端口重新暴露出去。本脚本只把目标 release 的 backend/ 重新投到
#     DEPLOY_PATH，compose 保持本仓版本（127.0.0.1:5200），不触碰端口。
#
#   前置（deploy.yml 步骤 3 建立的约定）：
#     - $STACK_DIR/releases/<tag>   不可变快照
#     - $STACK_DIR/current          → 指向当前 release 的软链
#     - $STACK_DIR/CURRENT_RELEASE  "<tag> <sha> <时间戳>"
#
#   用法:
#     bash scripts/rollback-release.sh                  # dry-run，只打印
#     bash scripts/rollback-release.sh --apply          # 实际执行
#     bash scripts/rollback-release.sh --to stack-v0.1.3 --apply
#
#   退出码: 0 成功 / 1 拒绝执行（前置不满足）/ 2 参数错误
# =============================================================
set -uo pipefail

STACK_DIR="${STACK_DIR:-/opt/vultr-genzltd-stack}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/looma-zervi}"
APPLY=0
TARGET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --to)    TARGET="${2:-}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# --- 前置自检：失败路径必须可预测，条件不满足就明确拒绝，绝不半途动作 ---
[ -d "$STACK_DIR/releases" ] || { echo "REFUSE: 无 $STACK_DIR/releases"; exit 1; }
[ -d "$DEPLOY_PATH/backend" ] || { echo "REFUSE: 无 $DEPLOY_PATH/backend"; exit 1; }

CUR="$(awk 'NR==1{print $1}' "$STACK_DIR/CURRENT_RELEASE" 2>/dev/null)"
echo "当前 release: ${CUR:-（未知）}"

if [ -z "$TARGET" ]; then
  TARGET="$(ls -1dt "$STACK_DIR"/releases/*/ 2>/dev/null | while read -r d; do
      b="$(basename "$d")"
      [ "$b" = "$CUR" ] && continue
      echo "$b"
    done | head -1)"
fi

if [ -z "$TARGET" ]; then
  echo "REFUSE: 找不到可回滚的目标 release（releases/ 下只有当前这一个）"
  exit 1
fi

SRC="$STACK_DIR/releases/$TARGET"
[ -d "$SRC/backend" ] || { echo "REFUSE: $SRC/backend 不存在，无法回滚代码"; exit 1; }

echo "回滚目标: $TARGET"
echo "  源:   $SRC/backend/"
echo "  目的: $DEPLOY_PATH/backend/（rsync -a，无 --delete，排除 data/ 与 .env）"
echo "  不动: $DEPLOY_PATH/docker/docker-compose.yml（端口保持 127.0.0.1:5200）"
echo "  不动: $DEPLOY_PATH/backend/data/（SQLite 运行时真源，回滚代码不回滚数据）"

if [ "$APPLY" != "1" ]; then
  echo "（dry-run：加 --apply 才执行）"
  exit 0
fi

rsync -a \
  --exclude='data/' \
  --exclude='.env' --exclude='*.env' \
  --exclude='__pycache__' --exclude='*.pyc' \
  "$SRC/backend/" "$DEPLOY_PATH/backend/"

# 标记回滚状态：/health.git_commit 会读到它，运维一眼能看出「当前是回滚态」
# 同时保证 healthcheck 的「git_commit 与发布一致」断言不会因回滚而误报
echo "rolled-back:$TARGET" > "$DEPLOY_PATH/backend/git_commit.txt"
echo "$TARGET rolled-back $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STACK_DIR/CURRENT_RELEASE"
ln -sfn "$SRC" "$STACK_DIR/current"

docker compose --env-file "$DEPLOY_PATH/backend/.env" \
  -f "$DEPLOY_PATH/docker/docker-compose.yml" -p looma-zervi \
  up -d --no-build --remove-orphans backend redis chromadb

echo "已回滚代码到 $TARGET（compose 与端口配置未改动）"
