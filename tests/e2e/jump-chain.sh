#!/usr/bin/env bash
# =============================================================
# jump-chain.sh — 生产跳转链路端到端断言（只读，不写任何远端状态）
#
#   覆盖「营销站 → 收银 → API → 应用登录 → circle」整条业务跳转链：
#     1) 营销站 genz.ltd 仍是 Vercel/静态站，且导航里保留了终端入口
#     2) 收银入口 appRegisterUrl → tspace.genz.ltd/register 真的返回 SPA
#     3) api.genz.ltd 的定价接口按 Origin 回显 CORS，且内容是新加坡后端
#     4) CORS 负向：陌生 Origin 不得被回显（防把 * 写回）
#     5) app.genz.ltd → api.genz.ltd 登录接口存在（GET 405 / POST 4xx 而非 5xx）
#     6) circle.genz.ltd → SG kernel（首页 200 + api/status 422 缺 circle_id）
#     7) www.genz.ltd 单独报告落点（当前=Vercel 的 Genzer Terminal，Supabase 承载）
#
#   用法:
#     bash tests/e2e/jump-chain.sh              # 现网断言
#     EXPECT_WWW=vercel bash tests/e2e/jump-chain.sh   # 把 www 落点也纳入硬断言
#     EXPECT_WWW=sg   ...                       # 期望 www 已迁新加坡
#
#   退出码：0 = 全部通过；1 = 有断言失败（明细见输出）
# =============================================================
set -uo pipefail

TIMEOUT="${TIMEOUT:-20}"
EXPECT_WWW="${EXPECT_WWW:-any}"   # any | vercel | sg
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP" 2>/dev/null || true' EXIT

PASS=0
FAIL=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
info() { printf '  \033[36m·\033[0m %s\n' "$1"; }

# fetch URL OUT HEADERS [extra curl args...] → 打印 HTTP 码
fetch() {
  local url="$1" out="$2" hdr="$3"; shift 3
  curl -sS --max-time "$TIMEOUT" -o "$out" -D "$hdr" -w '%{http_code}' "$@" "$url" 2>/dev/null || echo "000"
}

hdr() { grep -i "^$2:" "$1" 2>/dev/null | tail -1 | sed "s/^[^:]*: *//" | tr -d '\r'; }

# 用 python 做 JSON 断言（本机无 jq）
pyjson() { python -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));print($1)" "$2" 2>/dev/null; }

echo "=== 1. 营销站 genz.ltd（静态站 + 终端入口）==="
c=$(fetch https://genz.ltd/ "$TMP/apex.html" "$TMP/apex.hdr")
[ "$c" = "200" ] && ok "genz.ltd / → 200" || bad "genz.ltd / → $c"
ASSET=$(grep -oE 'src="/assets/index-[^"]+\.js"' "$TMP/apex.html" | head -1 | sed 's/src="//;s/"//')
if [ -n "$ASSET" ]; then
  c=$(fetch "https://genz.ltd$ASSET" "$TMP/apex.js" "$TMP/apexjs.hdr")
  if [ "$c" = "200" ] && grep -q "https://www.genz.ltd" "$TMP/apex.js"; then
    ok "导航「终端」入口 = https://www.genz.ltd（bundle 内实锤）"
  else
    bad "bundle 内找不到 http(s)://www.genz.ltd 终端入口（code=$c）"
  fi
else
  bad "未能从 genz.ltd 首页定位主 JS 资源"
fi
grep -q "https://tspace.genz.ltd/register" "$TMP/apex.js" 2>/dev/null \
  && ok "appRegisterUrl = https://tspace.genz.ltd/register（bundle 内实锤）" \
  || bad "bundle 内找不到 appRegisterUrl=tspace/register"
grep -q "https://api.genz.ltd" "$TMP/apex.js" 2>/dev/null \
  && ok "apiBase = https://api.genz.ltd（bundle 内实锤）" \
  || bad "bundle 内找不到 apiBase=api.genz.ltd"

echo "=== 2. 收银入口 tspace.genz.ltd/register ==="
c=$(fetch https://tspace.genz.ltd/register "$TMP/reg.html" "$TMP/reg.hdr")
if [ "$c" = "200" ] && grep -qiE '<div id="root"|/assets/' "$TMP/reg.html"; then
  ok "tspace /register → 200，返回 SPA 外壳"
else
  bad "tspace /register → $c（body $(wc -c < "$TMP/reg.html" 2>/dev/null || echo 0) B）"
fi
info "响应头 server=$(hdr "$TMP/reg.hdr" server)"

echo "=== 3. 定价接口（Origin: https://genz.ltd）==="
c=$(fetch "https://api.genz.ltd/v1/payment/providers?region=US" "$TMP/prov.json" "$TMP/prov.hdr" -H 'Origin: https://genz.ltd')
acao=$(hdr "$TMP/prov.hdr" access-control-allow-origin)
if [ "$c" = "200" ]; then
  ok "providers?region=US → 200"
  [ "$(pyjson "','.join(d.get('providers',[]))" "$TMP/prov.json")" = "stripe" ] \
    && ok "providers=[stripe]" || bad "providers 非 [stripe]：$(head -c 120 "$TMP/prov.json")"
  [ "$(pyjson "str(d.get('region'))" "$TMP/prov.json")" = "US" ] \
    && ok "region=US" || bad "region 非 US"
  [ "$(pyjson "str(d.get('stub_mode')).lower()" "$TMP/prov.json")" = "false" ] \
    && ok "stub_mode=false（真 Stripe，不是桩）" || bad "stub_mode 非 false"
else
  bad "providers → $c"
fi
[ "$acao" = "https://genz.ltd" ] && ok "CORS 回显 Origin=genz.ltd" || bad "CORS ACAO=$acao（期望 https://genz.ltd）"

c=$(fetch "https://api.genz.ltd/v1/payment/plans?region=US" "$TMP/plans.json" "$TMP/plans.hdr" -H 'Origin: https://genz.ltd')
acao2=$(hdr "$TMP/plans.hdr" access-control-allow-origin)
[ "$c" = "200" ] && ok "plans?region=US → 200（$(wc -c < "$TMP/plans.json") B）" || bad "plans → $c"
[ "$acao2" = "https://genz.ltd" ] && ok "plans CORS 回显 genz.ltd" || bad "plans ACAO=$acao2"

echo "=== 4. CORS 负向（陌生 Origin 不得回显）==="
fetch "https://api.genz.ltd/v1/payment/providers?region=US" "$TMP/evil.json" "$TMP/evil.hdr" -H 'Origin: https://evil.example' >/dev/null
acao3=$(hdr "$TMP/evil.hdr" access-control-allow-origin)
case "$acao3" in
  ""|"https://evil.example"|"*")
    [ "$acao3" = "https://evil.example" ] && bad "陌生 Origin 被回显（CORS 失守）" || { [ "$acao3" = "*" ] && bad "ACAO=*（过宽）" || ok "陌生 Origin 不回显（无 ACAO）"; } ;;
  *) ok "陌生 Origin 未放行（ACAO=$acao3）" ;;
