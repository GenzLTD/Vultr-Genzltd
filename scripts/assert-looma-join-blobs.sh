#!/usr/bin/env bash
# Assert Vultr tree carries the same git blobs as looma-zervi join overlay (PR #39 / FRA machine port).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
expect=(
  "backend/src/identity/__init__.py:b220c4ed060fc30af9beb7fb70fca4f2776d0b61"
  "backend/src/identity/ledger_subject.py:0a0a0a9c28e8ef4065672bfc2d453c6795940c48"
  "backend/src/payment/settlement.py:c45bde69b2e29ea8639d26a141205a7bab2f1e7f"
  "backend/src/api/routes/payment_routes.py:d2a0ba59ef8cf1d6e02b960976600662bde93c81"
  "backend/src/api/routes/huawei_iap_routes.py:393cf844a39da8224ba587eb75330f1e843bef1d"
  "backend/src/db/manager.py:5359a60768794e9ec382fc7d3bf507bf84b20ac9"
)
fail=0
for row in "${expect[@]}"; do
  path="${row%%:*}"
  want="${row##*:}"
  if [[ ! -f "$path" ]]; then
    echo "MISSING $path" >&2
    fail=1
    continue
  fi
  got="$(git hash-object "$path")"
  if [[ "$got" != "$want" ]]; then
    echo "BLOB_MISMATCH $path got=$got want=$want" >&2
    fail=1
  else
    echo "OK $got $path"
  fi
done
if [[ "$fail" -ne 0 ]]; then
  echo "REFUSE: Vultr join blobs drifted from looma-owned lock (see docs/fra-machine-wip-snapshot-20261102/BLOBS.md)" >&2
  exit 1
fi
echo "OK looma-join blobs identical (6/6)"