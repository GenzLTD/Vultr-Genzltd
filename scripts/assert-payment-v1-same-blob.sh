#!/usr/bin/env bash
# =============================================================
# Lock 1 — 契约同源：payment.v1 必须与 looma tip 同 blob
#
#   对比本仓 backend/contracts/payment.v1.json 与 looma 同路径。
#   优先 LOOMA_CHECKOUT（CI 第二 checkout）；否则浅克隆 LOOMA_REPO@LOOMA_REF。
#   漂移 → 非零退出（阻断 stack-v* / deploy 扇入）。
#
#   可选 GFCC SOURCE：两边都有时报告；STRICT_GFCC_SOURCE=1 才失败。
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOOMA_REF="${LOOMA_REF:-main}"
LOOMA_REPO="${LOOMA_REPO:-https://github.com/GenzLTD/looma-zervi.git}"
PATH_PAYMENT="backend/contracts/payment.v1.json"
PATH_SOURCE="contracts/gfcc/SOURCE.json"
STRICT_GFCC_SOURCE="${STRICT_GFCC_SOURCE:-0}"

if [[ ! -f "$PATH_PAYMENT" ]]; then
  echo "::error::missing $PATH_PAYMENT" >&2
  exit 1
fi

LOCAL_BLOB="$(git hash-object "$PATH_PAYMENT")"
echo "local payment.v1 blob=$LOCAL_BLOB"

TMP=""
cleanup() { [[ -n "${TMP:-}" && -d "$TMP" ]] && rm -rf "$TMP"; }
trap cleanup EXIT

if [[ -n "${LOOMA_CHECKOUT:-}" && -d "$LOOMA_CHECKOUT" ]]; then
  LOOMA_ROOT="$LOOMA_CHECKOUT"
  echo "using LOOMA_CHECKOUT=$LOOMA_ROOT"
else
  TMP="$(mktemp -d)"
  LOOMA_ROOT="$TMP/looma"
  echo "clone $LOOMA_REPO ($LOOMA_REF)"
  git clone --depth 1 --branch "$LOOMA_REF" "$LOOMA_REPO" "$LOOMA_ROOT"
fi

if [[ ! -f "$LOOMA_ROOT/$PATH_PAYMENT" ]]; then
  echo "::error::looma missing $PATH_PAYMENT" >&2
  exit 1
fi

REMOTE_BLOB="$(git -C "$LOOMA_ROOT" hash-object "$PATH_PAYMENT" 2>/dev/null \
  || git hash-object "$LOOMA_ROOT/$PATH_PAYMENT")"
LOOMA_SHA="$(git -C "$LOOMA_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "looma sha=$LOOMA_SHA payment.v1 blob=$REMOTE_BLOB"

if [[ "$LOCAL_BLOB" != "$REMOTE_BLOB" ]]; then
  echo "::error::payment.v1 BLOB_DRIFT local=$LOCAL_BLOB looma=$REMOTE_BLOB (ref=$LOOMA_REF)" >&2
  echo "REFUSE: sync $PATH_PAYMENT from looma tip before tag/deploy" >&2
  exit 1
fi
echo "OK payment.v1 same blob ($LOCAL_BLOB)"

if [[ -f "$PATH_SOURCE" && -f "$LOOMA_ROOT/$PATH_SOURCE" ]]; then
  LOCAL_SRC="$(git hash-object "$PATH_SOURCE")"
  REMOTE_SRC="$(git -C "$LOOMA_ROOT" hash-object "$PATH_SOURCE" 2>/dev/null \
    || git hash-object "$LOOMA_ROOT/$PATH_SOURCE")"
  echo "SOURCE.json local=$LOCAL_SRC looma=$REMOTE_SRC"
  if [[ "$LOCAL_SRC" != "$REMOTE_SRC" ]]; then
    if [[ "$STRICT_GFCC_SOURCE" == "1" ]]; then
      echo "::error::GFCC SOURCE BLOB_DRIFT local=$LOCAL_SRC looma=$REMOTE_SRC" >&2
      exit 1
    fi
    echo "::warning::GFCC SOURCE drift (STRICT_GFCC_SOURCE=0; playbook holds 1.6.0 consumer pin)"
  else
    echo "OK GFCC SOURCE same blob"
  fi
else
  echo "NOTE: GFCC SOURCE compare skipped (missing on one side)"
fi
