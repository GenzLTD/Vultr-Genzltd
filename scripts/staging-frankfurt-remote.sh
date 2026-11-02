#!/bin/sh
# 在法兰克福上执行。调用方先把契约目录和本文件放到 /tmp/staging-frankfurt/，
# 并把 .staging-gfcc.env 写到检出根目录。不部署 zervi-rust，不重建 looma-backend。
set -eu

REPO=/opt/src/Vultr-Genzltd
STAGE=/tmp/staging-frankfurt
: "${VULTR_SHA:?}"
: "${GFCC_SHA:?}"

cd "$REPO"
test -d .git
test -f "$STAGE/docker-compose.frankfurt.yml"
test -d "$STAGE/contracts-gfcc"
test -f "$REPO/.staging-gfcc.env"

ENV_BAK="$(mktemp)"
if [ -f services/tatha/.env ]; then
  cp services/tatha/.env "$ENV_BAK"
fi

git status --porcelain > /tmp/staging-frankfurt-status.txt
python3 - <<'PY'
import pathlib, sys
allowed_exact = {
    "compose/docker-compose.frankfurt.yml",
    ".staging-gfcc.env",
    ".staging-delivery",
    "services/tatha/.env",
}
bad = []
text = pathlib.Path("/tmp/staging-frankfurt-status.txt").read_text(encoding="utf-8")
for line in text.splitlines():
    path = line[3:] if len(line) > 3 else line
    path = path.split(" -> ")[-1].strip()
    if path in allowed_exact or path.startswith("contracts/gfcc/"):
        continue
    bad.append(line)
if bad:
    print("REFUSE: 预发检出有本流水线不认识的本地改动", file=sys.stderr)
    print("\n".join(bad), file=sys.stderr)
    sys.exit(1)
PY

git checkout -- contracts/gfcc
if git cat-file -e "HEAD:services/tatha/.env" 2>/dev/null; then
  git checkout -- services/tatha/.env
fi
rm -f compose/docker-compose.frankfurt.yml
git fetch origin
git checkout --detach "$VULTR_SHA"
if [ -s "$ENV_BAK" ]; then
  cp "$ENV_BAK" services/tatha/.env
fi
rm -f "$ENV_BAK"

rm -rf contracts/gfcc
mkdir -p contracts/gfcc
cp -a "$STAGE/contracts-gfcc/." contracts/gfcc/
cp "$STAGE/docker-compose.frankfurt.yml" compose/docker-compose.frankfurt.yml

python3 - <<PY
import json, os, sys
pin = json.load(open("contracts/gfcc/SOURCE.json", encoding="utf-8"))
mem = json.load(open("contracts/gfcc/memory.v1.json", encoding="utf-8"))
want = os.environ["GFCC_SHA"]
if pin.get("commit") != want:
    sys.exit(f"REFUSE: SOURCE.json.commit={pin.get('commit')} 不是 {want}")
if mem.get("version") != "1.3.0" or pin["families"]["l0"]["version"] != "1.3.0":
    sys.exit("REFUSE: L0 不是 1.3.0")
store = mem.get("store_slot") or {}
if "gfcc" not in (store.get("optional_adapters") or []) or store.get("link") != "actor_sub":
    sys.exit("REFUSE: memory.v1.json 没有 gfcc 适配器或 actor_sub 关联")
print("OK checkout pin", want[:12], "l0", pin["families"]["l0"]["version"])
PY

snap() {
  docker inspect -f '{{.Id}}' "$1"
}
b1="$(snap looma-backend)"
r1="$(snap looma-redis)"
c1="$(snap looma-chromadb)"

COMPOSE="docker compose --env-file $REPO/.staging-gfcc.env -f $REPO/compose/docker-compose.yml -f $REPO/compose/docker-compose.frankfurt.yml -p looma-zervi"
# GFCC_KERNEL_IMAGE 必须在任何 $COMPOSE 命令之前进 env 文件：compose 对全部服务
# 插值，基座 compose 里 gfcc-kernel 的 image 引用它，缺了连 build tatha 都会炸
#（run 39081711926 的根因）。
sed -i '/^GFCC_KERNEL_IMAGE=/d' "$REPO/.staging-gfcc.env"
printf 'GFCC_KERNEL_IMAGE=gfcc-kernel:stage-%s\n' "$GFCC_SHA" >> "$REPO/.staging-gfcc.env"

