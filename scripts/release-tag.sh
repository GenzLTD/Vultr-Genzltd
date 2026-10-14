#!/usr/bin/env bash
# =============================================================
# release-tag.sh — 打不可变 stack-v* 注释 tag（默认不 push、不动真机）
#
#   手工发版的替代：契约钉 + 干跑全绿，才能留下可回滚的版本号。
#   回滚不是「再手改一遍 nginx」，而是检出上一个 tag。
#
#   用法:
#     bash scripts/release-tag.sh 0.1.0                # 只打本地 tag（默认）
#     bash scripts/release-tag.sh 0.1.0 --push         # 打 tag + 推远端 —— 会真实部署，见下
#     bash scripts/release-tag.sh 0.1.0 --allow-dirty  # 允许脏工作区（仅本地演练）
#     bash scripts/release-tag.sh 0.1.0 --skip-dryrun  # 跳过干跑（仅本地演练）
#
#   --push 的真实语义（2026-10-14 修订）:
#     vars.DEPLOY_ENABLED 已于 2026-10-11 由 looma-zervi 海外部署 CI 有意置为 true，
#     deploy.yml 的部署门因此常开：push stack-v* 即真实部署到 vars.DEPLOY_HOST，
#     且无审批拦截。旧注「现在禁止 push / DEPLOY_ENABLED 默认关」系旧项目残留，
#     自 2026-10-11 澄清后已不适用，故此处不再拦截，改为把目标机摆到眼前再推。
#     发版纪律：先 push 分支，再单独 push tag（避免 Actions 列表双记录）。
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION=""
PUSH=0
ALLOW_DIRTY=0
SKIP_DRYRUN=0
for arg in "$@"; do
  case "$arg" in
    --push) PUSH=1 ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    --skip-dryrun) SKIP_DRYRUN=1 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      if [ -z "$VERSION" ]; then VERSION="$arg"; else echo "unexpected: $arg" >&2; exit 1; fi
      ;;
  esac
done

if [ -z "$VERSION" ]; then
  echo "usage: bash scripts/release-tag.sh X.Y.Z [--push] [--allow-dirty] [--skip-dryrun]" >&2
  exit 1
fi
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "version must be X.Y.Z (got $VERSION)" >&2
  exit 1
fi

TAG="stack-v${VERSION}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not a git repo" >&2
  exit 1
fi
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "tag already exists: $TAG  (tags are immutable; bump the version)" >&2
  exit 1
fi
if [ "$ALLOW_DIRTY" -eq 0 ]; then
  if [ -n "$(git status --porcelain)" ]; then
    echo "working tree dirty. commit first, or pass --allow-dirty for a local experiment tag." >&2
    git status --short
    exit 1
  fi
fi

# --push 前置告知：把「推出去会部署到哪台机」摆到眼前（查不到不阻断）
DEPLOY_HOST=""
if [ "$PUSH" -eq 1 ]; then
  echo "=== --push：本仓 DEPLOY_ENABLED=true（2026-10-11 起）→ 推 tag 即真实部署 ===" >&2
  if command -v gh >/dev/null 2>&1; then
    DEPLOY_HOST="$(gh api repos/GenzLTD/Vultr-Genzltd/actions/variables/DEPLOY_HOST --jq .value 2>/dev/null || true)"
  fi
  if [ -n "$DEPLOY_HOST" ]; then
    echo "  DEPLOY_HOST = $DEPLOY_HOST" >&2
  else
    echo "  DEPLOY_HOST = (未查到；以 repo vars 为准)" >&2
  fi
  echo "  将推送单条 refs/tags/$TAG；请确认要发的正是 HEAD，且分支已先推。" >&2
fi

echo "=== 1/3 契约层 ==="
sh "$ROOT/scripts/assert-contracts.sh"

if [ "$SKIP_DRYRUN" -eq 0 ]; then
  echo "=== 2/3 干跑（--static）==="
  sh "$ROOT/scripts/dryrun.sh" --static
else
  echo "=== 2/3 干跑跳过（--skip-dryrun）==="
fi

SHA="$(git rev-parse HEAD)"
PIN="$(grep -oE '[0-9a-f]{40}' contracts/gfcc/SOURCE.json | head -1 | cut -c1-12)"
PIN="${PIN:-unknown}"

echo "=== 3/3 注释 tag $TAG ==="
MSG=$(cat <<EOF
$TAG

Immutable overseas stack snapshot.
gfcc pin: $PIN
sha: $SHA

Rollback: bash scripts/rollback-tag.sh $TAG
Deploy: push 本 tag 即真实部署（DEPLOY_ENABLED=true，无审批拦截）。
Deploy host: ${DEPLOY_HOST:-见 repo vars.DEPLOY_HOST}
EOF
)
git tag -a "$TAG" -m "$MSG"
echo "created $TAG -> $SHA"

if [ "$PUSH" -eq 1 ]; then
  echo "=== push refs/tags/$TAG → origin（这将触发真实部署）==="
  git push origin "refs/tags/$TAG"
  echo "已推送。看 CI：gh run list --limit 3"
else
  echo "not pushed. inspect: git show $TAG"
  echo "要发布：bash scripts/release-tag.sh $VERSION --push"
fi
