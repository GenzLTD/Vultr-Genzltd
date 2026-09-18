#!/usr/bin/env sh
# =============================================================
# assert-contracts.sh — GFCC 契约层门禁（不动真机）
#
#   无契约钉，stack-v* 只是一堆文件，回滚时不知道协议是哪一版。
# =============================================================
set -u
(set -o pipefail) 2>/dev/null && set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTRACTS="$ROOT/contracts/gfcc"
fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
no()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=1; }

PY=""
if [ -n "${PYTHON_BIN:-}" ] && "$PYTHON_BIN" -c "import sys" >/dev/null 2>&1; then
  PY="$PYTHON_BIN"
elif command -v py >/dev/null 2>&1 && py -3 -c "import sys" >/dev/null 2>&1; then
  PY=py
elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
  PY=python
fi
runpy() {
  if [ -z "$PY" ]; then
    echo "python missing" >&2
    return 127
  fi
  if [ "$PY" = py ]; then py -3 "$@"; else "$PY" "$@"; fi
}

printf '\033[1m=== GFCC 契约层 ===\033[0m\n'
if [ ! -f "$CONTRACTS/SOURCE.json" ]; then
  no "缺少 contracts/gfcc/SOURCE.json"
  exit 1
fi
if [ -z "$PY" ]; then
  no "找不到 python3 / python / py（可设 PYTHON_BIN）"
  exit 1
fi

if runpy "$ROOT/tools/validate_contracts.py" "$CONTRACTS"; then
  ok "JSON / 家族版本 / SOURCE 钉 / \$ref"
else
  no "契约校验失败"
fi

exit "$fail"
