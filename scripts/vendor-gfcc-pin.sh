#!/bin/sh
# 把 GenzLTD/gfcc 某一提交的契约字节拷进本仓 contracts/gfcc，并改 SOURCE.json 的钉。
# 只改 commit、pinned_at、家族 version。不改协议字段。
# L0 必须是 1.5.0，信号必须是 1.1.0，否则拒绝。
set -eu

GFCC_SRC="${1:?用法: vendor-gfcc-pin.sh <gfcc 检出> <contracts/gfcc 目录>}"
DEST="${2:?用法: vendor-gfcc-pin.sh <gfcc 检出> <contracts/gfcc 目录>}"

if ! git -C "$GFCC_SRC" rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "FAIL: $GFCC_SRC 不是 git 检出" >&2
  exit 1
fi

SHA="$(git -C "$GFCC_SRC" rev-parse HEAD)"
export GFCC_SHA="$SHA"
export GFCC_CONTRACTS="$GFCC_SRC/contracts"
export DEST_CONTRACTS="$DEST"

PY=""
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "FAIL: 需要 python3" >&2
  exit 1
fi

"$PY" - <<'PY'
import json, os, shutil
from datetime import datetime, timezone
from pathlib import Path

src = Path(os.environ["GFCC_CONTRACTS"])
dest = Path(os.environ["DEST_CONTRACTS"])
sha = os.environ["GFCC_SHA"]
if len(sha) < 40:
    raise SystemExit(f"FAIL: gfcc SHA 不是完整提交 {sha}")

memory = json.loads((src / "memory.v1.json").read_text(encoding="utf-8"))
signal = json.loads((src / "signal.envelope.v1.json").read_text(encoding="utf-8"))
axis = src / "signals" / "value_axis_choice.v1.json"
score = src / "job_match.v1.json"
if memory.get("version") != "1.5.0":
    raise SystemExit(f"FAIL: memory.v1.json version={memory.get('version')}，本预发只收 1.5.0")
if signal.get("version") != "1.1.0":
    raise SystemExit(f"FAIL: signal.envelope version={signal.get('version')}，本预发只收 1.1.0")
if not axis.is_file():
    raise SystemExit("FAIL: 真源缺少 signals/value_axis_choice.v1.json")
if not score.is_file() or json.loads(score.read_text(encoding="utf-8")).get("writes_to") != "none":
    raise SystemExit("FAIL: 真源缺少 job_match.v1.json，或 writes_to 不是 none")

pin_path = dest / "SOURCE.json"
pin = json.loads(pin_path.read_text(encoding="utf-8"))
if pin.get("authority") != "GenzLTD/gfcc":
    raise SystemExit("FAIL: SOURCE.json.authority 必须保持 GenzLTD/gfcc")

families = pin.get("families") or {}
versions = {"l0": memory["version"], "signal": signal.get("version")}
for family, spec in families.items():
    expected = versions.get(family)
    if not expected:
        raise SystemExit(f"FAIL: 不知道家族 {family} 的 version 该从哪份契约读")
    for rel in spec.get("files") or []:
        source = src / rel
        target = dest / rel
        if not source.is_file():
            raise SystemExit(f"FAIL: 真源缺少 {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    spec["version"] = expected

pin["commit"] = sha
pin["pinned_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
pin_path.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OK pin commit={sha} l0={versions['l0']} signal={versions['signal']}")
PY
