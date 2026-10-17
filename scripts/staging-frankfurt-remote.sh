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
docker tag looma-zervi-tatha:latest "looma-zervi-tatha:pre-$VULTR_SHA" 2>/dev/null || true
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

tport="$(docker port tatha-mbti 8010/tcp | head -n 1)"
[ "$tport" = "127.0.0.1:5210" ] || { echo "REFUSE: tatha 端口 $tport" >&2; exit 1; }
pport="$(docker port gfcc-pgvector 5432/tcp | head -n 1)"
[ "$pport" = "127.0.0.1:5434" ] || { echo "REFUSE: gfcc-pgvector 端口 $pport" >&2; exit 1; }

ready=0
i=1
while [ "$i" -le 20 ]; do
  if docker exec gfcc-pgvector pg_isready -U gfcc -d gfcc; then
    ready=1
    break
  fi
  sleep 2
  i=$((i + 1))
done
[ "$ready" = 1 ] || { echo "REFUSE: gfcc-pgvector 40 秒内未就绪" >&2; exit 1; }
db="$(docker exec gfcc-pgvector psql -U gfcc -d gfcc -tAc 'SELECT current_database()')"
[ "$db" = "gfcc" ] || { echo "REFUSE: 当前库是 $db" >&2; exit 1; }

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

printf 'vultr=%s\ngfcc=%s\nl0=1.3.0\n' "$VULTR_SHA" "$GFCC_SHA" > "$REPO/.staging-delivery"

if curl -sf --max-time 20 http://127.0.0.1:5210/openapi.json | python3 -c 'import json,sys; paths=json.load(sys.stdin).get("paths",{}); sys.exit(0 if any("recall" in p for p in paths) else 1)'; then
  echo "OK Tatha OpenAPI 含 recall"
else
  echo "::warning::Tatha 镜像没有 memory.recall。契约钉已是 1.3.0，services/tatha 还没有这条路由，也不读 X-Actor-Sub。zervi-rust 不在本机。"
fi
