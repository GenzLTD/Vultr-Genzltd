#!/usr/bin/env sh
# =============================================================
# dryrun.sh — 本地干跑（绝不动真机）
#
#   只依赖本仓目录树，不组装 /opt/looma-zervi，不要求旁边有 looma-zervi。
#     1) 本仓内补齐 data/ 与 backend/.env 桩
#     2) GFCC 契约层（SOURCE 钉 + JSON + $ref）
#     3) docker compose config 语法校验
#     4) 端口收内网断言：唯一允许发布的宿主端口是 127.0.0.1:5200
#     5) nginx -t（容器内 nginx，读本仓 nginx/nginx.conf）
#     6) 裸域 Host 不得回归 + circle 片段在仓、未进现行 conf + compose 相对 baseline
#     7) 运行时：回环绑定在其它网卡上不可达
#
#   用法:
#     bash scripts/dryrun.sh            # 全量
#     bash scripts/dryrun.sh --static   # 只做静态校验
#
#   退出码: 0 = 干跑全绿；非 0 = 有断言失败
# =============================================================
set -u
(set -o pipefail) 2>/dev/null && set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
SSL_DIR="$ROOT/dryrun/layout/ssl"
ERR_DIR="$ROOT/dryrun/layout"
COMPOSE="$ROOT/compose/docker-compose.yml"
NGINX_CONF="$ROOT/nginx/nginx.conf"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:1.18}"
PROBE_PORT=15200
RUNTIME=1
[ "${1:-}" = "--static" ] && RUNTIME=0

ALLOWED_PUBLISHED="127.0.0.1:5200"
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

fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
no()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=1; }
hdr() { printf '\n\033[1m[%s]\033[0m %s\n' "$1" "$2"; }

printf '\033[1m=== Vultr-Genzltd 本地干跑 ===\033[0m\n'
printf '仓库: %s\n' "$ROOT"

