#!/bin/sh
# 把 GenzLTD/gfcc 某一提交的契约字节拷进本仓 contracts/gfcc，并改 SOURCE.json 的钉。
# 只改 commit、pinned_at、家族 version，以及真源里新出现且版本与该家族一致的文件清单。
# 不改协议字段。
# 这次预发只收一对：L0 1.5.0 + 信号 1.1.0（含 job_match、value_axis_choice）。
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
pair = (memory.get("version"), signal.get("version"))
if pair != ("1.5.0", "1.1.0"):
    raise SystemExit(
        "FAIL: 本预发只收 L0 1.5.0+信号 1.1.0；"
        f"收到 l0={pair[0]} signal={pair[1]}"
    )

pin_path = dest / "SOURCE.json"
pin = json.loads(pin_path.read_text(encoding="utf-8"))
if pin.get("authority") != "GenzLTD/gfcc":
    raise SystemExit("FAIL: SOURCE.json.authority 必须保持 GenzLTD/gfcc")

def family_of(rel: str) -> str:
    if rel.startswith("signals/") or rel.startswith("signal."):
        return "signal"
    return "l0"

def read_version(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("version")
    return str(version) if version else ""

discovered = {"l0": [], "signal": []}
candidates = sorted(p for p in src.glob("*.json") if p.name != "SOURCE.json")
signals_dir = src / "signals"
if signals_dir.is_dir():
    candidates.extend(sorted(signals_dir.glob("*.json")))
versions = {"l0": pair[0], "signal": pair[1]}
for path in candidates:
    rel = path.relative_to(src).as_posix()
    fam = family_of(rel)
    if read_version(path) == versions[fam]:
        discovered[fam].append(rel)

families = pin.get("families") or {}
for family, spec in families.items():
    expected = versions.get(family)
    if not expected:
        raise SystemExit(f"FAIL: 不知道家族 {family} 的 version 该从哪份契约读")
    listed = list(spec.get("files") or [])
    known = set(listed)
    for rel in discovered[family]:
        if rel not in known:
            listed.append(rel)
            known.add(rel)
    for rel in listed:
        source = src / rel
        target = dest / rel
        if not source.is_file():
            raise SystemExit(f"FAIL: 真源缺少 {rel}")
        got = read_version(source)
        if got != expected:
            raise SystemExit(f"FAIL: {rel} version={got}，家族 {family} 要求 {expected}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    spec["files"] = listed
    spec["version"] = expected

pin["commit"] = sha
pin["pinned_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
pin_path.write_text(json.dumps(pin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OK pin commit={sha} l0={versions['l0']} signal={versions['signal']}")
PY