# SIGNAL_INGEST_SECRET：从机器本地 ingest.env 注入 .staging-gfcc.env（不打印值）。
# 缺密钥则 fail-fast —— 禁止 recreate kernel 后静默 no-auth（未签名变 422）。
INGEST_ENV_CANDIDATES="/opt/looma-fra-emit/ingest.env /root/looma-fra-emit/ingest.env"
if ! grep -q '^SIGNAL_INGEST_SECRET=.\+' "$REPO/.staging-gfcc.env" 2>/dev/null; then
  injected=0
  for cand in $INGEST_ENV_CANDIDATES; do
    if [ -f "$cand" ] && grep -q '^SIGNAL_INGEST_SECRET=.\+' "$cand"; then
      sed -i '/^SIGNAL_INGEST_SECRET=/d' "$REPO/.staging-gfcc.env"
      grep '^SIGNAL_INGEST_SECRET=' "$cand" >> "$REPO/.staging-gfcc.env"
      chmod 600 "$REPO/.staging-gfcc.env"
      injected=1
      echo "OK SIGNAL_INGEST_SECRET 已从机器 ingest.env 注入 .staging-gfcc.env（不入库）"
      break
    fi
  done
  if [ "$injected" != 1 ]; then
    echo "REFUSE: SIGNAL_INGEST_SECRET 缺失。请在预发机写入 /opt/looma-fra-emit/ingest.env 或 .staging-gfcc.env（永不 commit）。缺密钥会让 gfcc-kernel 进入 no-auth。" >&2
    exit 1
  fi
else
  echo "OK .staging-gfcc.env 已含 SIGNAL_INGEST_SECRET"
fi

# 本提交把 gfcc-kernel 上移基座 compose（circle 生产化，与新加坡同款定义）：
# 预发要证明「服务定义已在基座单文件里」，overlay 只剩 stub 覆盖。
# 注意不能对基座跑全量 `docker compose config` 渲染：法兰克福 src 检出刻意没有
# backend/.env，backend 的 env_file 会让全量渲染直接失败（与 kernel 无关；
# 2026-10-18 run 39085585622 实测）。定义存在性用文本断言，功能证明由下面的
# build/up + /health + SQLite 落盘承担。
grep -q '^  gfcc-kernel:' "$REPO/compose/docker-compose.yml" \
  || { echo "REFUSE: 基座 compose 单文件里没有 gfcc-kernel 服务定义" >&2; exit 1; }
echo "OK 基座 compose 含 gfcc-kernel（circle 生产化同款定义）"
docker image inspect "looma-zervi-tatha:pre-$VULTR_SHA" >/dev/null 2>&1 \
  || docker tag looma-zervi-tatha:latest "looma-zervi-tatha:pre-$VULTR_SHA" \
  || true
rm -f "$REPO/.staging-delivery"
$COMPOSE build tatha
$COMPOSE up -d gfcc-pgvector
$COMPOSE up -d --no-deps --force-recreate tatha

b2="$(snap looma-backend)"
r2="$(snap looma-redis)"
c2="$(snap looma-chromadb)"
if [ "$b1" != "$b2" ] || [ "$r1" != "$r2" ] || [ "$c1" != "$c2" ]; then
  echo "REFUSE: looma-backend / redis / chromadb 容器被换掉了" >&2
  exit 1
fi

db=""
i=1
while [ "$i" -le 20 ]; do
  db="$(docker exec gfcc-pgvector psql -U gfcc -d gfcc -tAc 'SELECT current_database()' 2>/dev/null || true)"
  [ "$db" = "gfcc" ] && break
  sleep 2
  i=$((i + 1))
done
[ "$db" = "gfcc" ] || { echo "REFUSE: gfcc 库 40 秒内不可用（当前：$db）" >&2; exit 1; }

# memory 端口（recall）的存储结构。卷是已经 initdb 的，docker-entrypoint-initdb.d
# 不会再跑，所以这里每次显式迁移；SQL 幂等，重复执行不改数据。
MIGRATE="$STAGE/gfcc-memory-v1.sql"
[ -f "$MIGRATE" ] || { echo "REFUSE: 预发包缺 gfcc-memory-v1.sql" >&2; exit 1; }
docker exec -i gfcc-pgvector psql -U gfcc -d gfcc -v ON_ERROR_STOP=1 -q -f - < "$MIGRATE" \
  || { echo "REFUSE: memory 存储迁移失败（compose/sql/gfcc-memory-v1.sql）" >&2; exit 1; }