esac

echo "=== 5. app.genz.ltd → api.genz.ltd 登录链路 ==="
c=$(fetch "https://api.genz.ltd/v1/auth/login" "$TMP/login_get.json" "$TMP/login_get.hdr" -H 'Origin: https://app.genz.ltd')
acao4=$(hdr "$TMP/login_get.hdr" access-control-allow-origin)
[ "$c" = "405" ] && ok "GET /v1/auth/login → 405（路由存在、只收 POST）" || bad "GET /v1/auth/login → $c（期望 405）"
[ "$acao4" = "https://app.genz.ltd" ] && ok "登录 CORS 回显 app.genz.ltd" || bad "登录 ACAO=$acao4"

c=$(fetch "https://api.genz.ltd/v1/auth/login" "$TMP/pre.json" "$TMP/pre.hdr" \
      -X OPTIONS -H 'Origin: https://app.genz.ltd' \
      -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type')
acao5=$(hdr "$TMP/pre.hdr" access-control-allow-origin)
meth=$(hdr "$TMP/pre.hdr" access-control-allow-methods)
case "$c" in 200|204) ok "OPTIONS 预检 → $c" ;; *) bad "OPTIONS 预检 → $c" ;; esac
[ "$acao5" = "https://app.genz.ltd" ] && ok "预检 CORS 回显 app.genz.ltd" || bad "预检 ACAO=$acao5"
echo "$meth" | grep -qi "POST" && ok "预检 allow-methods 含 POST" || bad "预检 allow-methods=$meth"

c=$(fetch "https://api.genz.ltd/v1/auth/login" "$TMP/post.json" "$TMP/post.hdr" \
      -X POST -H 'Origin: https://app.genz.ltd' -H 'Content-Type: application/json' -d '{"email":"probe@invalid.test","password":"x"}')
[ "${c:0:1}" = "4" ] && ok "POST 假凭据 → $c（4xx，非 500）" || bad "POST 假凭据 → $c（期望 4xx）"

echo "=== 6. circle.genz.ltd → SG kernel ==="
c=$(fetch https://circle.genz.ltd/circle/ "$TMP/circle.html" "$TMP/circle.hdr")
size=$(wc -c < "$TMP/circle.html" 2>/dev/null || echo 0)
[ "$c" = "200" ] && ok "circle /circle/ → 200（$size B）" || bad "circle /circle/ → $c"
sha=$(sha256sum < "$TMP/circle.html" 2>/dev/null | cut -d' ' -f1)
info "circle 首页 SHA-256=${sha:-未取到}"
c=$(fetch https://circle.genz.ltd/circle/api/status "$TMP/cs.json" "$TMP/cs.hdr")
if [ "$c" = "422" ] && grep -q "circle_id" "$TMP/cs.json"; then
  ok "circle /circle/api/status → 422 missing circle_id（kernel 应答）"
else
  bad "circle /circle/api/status → $c（期望 422 缺 circle_id）"
fi

echo "=== 7. www.genz.ltd（终端站，当前独立栈）==="
c=$(fetch https://www.genz.ltd/ "$TMP/www.html" "$TMP/www.hdr")
srv=$(hdr "$TMP/www.hdr" server)
nx=$(hdr "$TMP/www.hdr" x-powered-by)
info "首页 → $c | server=$srv${nx:+ | x-powered-by=$nx}"
c2=$(fetch https://www.genz.ltd/auth/login "$TMP/wwl.html" "$TMP/wwl.hdr")
info "/auth/login → $c2"
case "$EXPECT_WWW" in
  vercel) echo "$srv" | grep -qi vercel && ok "www 落点=Vercel（符合当前双站口径）" || bad "www 落点非 Vercel（server=$srv）" ;;
  sg)     echo "$srv$nx" | grep -qiE "vercel" && bad "www 仍在 Vercel（期望已迁 SG）" || ok "www 已不在 Vercel（server=$srv）" ;;
  any)    info "www 落点仅报告，不硬断言（EXPECT_WWW=vercel|sg 可纳入门禁）" ;;
esac
[ "$c" = "200" ] && ok "www 首页可达 200" || bad "www 首页 → $c"

echo
echo "=== 汇总：$PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
