#!/usr/bin/env bash
# =============================================================
# release-tag.sh — 打不可变 stack-v* 注释 tag（默不 push、不动真机）
#
#   手工发版的替代：契约钉 + 干跑全绿，才能留下可回滚的版本号。
#   回滚不是「再手改一遍 nginx」，而是检出上一个 tag。
#
#   用法:
#     bash scripts/release-tag.sh 0.1.0
#     bash scripts/release-tag.sh 0.1.0 --push     # 推 tag，触发 CI；仍不会部署
#     bash scripts/release-tag.sh 0.1.0 --allow-dirty
#
#   部署真机另需: 停掉 looma-zervi overseas-*、本仓收齐 tspace 源码、
#   vars.DEPLOY_ENABLED=true。现在禁止 --push 到会触发部署的远端 tag。
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
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      if [ -z "$VERSION" ]; then VERSION="$arg"; else echo "unexpected: $arg" >&2; exit 1; fi
      ;;
  esac
done

if [ -z "$VERSION" ]; then
  echo "usage: bash scripts/release-tag.sh X.Y.Z [--push] [--allow-dirty]" >&2
  exit 1
fi
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "version must be X.Y.Z (got $VERSION)" >&2
  exit 1
fi

if [ "$PUSH" -eq 1 ]; then
  echo "REFUSE: 现在禁止 push stack-v*。" >&2
  echo "  旧云主机服务仍在跑；looma-zervi overseas-* rsync 未停。" >&2
  echo "  本地可以打 tag 做演练，不要推远端，也不要开 DEPLOY_ENABLED。" >&2
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
Deploy still gated by DEPLOY_ENABLED (off by default).
EOF
)
git tag -a "$TAG" -m "$MSG"
echo "created $TAG -> $SHA"
echo "not pushed. inspect: git show $TAG"