mcols="$(docker exec gfcc-pgvector psql -U gfcc -d gfcc -tAc \
  "select count(*) from information_schema.columns where table_schema='public' and table_name='memory_record'" 2>/dev/null || true)"
[ "$mcols" = "12" ] || { echo "REFUSE: memory_record 列数 $mcols（期望 12），迁移未生效" >&2; exit 1; }

# 连接串必须真的进了容器：compose 注入没生效时 Tatha 会带着空 DSN 起来，
# recall 只会返回 status=error，看起来像「没有记忆」，所以在这里就拦住。
# 只判前缀，不打印值（DSN 里有口令）。
if ! docker exec tatha-mbti true 2>/dev/null; then
  echo "REFUSE: tatha 容器不可 exec（未运行或正在重启），先看 docker logs tatha-mbti" >&2
  exit 1
fi
dsn_prefix="$(docker exec tatha-mbti printenv GFCC_DB_DSN 2>/dev/null | cut -c1-13 || true)"
[ "$dsn_prefix" = "postgresql://" ] || { echo "REFUSE: tatha 容器内 GFCC_DB_DSN 不是 postgresql:// 开头（compose 注入或 .staging-gfcc.env 缺失）" >&2; exit 1; }

healthy=0
i=1
while [ "$i" -le 30 ]; do
  if curl -sf --max-time 5 http://127.0.0.1:5210/health; then
    healthy=1
    echo
    break
  fi
  sleep 2
  i=$((i + 1))
done
[ "$healthy" = 1 ] || { echo "REFUSE: tatha /health 60 秒内未就绪。镜像锚点是 looma-zervi-tatha:pre-$VULTR_SHA" >&2; exit 1; }

tport="$(docker port tatha-mbti 8010/tcp | head -n 1)"
[ "$tport" = "127.0.0.1:5210" ] || { echo "REFUSE: tatha 端口 $tport" >&2; exit 1; }
pport="$(docker port gfcc-pgvector 5432/tcp | head -n 1)"
[ "$pport" = "127.0.0.1:5434" ] || { echo "REFUSE: gfcc-pgvector 端口 $pport" >&2; exit 1; }

printf 'vultr=%s\ngfcc=%s\nl0=1.3.0\nschema=memory.v1\n' "$VULTR_SHA" "$GFCC_SHA" > "$REPO/.staging-delivery"

# 端到端冒烟：/v1/ask + context.port_hint=memory，带原始 X-Actor-Sub。
# 只读、不写库；空结果按契约也算成功。free 档 ask 配额是 1 次/进程·天，
# 容器刚重建所以计数是新的，这里只打一次。
code="$(curl -s -o /tmp/recall-smoke.json -w '%{http_code}' --max-time 10 \
  -H 'Authorization: Bearer staging-smoke' \
  -H 'X-Actor-Sub: staging-smoke-sub' \
  -H 'Content-Type: application/json' \
  -d '{"message":"recall smoke","context":{"port_hint":"memory","library":"issue","limit":1}}' \
  http://127.0.0.1:5210/v1/ask || true)"
case "$code" in
  200)
    if python3 -c 'import json,sys; d=json.load(open("/tmp/recall-smoke.json")); sys.exit(0 if d.get("port")=="memory" and d.get("result",{}).get("status")=="ok" else 1)'; then
      echo "OK recall 冒烟：port=memory status=ok（空结果也算成功）"
    else
      echo "REFUSE: recall 响应不是 port=memory/status=ok：$(head -c 400 /tmp/recall-smoke.json)" >&2
      exit 1
    fi
    ;;
  401)
    # 配了 QUANTUM_AUTH_URL 时 stub 身份不再被接受，此时流水线无法自测，但不该判失败。
    echo "::warning::recall 冒烟 401：QUANTUM_AUTH_URL 已配置，流水线不带真实 token，跳过自测"
    ;;
  *)
    echo "REFUSE: recall 冒烟 HTTP $code：$(head -c 400 /tmp/recall-smoke.json 2>/dev/null)" >&2
    exit 1
    ;;
esac
rm -f /tmp/recall-smoke.json