# -------------------------------------------------------------
hdr 1 "本仓布局（不模仿生产机 /opt）"
mkdir -p "$ROOT/data/poetry_full" "$ROOT/data/chroma_models" "$ERR_DIR"
if [ ! -f "$ROOT/backend/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/backend/.env"
  ok "写入 backend/.env 桩（来自 .env.example，无真密钥）"
else
  ok "backend/.env 已存在，未覆盖"
fi
if [ ! -f "$COMPOSE" ]; then no "缺少 $COMPOSE"; else ok "compose: compose/docker-compose.yml"; fi
if [ ! -f "$NGINX_CONF" ]; then no "缺少 $NGINX_CONF"; else ok "nginx: nginx/nginx.conf"; fi
if [ ! -d "$ROOT/backend" ]; then no "缺少 backend/（本仓应自带，不要去借 looma-zervi）"; else ok "backend/: 本仓自带"; fi
if [ -f "$ROOT/docker/Dockerfile.backend" ]; then ok "docker/Dockerfile.backend"; else no "缺少 docker/Dockerfile.backend"; fi
if [ -f "$ROOT/frontend/packages/saas/package.json" ]; then ok "frontend: @looma/saas"; else no "缺少 frontend/packages/saas（tspace 必须能在本仓构建）"; fi
if [ -f "$ROOT/frontend/pnpm-lock.yaml" ]; then ok "frontend/pnpm-lock.yaml"; else no "缺少 frontend/pnpm-lock.yaml"; fi
if [ -n "$PY" ]; then ok "python: $PY"; else no "找不到 python3 / python / py（可设 PYTHON_BIN）"; fi
if [ "$fail" -ne 0 ]; then
  printf '\n\033[31m布局不齐，停止。\033[0m\n'
  exit 1
fi

# -------------------------------------------------------------
hdr 2 "GFCC 契约层（无钉则 tag 无法回滚协议）"
# 直接调 python，避免 Windows 上 `bash` 被解析成 WSL 空壳。
if runpy "$ROOT/tools/validate_contracts.py" "$ROOT/contracts/gfcc"; then
  ok "契约层门禁通过"
else
  no "契约层门禁失败"
fi

# -------------------------------------------------------------
hdr 3 "docker compose 语法校验"
if docker compose -f "$COMPOSE" --project-directory "$ROOT/compose" config -q 2>"$ERR_DIR/compose.err"; then
  ok "compose 语法通过"
  rm -f "$ERR_DIR/compose.err"
else
  no "compose 语法失败"
  sed 's/^/     /' "$ERR_DIR/compose.err" | head -20
fi

# -------------------------------------------------------------
hdr 4 "端口收内网断言（唯一允许发布: ${ALLOWED_PUBLISHED}）"
RENDERED="$ERR_DIR/rendered.json"
if docker compose -f "$COMPOSE" --project-directory "$ROOT/compose" config --format json >"$RENDERED" 2>/dev/null; then
  runpy - "$RENDERED" "$ALLOWED_PUBLISHED" <<'PY'
import json, sys
rendered, allowed = sys.argv[1], sys.argv[2]
d = json.load(open(rendered, encoding="utf-8"))
svcs = d.get("services", {})
expected = {"backend", "chromadb", "redis"}
rc = 0
if set(svcs) != expected:
    print(f"  \033[31m✗\033[0m 服务集合异常: {sorted(svcs)} != {sorted(expected)}")
    rc = 1
else:
    print(f"  \033[32m✓\033[0m 服务集合: {', '.join(sorted(svcs))}")
published = []
for name in sorted(svcs):
    ports = svcs[name].get("ports") or []
    if not ports:
        print(f"  \033[32m✓\033[0m {name}: 不发布宿主端口")
        continue
    for p in ports:
        host_ip = p.get("host_ip") or "0.0.0.0"
        tag = f"{host_ip}:{p.get('published')}"
        published.append(tag)
        target = p.get("target")
        if tag == allowed:
            print(f"  \033[32m✓\033[0m {name}: {tag} → 容器 {target}")
        else:
            print(f"  \033[31m✗\033[0m {name}: {tag} → 容器 {target}（应为 {allowed} 或不发布）")
            rc = 1
if allowed not in published:
    print(f"  \033[31m✗\033[0m 缺少必需的发布端口 {allowed}（宿主 nginx upstream 依赖它）")
    rc = 1
sys.exit(rc)
PY
  [ $? -ne 0 ] && fail=1
  rm -f "$RENDERED"
else
  no "无法渲染 compose 配置，端口断言跳过"
fi

# -------------------------------------------------------------
hdr 5 "nginx -t 语法校验"
img=""
for cand in "$NGINX_IMAGE" nginx:1.20 nginx:alpine; do
  if docker pull -q "$cand" >/dev/null 2>&1; then img="$cand"; break; fi
done
if [ -z "$img" ]; then
  no "无法获取 nginx 镜像（离线？）——跳过语法校验，视为未验证"
else
  mkdir -p "$SSL_DIR"
  if [ ! -f "$SSL_DIR/fullchain.pem" ]; then
    openssl req -x509 -nodes -days 30 -newkey rsa:2048 -subj "/CN=dryrun.local" \
      -keyout "$SSL_DIR/privkey.pem" -out "$SSL_DIR/fullchain.pem" >/dev/null 2>&1
  fi
  out="$(docker run --rm --entrypoint nginx \
    -v "$NGINX_CONF:/etc/nginx/nginx.conf:ro" \
    -v "$SSL_DIR:/etc/nginx/ssl:ro" \
    "$img" -t 2>&1)"
  printf '%s\n' "$out" | sed 's/^/     /'
  if printf '%s' "$out" | grep -q "syntax is ok"; then
    ok "nginx.conf 语法通过（${img}）"
  else
    no "nginx.conf 语法失败"
  fi
fi

# -------------------------------------------------------------
hdr 6 "期望态断言（本仓 nginx / compose，不是生产机路径）"
runpy - "$NGINX_CONF" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
tokens = []
for m in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", text):
    tokens.extend(t for t in m.group(1).split() if t)
bare = [t for t in tokens if t in ("genz.ltd", "www.genz.ltd")]
need = {"api.genz.ltd", "tspace.genz.ltd"}
rc = 0
if bare:
    print(f"  \033[31m✗\033[0m nginx 仍有裸域 server_name: {bare}")
    rc = 1
else:
    print("  \033[32m✓\033[0m nginx 无 genz.ltd / www.genz.ltd server_name")
missing = sorted(need - set(tokens))
if missing:
    print(f"  \033[31m✗\033[0m nginx 缺少 Host: {missing}")
    rc = 1
else:
    print("  \033[32m✓\033[0m nginx Host: api.genz.ltd, tspace.genz.ltd")
sys.exit(rc)
PY
[ $? -ne 0 ] && fail=1

if diff -q "$ROOT/baseline/docker-compose.yml" "$COMPOSE" >/dev/null 2>&1; then
  no "compose 与 baseline 一致——P0 端口收敛未生效"
else
  changed="$(diff -u "$ROOT/baseline/docker-compose.yml" "$COMPOSE" | grep -cE '^[+-][^+-]' || true)"
  ok "compose 相对 baseline 有差异（${changed} 行，应为端口收内网）"
  echo "     --- 变更集（- baseline / + 期望态）---"
  diff -u "$ROOT/baseline/docker-compose.yml" "$COMPOSE" \
    | sed -n '3,80p' | sed 's/^/     /'
fi

if diff -q "$ROOT/baseline/nginx.conf" "$NGINX_CONF" >/dev/null 2>&1; then
  no "nginx 仍等于 2026-09-18 晨间基线（含裸域块）——摘块未进本仓"
else
  ok "nginx 已相对 baseline 摘掉裸域（这是期望态，不是事故）"
fi

CIRCLE_SNIPPET="$ROOT/nginx/sites/circle.genz.ltd.conf"
runpy - "$NGINX_CONF" "$CIRCLE_SNIPPET" <<'PY'
import re, sys
main, snippet = sys.argv[1], sys.argv[2]
main_text = open(main, encoding="utf-8").read()
rc = 0
tokens = []
for m in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", main_text):
    tokens.extend(t for t in m.group(1).split() if t)
if "circle.genz.ltd" in tokens:
    print("  \033[31m✗\033[0m 现行 nginx.conf 已有 server_name circle.genz.ltd —— 必须走独立 tag 解开，禁止混进默认 conf")
    rc = 1
else:
    print("  \033[32m✓\033[0m 现行 nginx.conf 尚未收 circle.genz.ltd（片段另存）")
try:
    snip = open(snippet, encoding="utf-8").read()
except FileNotFoundError:
    print(f"  \033[31m✗\033[0m 缺少 circle 片段: {snippet}")
    sys.exit(1)
if not re.search(r"(?m)^\s*server_name\s+circle\.genz\.ltd\s*;", snip):
    print("  \033[31m✗\033[0m circle 片段缺少 server_name circle.genz.ltd")
    rc = 1
else:
    print("  \033[32m✓\033[0m circle 片段 Host: circle.genz.ltd")
if "127.0.0.1:5211" not in snip:
    print("  \033[31m✗\033[0m circle 片段未指向回环 127.0.0.1:5211")
    rc = 1
else:
    print("  \033[32m✓\033[0m circle 片段上游 127.0.0.1:5211（kernel 未进 compose 前不得解开 include）")
if "location /circle/" not in snip:
    print("  \033[31m✗\033[0m circle 片段缺少 location /circle/")
    rc = 1
else:
    print("  \033[32m✓\033[0m circle 路径 /circle/")
sys.exit(rc)
PY
[ $? -ne 0 ] && fail=1

# -------------------------------------------------------------
hdr 7 "运行时语义实证：回环绑定在其它网卡不可达"
if [ "$RUNTIME" -eq 0 ]; then
  echo "     （--static 已跳过）"
elif [ -z "$img" ]; then
  echo "     （无可用镜像，跳过）"
else
  docker rm -f vultr-genzltd-dryrun-probe >/dev/null 2>&1 || true
  if docker run -d --name vultr-genzltd-dryrun-probe --entrypoint sleep \
       -p "127.0.0.1:$PROBE_PORT:80" "$img" 20 >/dev/null 2>&1; then
    sleep 1
    bound="$(docker port vultr-genzltd-dryrun-probe 80/tcp 2>/dev/null | head -1)"
    case "$bound" in
      127.0.0.1:*) ok "docker 实际绑定 = $bound" ;;
      *)           no "docker 实际绑定异常 = ${bound:-（空）}" ;;
    esac
    if nc -z -w 2 127.0.0.1 "$PROBE_PORT" >/dev/null 2>&1; then
      ok "回环可达（127.0.0.1:${PROBE_PORT}）"
    else
      no "回环不可达（127.0.0.1:${PROBE_PORT}）"
    fi
    lanip=""
    if command -v ip >/dev/null 2>&1; then
      lanip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
    fi
    if [ -z "$lanip" ] && command -v hostname >/dev/null 2>&1; then
      lanip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    fi
    if [ -z "$lanip" ] && [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
      lanip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
    fi
    if [ -n "$lanip" ] && [ "$lanip" != "127.0.0.1" ]; then
      if nc -z -w 2 "$lanip" "$PROBE_PORT" >/dev/null 2>&1; then
        no "局域网可达（$lanip:${PROBE_PORT}）——收内网未生效"
      else
        ok "局域网不可达（$lanip:${PROBE_PORT}）——收内网生效"
      fi
    else
      echo "     （未取到非回环局域网 IP，跳过外部网卡验证）"
    fi
    docker rm -f vultr-genzltd-dryrun-probe >/dev/null 2>&1 || true
  else
    no "探针容器启动失败（镜像 ${img}）"
  fi
fi

# -------------------------------------------------------------
printf '\n\033[1m=== 干跑结论 ===\033[0m\n'
if [ "$fail" -eq 0 ]; then
  printf '\033[32m全部通过。\033[0m本仓自包含校验完成（未碰真机）。\n'
else
  printf '\033[31m存在失败断言，不得进入真机流程。\033[0m\n'
fi
exit "$fail"
