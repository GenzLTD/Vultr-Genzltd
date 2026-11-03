#!/usr/bin/env bash
# =============================================================
# Lock 3 — 认人代码同源：SG 发布树必须携带 looma join 语义
#
#   1) identity/ledger_subject.py + __init__.py 必须存在，且与 looma tip 同 blob
#   2) manager / settlement 必须含 recompute_user_tier 路径（禁整树旧 Vultr overlay 盖掉）
#   3) 钉 contracts/looma-join.PIN.json 的 looma_sha（文档/验收用；CI 打印实测 tip）
#
#   不在本门禁强制 payment_routes 全量 wiring（避免 #39 wholesale overlay 事故）；
#   验收清单见 docs/dual-track-ledger-boundary.md。
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOOMA_REF="${LOOMA_REF:-main}"
LOOMA_REPO="${LOOMA_REPO:-https://github.com/GenzLTD/looma-zervi.git}"
PIN_FILE="contracts/looma-join.PIN.json"

IDENTITY_FILES=(
  "backend/src/identity/__init__.py"
  "backend/src/identity/ledger_subject.py"
)

fail=0

for path in "${IDENTITY_FILES[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "::error::MISSING $path — SG release must carry looma join semantics" >&2
    fail=1
  fi
done

for path in \
  "backend/src/db/manager.py" \
  "backend/src/payment/settlement.py"
do
  if [[ ! -f "$path" ]]; then
    echo "::error::MISSING $path" >&2
    fail=1
    continue
  fi
  if ! grep -q "recompute_user_tier" "$path"; then
    echo "::error::$path missing recompute_user_tier — refuse Vultr-old overlay" >&2
    fail=1
  else
    echo "OK marker recompute_user_tier in $path"
  fi
done

TMP=""
cleanup() {
  if [[ -n "${TMP:-}" && -d "$TMP" ]]; then
    rm -rf "$TMP"
  fi
}
trap cleanup EXIT

if [[ -n "${LOOMA_CHECKOUT:-}" && -d "$LOOMA_CHECKOUT" ]]; then
  LOOMA_ROOT="$LOOMA_CHECKOUT"
else
  TMP="$(mktemp -d)"
  LOOMA_ROOT="$TMP/looma"
  git clone --depth 1 --branch "$LOOMA_REF" "$LOOMA_REPO" "$LOOMA_ROOT"
fi

LOOMA_SHA="$(git -C "$LOOMA_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "looma tip sha=$LOOMA_SHA (ref=$LOOMA_REF)"

for path in "${IDENTITY_FILES[@]}"; do
  if [[ ! -f "$path" ]]; then
    continue
  fi
  if [[ ! -f "$LOOMA_ROOT/$path" ]]; then
    echo "::error::looma tip missing $path" >&2
    fail=1
    continue
  fi
  local_blob="$(git hash-object "$path")"
  remote_blob="$(git -C "$LOOMA_ROOT" hash-object "$path" 2>/dev/null \
    || git hash-object "$LOOMA_ROOT/$path")"
  if [[ "$local_blob" != "$remote_blob" ]]; then
    echo "::error::JOIN_BLOB_MISMATCH $path local=$local_blob looma=$remote_blob" >&2
    fail=1
  else
    echo "OK $local_blob $path"
  fi
done

if [[ -f "$PIN_FILE" ]]; then
  echo "PIN file present: $PIN_FILE"
  if command -v python3 >/dev/null 2>&1; then PY=python3
  elif command -v python >/dev/null 2>&1; then PY=python
  else PY=""; fi
  if [[ -n "$PY" ]]; then
    "$PY" - "$PIN_FILE" "$LOOMA_SHA" <<'PY'
import json, sys
pin = json.load(open(sys.argv[1], encoding="utf-8"))
tip = sys.argv[2]
want = (pin.get("looma_sha") or "").strip()
print(f"pin.looma_sha={want or '(empty)'} tip={tip}")
if want and tip != "unknown" and not tip.startswith(want) and not want.startswith(tip[:12]):
    print(f"::warning::PIN looma_sha={want} differs from checkout tip={tip} — refresh pin when intentionally advancing join")
PY
  fi
else
  echo "::warning::missing $PIN_FILE — add pin documenting required looma SHA"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "REFUSE: join semantics drifted or missing (see docs/dual-track-ledger-boundary.md)" >&2
  exit 1
fi
echo "OK looma join semantics (identity blobs + recompute_user_tier markers)"