# ---- gfcc kernel（circle :5211）预发实例 ----
# 服务定义在基座 compose（本提交上移）。源码不进预发包：gfcc 是 public 仓，
# 机器直接拉 pinned SHA。镜像 tag 带 SHA，compose 用 .staging-gfcc.env 里的
# GFCC_KERNEL_IMAGE 插值。存储是容器内 SQLite（data/memory.db、
# data/circle_flow.db），CREATE TABLE IF NOT EXISTS 首启即建，没有 Postgres
# 迁移。ETHOS_AUTH_SECRET 空 = stub 鉴权（overlay 显式覆盖，预发联调口径）。
KERNEL_SRC=/opt/src/gfcc
if [ -d "$KERNEL_SRC/.git" ]; then
  git -C "$KERNEL_SRC" fetch --depth=1 origin "$GFCC_SHA" >/dev/null 2>&1
else
  git clone --no-checkout https://github.com/GenzLTD/gfcc "$KERNEL_SRC" >/dev/null 2>&1
fi
git -C "$KERNEL_SRC" fetch --depth=1 origin "$GFCC_SHA" >/dev/null 2>&1 \
  || { echo "REFUSE: gfcc 源码拉取失败（$KERNEL_SRC，sha=$GFCC_SHA）" >&2; exit 1; }
git -C "$KERNEL_SRC" checkout --detach --force FETCH_HEAD >/dev/null 2>&1
ksha="$(git -C "$KERNEL_SRC" rev-parse HEAD)"
[ "$ksha" = "$GFCC_SHA" ] || { echo "REFUSE: kernel 源码 HEAD=$ksha 不是 $GFCC_SHA" >&2; exit 1; }

kimg="gfcc-kernel:stage-$GFCC_SHA"
docker build -f "$REPO/docker/Dockerfile.gfcc-kernel" -t "$kimg" "$KERNEL_SRC" \
  || { echo "REFUSE: kernel 镜像构建失败" >&2; exit 1; }

# --force-recreate：保证本次注入的 SIGNAL_INGEST_SECRET 进入容器 env
#（仅 up -d 时旧容器会带着 MISSING secret 继续跑）。
$COMPOSE up -d --no-deps --force-recreate gfcc-kernel

khealthy=0
i=1
while [ "$i" -le 30 ]; do
  if curl -sf --max-time 5 http://127.0.0.1:5211/health; then
    khealthy=1
    echo
    break
  fi
  sleep 2
  i=$((i + 1))
done
[ "$khealthy" = 1 ] || { echo "REFUSE: kernel /health 60 秒内未就绪，先看 docker logs gfcc-kernel" >&2; exit 1; }
kport="$(docker port gfcc-kernel 5211/tcp | head -n 1)"
[ "$kport" = "127.0.0.1:5211" ] || { echo "REFUSE: kernel 端口 $kport" >&2; exit 1; }

# 容器内必须看见密钥（只报长度，不打印值）
sec_len="$(docker exec gfcc-kernel sh -c 'printf %s "${SIGNAL_INGEST_SECRET:-}" | wc -c' | tr -d ' ')"
[ "${sec_len:-0}" -gt 0 ] || { echo "REFUSE: gfcc-kernel 容器内 SIGNAL_INGEST_SECRET 仍为空（no-auth 风险）" >&2; exit 1; }
echo "OK kernel SIGNAL_INGEST_SECRET 已注入（len=$sec_len）"

# SQLite 落盘校验 = 这一刀的迁移验证：库文件必须真的在卷上，不能是内存 stub。
for dbf in data/memory.db data/circle_flow.db; do
  docker exec gfcc-kernel test -s "/app/$dbf" \
    || { echo "REFUSE: kernel SQLite 库未落盘：$dbf（STORE_PROVIDER 未生效？）" >&2; exit 1; }
done
echo "OK kernel SQLite 落盘：memory.db / circle_flow.db"

# /circle/ 会场入口冒烟（nginx include 仍未解，这只打本机回环）。
ccode="$(curl -s -o /tmp/circle-smoke.html -w '%{http_code}' --max-time 10 http://127.0.0.1:5211/circle/ || true)"
[ "$ccode" = "200" ] || { echo "REFUSE: kernel /circle/ HTTP $ccode" >&2; exit 1; }
grep -qi "circle" /tmp/circle-smoke.html || { echo "REFUSE: /circle/ 响应不像会场页" >&2; exit 1; }
rm -f /tmp/circle-smoke.html

