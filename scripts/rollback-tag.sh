#!/usr/bin/env bash
# =============================================================
# rollback-tag.sh — 按已落地的 stack-v* 回滚（在目标机或经 SSH）
#
#   回滚单元是 tag，不是「再手搓一份 nginx」。
#   只从 /opt/vultr-genzltd-stack/releases/<tag>/ 取树。目录不存在 = 拒绝，不发明配置。
#
#   用法（在 Vultr 上）:
#     STACK_DIR=/opt/vultr-genzltd-stack DEPLOY_PATH=/opt/looma-zervi \
#       bash /opt/vultr-genzltd-stack/scripts/rollback-tag.sh stack-v0.1.0
#
#   用法（从 CI / 笔记本，BatchMode SSH）:
#     bash scripts/rollback-tag.sh stack-v0.1.0 vultr
#
#   不会在 DEPLOY_ENABLED 语义之外被 CI 自动调用。手工止血用。
# =============================================================
set -euo pipefail

TAG="${1:?usage: rollback-tag.sh stack-vX.Y.Z [ssh-host]}"
SSH_HOST="${2:-}"
STACK_DIR="${STACK_DIR:-/opt/vultr-genzltd-stack}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/looma-zervi}"

if ! printf '%s' "$TAG" | grep -Eq '^stack-v[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "tag must look like stack-vX.Y.Z (got $TAG)" >&2
  exit 1
fi

REMOTE=$(cat <<'REMOTE'
set -euo pipefail
TAG="$1"
STACK_DIR="$2"
DEPLOY_PATH="$3"
REL="${STACK_DIR}/releases/${TAG}"
if [ ! -d "$REL" ]; then
  echo "REFUSE: ${REL} 不存在。没有这份树就不能回滚到这个 tag。" >&2
  echo "已有 releases:" >&2
  ls -1 "${STACK_DIR}/releases" 2>/dev/null || echo "(none)" >&2
  exit 1
fi
if [ ! -f "${REL}/compose/docker-compose.yml" ]; then
  echo "REFUSE: ${REL} 缺 compose" >&2
  exit 1
fi
if [ ! -f "${REL}/RELEASE.json" ]; then
  echo "REFUSE: ${REL} 缺 RELEASE.json" >&2
  exit 1
fi

mkdir -p "${STACK_DIR}/backups"
if [ -f "${DEPLOY_PATH}/docker/docker-compose.yml" ]; then
  cp "${DEPLOY_PATH}/docker/docker-compose.yml" \
     "${STACK_DIR}/backups/docker-compose.yml.rollback-$(date +%Y%m%d-%H%M%S)"
fi

cp "${REL}/compose/docker-compose.yml" "${DEPLOY_PATH}/docker/docker-compose.yml"
ln -sfn "$REL" "${STACK_DIR}/current"
printf '%s %s\n' "$TAG" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${STACK_DIR}/CURRENT_RELEASE"

echo "--- RELEASE.json ---"
cat "${REL}/RELEASE.json"

# 契约层随 tag 回来，但不自动解开 circle include。
docker compose --env-file "${DEPLOY_PATH}/backend/.env" \
  -f "${DEPLOY_PATH}/docker/docker-compose.yml" -p looma-zervi \
  up -d --no-build --remove-orphans backend redis chromadb

bash "${STACK_DIR}/scripts/healthcheck.sh"
echo "rolled back to ${TAG}"
REMOTE
)

if [ -n "$SSH_HOST" ]; then
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$SSH_HOST" \
    "STACK_DIR=$(printf %q "$STACK_DIR") DEPLOY_PATH=$(printf %q "$DEPLOY_PATH") bash -s -- $(printf %q "$TAG") $(printf %q "$STACK_DIR") $(printf %q "$DEPLOY_PATH")" \
    <<<"$REMOTE"
else
  bash -s -- "$TAG" "$STACK_DIR" "$DEPLOY_PATH" <<<"$REMOTE"
fi
