#!/usr/bin/env bash
# =============================================================
# dryrun.sh — 本地干跑（绝不动真机）
#
#   把变更集在本机完整过一遍，通过后才谈"动真机"：
#     1) 组装 /opt/looma-zervi 布局镜像（compose 用的是相对路径，
#        只有复现目录布局才能真实解析 ../backend、../data/...）
#     2) docker compose config 语法校验
#     3) 端口收内网断言：唯一允许发布的宿主端口是 127.0.0.1:5200
#     4) nginx -t 语法校验（容器内跑 nginx 1.18，对齐 Ubuntu 22.04）
#     5) 基线指纹断言 + 打印与现网的精确差异（证明只改了该改的）
#     6) 运行时语义实证：回环绑定在其它网卡上确实不可达
#
#   用法:
#     bash scripts/dryrun.sh            # 全量（含运行时实证）
#     bash scripts/dryrun.sh --static   # 只做静态校验，不拉镜像
#
#   退出码: 0 = 干跑全绿，可进入真机流程；非 0 = 有断言失败
# =============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAYOUT="$ROOT/dryrun/layout/opt-looma-zervi"
SSL_DIR="$ROOT/dryrun/layout/ssl"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:1.18}"
PROBE_PORT=15200
RUNTIME=1
[ "${1:-}" = "--static" ] && RUNTIME=0

# 现网冻结基线（见 baseline/MANIFEST.md）
BASE_COMPOSE_MD5="8aace57b5c757e70a5298add5534ef6f"
BASE_NGINX_MD5="0f505e33f8fb047f4185689b89e4c256"
ALLOWED_PUBLISHED="127.0.0.1:5200"

fail=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
no()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=1; }
hdr() { printf '\n\033[1m[%s]\033[0m %s\n' "$1" "$2"; }
md5of() { if command -v md5 >/dev/null 2>&1; then md5 -q "$1"; else md5sum "$1" | cut -d' ' -f1; fi; }

printf '\033[1m=== Vultr-Genzltd 本地干跑 ===\033[0m\n'
printf '仓库: %s\n' "$ROOT"

# -------------------------------------------------------------
hdr 1 "组装布局镜像"
rm -rf "$LAYOUT"
mkdir -p "$LAYOUT/docker" "$LAYOUT/backend" "$LAYOUT/data/poetry_full" "$LAYOUT/data/chroma_models"
cp "$ROOT/compose/docker-compose.yml" "$LAYOUT/docker/docker-compose.yml"
cp "$ROOT/.env.example" "$LAYOUT/backend/.env"
: > "$LAYOUT/docker/Dockerfile.backend"        # 干跑不构建镜像，仅占位满足路径解析
ok "布局就绪: ${LAYOUT#$ROOT/}"

# -------------------------------------------------------------
hdr 2 "docker compose 语法校验"
if docker compose -f "$LAYOUT/docker/docker-compose.yml" config -q 2>"$LAYOUT/config.err"; then
  ok "compose 语法通过"
else
  no "compose 语法失败"
  sed 's/^/     /' "$LAYOUT/config.err" | head -20
fi

# -------------------------------------------------------------
hdr 3 "端口收内网断言（唯一允许发布: ${ALLOWED_PUBLISHED}）"
if docker compose -f "$LAYOUT/docker/docker-compose.yml" config --format json >"$LAYOUT/rendered.json" 2>/dev/null; then
  python3 - "$LAYOUT/rendered.json" "$ALLOWED_PUBLISHED" <<'PY'
import json, sys
rendered, allowed = sys.argv[1], sys.argv[2]
d = json.load(open(rendered))
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
    print(f"  \033[31m✗\033[0m 缺少必需的发布端口 {allowed}（宿主 nginx 的 upstream 依赖它）")
    rc = 1
sys.exit(rc)
PY
  [ $? -ne 0 ] && fail=1
else
  no "无法渲染 compose 配置，端口断言跳过"
fi

# -------------------------------------------------------------
hdr 4 "nginx -t 语法校验"
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
    -v "$ROOT/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
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
hdr 5 "基线指纹断言 + 精确差异"
n_md5="$(md5of "$ROOT/nginx/nginx.conf")"
if [ "$n_md5" = "$BASE_NGINX_MD5" ]; then
  ok "nginx.conf 与现网逐字节一致（本次不改 nginx）"
else
  no "nginx.conf 被改动（$n_md5 ≠ 基线 ${BASE_NGINX_MD5}）——P0 不含 nginx 改动"
fi
c_md5="$(md5of "$ROOT/compose/docker-compose.yml")"
if [ "$c_md5" = "$BASE_COMPOSE_MD5" ]; then
  no "compose 与现网一致——变更未生效"
else
  changed="$(diff -u "$ROOT/baseline/docker-compose.yml" "$ROOT/compose/docker-compose.yml" | grep -cE '^[+-][^+-]' || true)"
  ok "compose 相对现网有差异（${changed} 行变动）"
  echo "     --- 变更集（- 现网 / + 变更后）---"
  diff -u "$ROOT/baseline/docker-compose.yml" "$ROOT/compose/docker-compose.yml" \
    | sed -n '3,200p' | sed 's/^/     /'
fi

# -------------------------------------------------------------
hdr 6 "运行时语义实证：回环绑定在其它网卡不可达"
if [ "$RUNTIME" -eq 0 ]; then
  echo "     （--static 已跳过）"
elif [ -z "$img" ]; then
  echo "     （无可用镜像，跳过）"
else
  docker rm -f looma-dryrun-probe >/dev/null 2>&1 || true
  if docker run -d --name looma-dryrun-probe --entrypoint sleep \
       -p "127.0.0.1:$PROBE_PORT:80" "$img" 20 >/dev/null 2>&1; then
    sleep 1
    bound="$(docker port looma-dryrun-probe 80/tcp 2>/dev/null | head -1)"
    case "$bound" in
      127.0.0.1:*) ok "docker 实际绑定 = $bound" ;;
      *)           no "docker 实际绑定异常 = ${bound:-（空）}" ;;
    esac
    if nc -z -w 2 127.0.0.1 "$PROBE_PORT" >/dev/null 2>&1; then
      ok "回环可达（127.0.0.1:${PROBE_PORT}）"
    else
      no "回环不可达（127.0.0.1:${PROBE_PORT}）"
    fi
    lanip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
    if [ -n "$lanip" ]; then
      if nc -z -w 2 "$lanip" "$PROBE_PORT" >/dev/null 2>&1; then
        no "局域网可达（$lanip:${PROBE_PORT}）——收内网未生效"
      else
        ok "局域网不可达（$lanip:${PROBE_PORT}）——收内网生效"
      fi
    else
      echo "     （未取到局域网 IP，跳过外部网卡验证）"
    fi
    docker rm -f looma-dryrun-probe >/dev/null 2>&1 || true
  else
    no "探针容器启动失败（镜像 ${img}）"
  fi
fi

# -------------------------------------------------------------
printf '\n\033[1m=== 干跑结论 ===\033[0m\n'
if [ "$fail" -eq 0 ]; then
  printf '\033[32m全部通过。\033[0m可进入真机流程（需另行授权）。\n'
else
  printf '\033[31m存在失败断言，不得进入真机流程。\033[0m\n'
fi
exit "$fail"