# ---- 鉴权门禁（Dell/Win 2026-11-02）：禁止 no-auth 回归 ----
# 未签名 → 401；value-axes（ETHOS 空）→ 503；带签名但混入职位分字段 → 422；合法签名 → 200
unsigned_code="$(curl -s -o /tmp/sig-unsigned.json -w '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' \
  -d '{"signal_type":"personality_beacon","user_id_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","nonce":"stagingunsigned1","payload":{"personality_type":"INTJ","source":"planetx"}}' \
  http://127.0.0.1:5211/v1/signal-ingest || true)"
[ "$unsigned_code" = "401" ] || { echo "REFUSE: 未签名 ingest 期望 401，实际 $unsigned_code（疑似 no-auth）：$(head -c 200 /tmp/sig-unsigned.json)" >&2; exit 1; }
echo "OK 未签名 ingest → 401"

va_code="$(curl -s -o /tmp/va-smoke.json -w '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' \
  -d '{"op":"read","user_id_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' \
  http://127.0.0.1:5211/v1/identity/value-axes || true)"
[ "$va_code" = "503" ] || { echo "REFUSE: value-axes 期望 503 auth_unconfigured（预发 ETHOS 空），实际 $va_code：$(head -c 200 /tmp/va-smoke.json)" >&2; exit 1; }
echo "OK value-axes → 503"

BODY_BAD='{"signal_type":"personality_beacon","user_id_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","nonce":"stagingjobfields1","payload":{"personality_type":"INTJ","source":"planetx","salary_match":1,"overall":1}}'
SIG_BAD="$(SIGNAL_INGEST_SECRET="$(grep '^SIGNAL_INGEST_SECRET=' "$REPO/.staging-gfcc.env" | cut -d= -f2-)" python3 -c 'import hmac,hashlib,os,sys; print(hmac.new(os.environ["SIGNAL_INGEST_SECRET"].encode(), sys.argv[1].encode(), hashlib.sha256).hexdigest())' "$BODY_BAD")"
job_code="$(curl -s -o /tmp/job-fields.json -w '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' -H "X-Signature: $SIG_BAD" \
  -d "$BODY_BAD" http://127.0.0.1:5211/v1/signal-ingest || true)"
[ "$job_code" = "422" ] || { echo "REFUSE: 职位分字段混入 beacon 期望 422，实际 $job_code：$(head -c 200 /tmp/job-fields.json)" >&2; exit 1; }
echo "OK job-score 字段拒绝 → 422"

BODY_OK='{"signal_type":"personality_beacon","user_id_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","nonce":"stagingsignedok01","payload":{"personality_type":"INTJ","source":"planetx"}}'
SIG_OK="$(SIGNAL_INGEST_SECRET="$(grep '^SIGNAL_INGEST_SECRET=' "$REPO/.staging-gfcc.env" | cut -d= -f2-)" python3 -c 'import hmac,hashlib,os,sys; print(hmac.new(os.environ["SIGNAL_INGEST_SECRET"].encode(), sys.argv[1].encode(), hashlib.sha256).hexdigest())' "$BODY_OK")"
signed_code="$(curl -s -o /tmp/sig-ok.json -w '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' -H "X-Signature: $SIG_OK" \
  -d "$BODY_OK" http://127.0.0.1:5211/v1/signal-ingest || true)"
[ "$signed_code" = "200" ] || { echo "REFUSE: 合法签名 ingest 期望 200，实际 $signed_code：$(head -c 200 /tmp/sig-ok.json)" >&2; exit 1; }
echo "OK 合法签名 ingest → 200"
rm -f /tmp/sig-unsigned.json /tmp/va-smoke.json /tmp/job-fields.json /tmp/sig-ok.json

kver="$(grep -m1 '^version' "$KERNEL_SRC/services/gfcc_kernel/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"
kcid="$(docker inspect -f '{{.Id}}' gfcc-kernel)"
kdigest="$(docker image inspect "$(docker inspect -f '{{.Image}}' gfcc-kernel)" -f '{{.Id}}')"

printf 'vultr=%s\ngfcc=%s\nl0=1.3.0\nschema=memory.v1\nkernel=%s@%s\nkernel_container=%s\nkernel_image_digest=%s\n' \
  "$VULTR_SHA" "$GFCC_SHA" "$kver" "$(printf %s "$GFCC_SHA" | cut -c1-7)" "$kcid" "$kdigest" > "$REPO/.staging-delivery"
