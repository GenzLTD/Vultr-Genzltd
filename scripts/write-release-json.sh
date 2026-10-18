#!/usr/bin/env sh
# =============================================================
# write-release-json.sh — 由 tag / CI 调用，写出 RELEASE.json（stdout）
#
#   用法: bash scripts/write-release-json.sh stack-vX.Y.Z [git-sha]
# =============================================================
set -eu
(set -o pipefail) 2>/dev/null && set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:?usage: write-release-json.sh stack-vX.Y.Z [sha]}"
SHA="${2:-}"
if [ -z "$SHA" ]; then
  SHA="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
fi

SOURCE="$ROOT/contracts/gfcc/SOURCE.json"
if [ ! -f "$SOURCE" ]; then
  echo "missing $SOURCE" >&2
  exit 1
fi

# 不引入 jq：用 python 把 pin 嵌进 RELEASE
PY=""
if [ -n "${PYTHON_BIN:-}" ]; then PY="$PYTHON_BIN"
elif command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v py >/dev/null 2>&1; then PY=py
elif command -v python >/dev/null 2>&1; then PY=python
fi
if [ -z "$PY" ]; then echo "python missing" >&2; exit 1; fi
runpy() { if [ "$PY" = py ]; then py -3 "$@"; else "$PY" "$@"; fi; }

runpy - "$SOURCE" "$TAG" "$SHA" <<'PY'
import json, sys
from datetime import datetime, timezone
pin = json.load(open(sys.argv[1], encoding="utf-8"))
tag, sha = sys.argv[2], sys.argv[3]
doc = {
    "schema": "vultr-genzltd.release.v1",
    "tag": tag,
    "git_sha": sha,
    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "gfcc": {
        "authority": pin.get("authority"),
        "commit": pin.get("commit"),
        "families": pin.get("families"),
        "kernel": pin.get("kernel"),
    },
    "circle": {
        "enabled": True,
        "reason": "kernel now in base compose (127.0.0.1:5211); nginx include opened and gated by deploy.yml (kernel /health 200 + ETHOS_AUTH_SECRET non-empty) before reload; DNS switch is a manual follow-up after local health is green",
        "host_desired": (pin.get("circle") or {}).get("host_desired"),
        "snippet": (pin.get("circle") or {}).get("snippet"),
    },
    "stack": {
        "compose": "compose/docker-compose.yml",
        "nginx": "nginx/nginx.conf",
        "contracts": "contracts/gfcc/",
        "target_dir_on_host": "/opt/vultr-genzltd-stack",
    },
}
json.dump(doc, sys.stdout, indent=2, ensure_ascii=False)
print()
PY
