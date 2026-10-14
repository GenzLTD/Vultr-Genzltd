#!/usr/bin/env bash
# 发布后契约复跑。由 deploy.yml 步骤 8c 在新进程已经对外服务之后调用。
# 部署前的 contract-gate 对的是即将发布的 url_map；这里对的是线上 /v1/endpoints。
# 前端还在调用、线上后端已经没有的路径 → 退出 1（部署步骤失败后走既有回滚）。
# 后端多出来、前端没调用的路径只报告，不计失败。
#
# 另外探针 GET /v1/narrative/engine/matrix 必须 200 且 domains 为有序 list。
# 这是路径还在、响应却是 500 的那一类（#29），字符串门禁看不见。
# 不要把这条探针放进 healthcheck.sh：回滚复检会拿新脚本去打旧进程，
# 退回 stack-v0.1.5 时 matrix 仍是 500，会把一次成功的代码回滚判成失败。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 - <<'PY'
import json
import urllib.request

req = urllib.request.Request(
    "https://api.genz.ltd/v1/endpoints",
    headers={"User-Agent": "Vultr-Genzltd-contract-gate/1.0"},
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.load(resp)
rules = []
seen = set()
for items in data["endpoints"].values():
    for item in items:
        path = item.split(" ", 1)[1]
        if path not in seen:
            seen.add(path)
            rules.append({"rule": path})
if not rules:
    raise SystemExit("::error::线上 /v1/endpoints 没有路由")
json.dump({"rules": rules}, open("/tmp/live-endpoints.json", "w", encoding="utf-8"))
print(f"线上路径 {len(rules)} 条")
PY

python3 "$ROOT/scripts/check-frontend-contract.py" \
  --endpoints-file /tmp/live-endpoints.json \
  --site https://tspace.genz.ltd \
  --site https://app.genz.ltd

echo "=== narrative matrix 必须 200（set 不可序列化的回归）==="
MATRIX_CODE="$(curl -sS -o /tmp/matrix.json -w '%{http_code}' --connect-timeout 20 \
  "https://api.genz.ltd/v1/narrative/engine/matrix")"
echo "HTTP ${MATRIX_CODE}"
[ "${MATRIX_CODE}" = "200" ] || {
  echo "::error::/v1/narrative/engine/matrix 期望 200，实得 ${MATRIX_CODE}"
  exit 1
}
python3 - <<'PY'
import json
data = json.load(open("/tmp/matrix.json", encoding="utf-8"))
domains = data.get("domains")
if not isinstance(domains, list) or not domains or domains != sorted(domains):
    raise SystemExit("::error::matrix.domains 应为非空有序 list")
print(f"matrix domains {len(domains)}")
PY
