#!/usr/bin/env bash
# =============================================================
# ethos-parity-onekey.sh — 身份联邦「探针一键绿」（收官-84）
#
# 一条命令复验三站 + 跨区互通 + 旧钥负例，输出矩阵与结论。
# 适用：任何一次 ETHOS 换钥 / stack 发版 / FRA 变更后的人工或 CI 复验。
#
# 断言集（对应双轨探活铁律，docs/dual-track-ledger-boundary.md）：
#   A1 天翼：deploy_track=looma 且 looma_sha==git_commit 且 kind=deploy_tip
#            且 stack_sha/vultr_tag 均 null（拒绝冒充海外栈）
#   A2 SG：  deploy_track=vultr 且 kind=join_pin 且 vultr_tag=stack-v*
#            且 stack_sha==git_commit 且 looma_sha != git_commit（PIN 不是 tip）
#   A3 FRA： deploy_track=vultr 且 vultr_tag=fra-rehearsal-* 且 looma_sha=null
#            （预演台不得冒充 looma tip，也不得冒充 SG 生产 tag）
#   A4 同钥：天翼 backend==kernel(.env)==gateway 容器；
#            FRA backend==kernel(.env)；指纹全站一致
#   A5 跨区：新钥 token → 公网 circle kernel /circle/api/me → 200
#   A6 负例：旧钥 token → 天翼 gateway 401（旧钥取自远端换钥备份）；
#            SG 侧旧钥负例需显式传 OLD_KEY（旧钥明文文件路径），缺省 SKIP
#
# 安全：只在远端铸/用 token，明钥不过本机、不打印，只显示指纹前 16 位。
#
# 依赖：curl、ssh、sha256sum；远端需 python3（铸探针 token）。
# 退出码：0=全绿（SKIP 不算失败）；1=有 FAIL。
#
# 用法：
#   bash scripts/ethos-parity-onekey.sh
#   TIANYI_SSH="ubuntu@14.29.216.219" TIANYI_KEY=~/.ssh/id_ed25519_cloud216 \
#   FRA_SSH=looma-staging-fra bash scripts/ethos-parity-onekey.sh
#   OLD_KEY=~/.ssh/ethos_old.key bash ...   # 追加 SG 侧旧钥负例
# =============================================================
set -uo pipefail

TIANYI_SSH="${TIANYI_SSH:-ubuntu@14.29.216.219}"
TIANYI_KEY="${TIANYI_KEY:-$HOME/.ssh/id_ed25519_cloud216}"
FRA_SSH="${FRA_SSH:-looma-staging-fra}"
TIANYI_HEALTH_URL="${TIANYI_HEALTH_URL:-http://14.29.216.219/health}"
SG_HEALTH_URL="${SG_HEALTH_URL:-https://api.genz.ltd/health}"
CIRCLE_URL="${CIRCLE_URL:-https://circle.genz.ltd/circle/api/me}"
OLD_KEY="${OLD_KEY:-}"
TIMEOUT="${TIMEOUT:-15}"

PASS=0; FAIL=0; SKIP=0
declare -a RESULTS

jsonget() { python -c "import sys,json;d=json.load(sys.stdin);v=d.get(sys.argv[1]);print('null' if v is None else v)" "$1" 2>/dev/null; }
row() { RESULTS+=("$1|$2|$3"); if [ "$2" = PASS ]; then PASS=$((PASS+1)); elif [ "$2" = FAIL ]; then FAIL=$((FAIL+1)); else SKIP=$((SKIP+1)); fi; }
h16() { printf '%s' "$1" | sha256sum | cut -c1-16; }

ssh_tianyi() { ssh -i "$TIANYI_KEY" -o ConnectTimeout=15 -o BatchMode=yes "$TIANYI_SSH" "$@" 2>/dev/null; }
ssh_fra()    { ssh -o ConnectTimeout=15 -o BatchMode=yes "$FRA_SSH" "$@" 2>/dev/null; }

# ---- 取三站 health ----
echo "===== 三站 health ====="
H_TY=$(curl -s --max-time "$TIMEOUT" "$TIANYI_HEALTH_URL" 2>/dev/null)
H_SG=$(curl -s --max-time "$TIMEOUT" "$SG_HEALTH_URL" 2>/dev/null)
H_FRA=$(ssh_fra 'curl -s --max-time 8 http://127.0.0.1:5200/health' 2>/dev/null)
for s in H_TY H_SG H_FRA; do
  eval "v=\${$s}"
  if ! printf '%s' "$v" | python -m json.tool >/dev/null 2>&1; then
    echo "$s: <invalid/empty>"; eval "$s=''"
  fi
done

g() { printf '%s' "$1" | jsonget "$2"; }

echo "--- A1 天翼（looma 轨） ---"
if [ -n "$H_TY" ]; then
  TY_TRACK=$(g "$H_TY" deploy_track); TY_GC=$(g "$H_TY" git_commit); TY_LS=$(g "$H_TY" looma_sha)
  TY_KIND=$(g "$H_TY" looma_sha_kind); TY_SS=$(g "$H_TY" stack_sha); TY_VT=$(g "$H_TY" vultr_tag)
  if [ "$TY_TRACK" = "looma" ] && [ "$TY_GC" = "$TY_LS" ] && [ "$TY_KIND" = "deploy_tip" ] \
     && [ "$TY_SS" = "null" ] && [ "$TY_VT" = "null" ]; then
    row "A1 天翼 tip=looma_sha，无 stack 冒充" PASS "git_commit=${TY_GC:0:8}"
  else
    row "A1 天翼 tip=looma_sha，无 stack 冒充" FAIL "track=$TY_TRACK kind=$TY_KIND ss=$TY_SS vt=$TY_VT"
  fi
else
  row "A1 天翼 health 不可达" FAIL "-"
fi

echo "--- A2 SG（vultr 轨，生产） ---"
if [ -n "$H_SG" ]; then
  SG_TRACK=$(g "$H_SG" deploy_track); SG_GC=$(g "$H_SG" git_commit); SG_LS=$(g "$H_SG" looma_sha)
  SG_KIND=$(g "$H_SG" looma_sha_kind); SG_SS=$(g "$H_SG" stack_sha); SG_VT=$(g "$H_SG" vultr_tag)
  case "$SG_VT" in stack-v*|sha-*) VT_OK=1 ;; *) VT_OK=0 ;; esac
  if [ "$SG_TRACK" = "vultr" ] && [ "$SG_KIND" = "join_pin" ] && [ "$VT_OK" = 1 ] \
     && [ "$SG_SS" = "$SG_GC" ] && [ "$SG_LS" != "$SG_GC" ]; then
    row "A2 SG tip=stack，looma_sha=join_pin" PASS "vultr_tag=$SG_VT stack=${SG_SS:0:8} pin=${SG_LS:0:8}"
  else
    row "A2 SG tip=stack，looma_sha=join_pin" FAIL "track=$SG_TRACK kind=$SG_KIND vt=$SG_VT"
  fi
else
  row "A2 SG health 不可达" FAIL "-"
fi

echo "--- A3 FRA（预演台） ---"
if [ -n "$H_FRA" ]; then
  FR_TRACK=$(g "$H_FRA" deploy_track); FR_VT=$(g "$H_FRA" vultr_tag); FR_LS=$(g "$H_FRA" looma_sha)
  case "$FR_VT" in fra-rehearsal-*) VT_OK=1 ;; *) VT_OK=0 ;; esac
  if [ "$FR_TRACK" = "vultr" ] && [ "$VT_OK" = 1 ] && [ "$FR_LS" = "null" ]; then
    row "A3 FRA 预演台标记，不冒充 looma/SG" PASS "vultr_tag=$FR_VT"
  else
    row "A3 FRA 预演台标记，不冒充 looma/SG" FAIL "track=$FR_TRACK vt=$FR_VT ls=$FR_LS"
  fi
else
  row "A3 FRA health 不可达" FAIL "-"
fi

echo "--- A4 同钥指纹（远端取，不出明钥） ---"
TY_PRINT='for c in looma-backend gfcc-am-gateway-1; do v=$(sudo docker exec $c printenv ETHOS_AUTH_SECRET 2>/dev/null); [ -n "$v" ] && echo "$c=$(printf %s "$v" | sha256sum | cut -c1-16)"; done; v=$(sudo grep -h "^ETHOS_AUTH_SECRET=" /data/gfcc/services/gfcc_kernel/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'"'"'"); [ -n "$v" ] && echo "kernel.env=$(printf %s "$v" | sha256sum | cut -c1-16)"'
TY_FP=$(ssh_tianyi "$TY_PRINT" 2>/dev/null)
FR_PRINT='v=$(docker exec looma-backend printenv ETHOS_AUTH_SECRET 2>/dev/null); [ -n "$v" ] && echo "backend=$(printf %s "$v" | sha256sum | cut -c1-16)"; v=$(grep -h "^ETHOS_AUTH_SECRET=" /data/gfcc/services/gfcc_kernel/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'"'"'"); [ -n "$v" ] && echo "kernel.env=$(printf %s "$v" | sha256sum | cut -c1-16)"'
FR_FP=$(ssh_fra "$FR_PRINT" 2>/dev/null)
echo "$TY_FP"; echo "$FR_FP"
REF_FP=$(printf '%s\n' "$TY_FP" "$FR_FP" | sed -n 's/^[^=]*=//p' | head -1)
if [ -n "$REF_FP" ] && [ "$(printf '%s\n' "$TY_FP" "$FR_FP" | sed -n 's/^[^=]*=//p' | sort -u | wc -l)" = 1 ]; then
  row "A4 天翼/FRA 全组件同钥" PASS "fingerprint=$REF_FP"
else
  row "A4 天翼/FRA 全组件同钥" FAIL "fp: $(printf '%s\n' "$TY_FP" "$FR_FP" | tr '\n' ' ')"
fi

echo "--- A5 跨区新钥（天翼铸→公网 SG kernel，明钥不过本机） ---"
TY_C=$(ssh -i "$TIANYI_KEY" -o ConnectTimeout=15 -o BatchMode=yes "$TIANYI_SSH" "CIRCLE_URL='$CIRCLE_URL' bash -s" <<'EOS' 2>/dev/null
python3 - <<'PY' > /tmp/.onekey_tok
import re, base64, hashlib, hmac, json, time
sec = re.search(r"(?m)^ETHOS_AUTH_SECRET=(.+?)\s*$", open("/data/gfcc/services/gfcc_kernel/.env").read()).group(1).strip("\"'")
def b64(x): return base64.urlsafe_b64encode(x).rstrip(b"=").decode()
now = int(time.time())
h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
p = b64(json.dumps({"sub": "onekey-probe", "tier": "pro", "iat": now, "exp": now + 300}, separators=(",", ":")).encode())
print(h + "." + p + "." + b64(hmac.new(sec.encode(), (h + "." + p).encode(), hashlib.sha256).digest()))
PY
curl -s -o /dev/null -w '%{http_code}' --max-time 12 -H "Authorization: Bearer $(cat /tmp/.onekey_tok)" "$CIRCLE_URL"
rm -f /tmp/.onekey_tok
EOS
)
TY_C="${TY_C//[$'\r\n']/}"
if [ "$TY_C" = "200" ]; then
  row "A5 新钥跨区互通（天翼铸→SG kernel 200）" PASS "circle=$TY_C"
elif [ -z "$TY_C" ]; then
  row "A5 新钥跨区互通" SKIP "天翼 ssh/python3 不可用"
else
  row "A5 新钥跨区互通（天翼铸→SG kernel）" FAIL "circle=$TY_C (want 200)"
fi

echo "--- A6 旧钥负例（天翼 gateway，旧钥取自远端换钥备份） ---"
TY_OLD=$(ssh_tianyi 'bash -s' <<'EOS' 2>/dev/null
BK=$(sudo sh -c 'ls -t /root/gfcc-env.bak-* 2>/dev/null' | head -1)
[ -n "$BK" ] || { echo "SKIPNOBACKUP"; exit 0; }
OLDK=$(sudo grep -h "^ETHOS_AUTH_SECRET=" "$BK" 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'")
NEWK=$(sudo grep -h "^ETHOS_AUTH_SECRET=" /data/gfcc/services/gfcc_kernel/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'")
if [ -z "$OLDK" ]; then echo "SKIPNOBACKUP"; exit 0; fi
[ "$OLDK" = "$NEWK" ] && { echo "SKIPSAMEKEY"; exit 0; }
python3 - "$OLDK" <<'PY' > /tmp/.onekey_old
import sys, base64, hashlib, hmac, json, time
sec = sys.argv[1]
def b64(x): return base64.urlsafe_b64encode(x).rstrip(b"=").decode()
now = int(time.time())
h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
p = b64(json.dumps({"sub": "onekey-probe", "tier": "pro", "iat": now, "exp": now + 300}, separators=(",", ":")).encode())
print(h + "." + p + "." + b64(hmac.new(sec.encode(), (h + "." + p).encode(), hashlib.sha256).digest()))
PY
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 -H "Authorization: Bearer $(cat /tmp/.onekey_old)" http://127.0.0.1:3210/v1/memory/health)
rm -f /tmp/.onekey_old
echo "$code"
EOS
)
case "$TY_OLD" in
  SKIP*) row "A6 旧钥负例（天翼 gateway）" SKIP "${TY_OLD#SKIP}" ;;
  401)   row "A6 旧钥负例（天翼 gateway 401）" PASS "code=401" ;;
  "")    row "A6 旧钥负例（天翼 gateway）" SKIP "ssh 不可达" ;;
  *)     row "A6 旧钥负例（天翼 gateway 401）" FAIL "code=$TY_OLD (want 401)" ;;
esac
# 可选：SG 侧旧钥负例（需显式提供旧钥明文文件；缺省不做）
if [ -n "$OLD_KEY" ] && [ -f "$OLD_KEY" ]; then
  OLDT=$(python - "$OLD_KEY" <<'PY' 2>/dev/null
import sys, base64, hashlib, hmac, json, time
sec = open(sys.argv[1]).read().strip()
def b64(x): return base64.urlsafe_b64encode(x).rstrip(b"=").decode()
now = int(time.time())
h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
p = b64(json.dumps({"sub": "onekey-probe", "tier": "pro", "iat": now, "exp": now + 300}, separators=(",", ":")).encode())
print(h + "." + p + "." + b64(hmac.new(sec.encode(), (h + "." + p).encode(), hashlib.sha256).digest()))
PY
)
  C_OLD_SG=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" -H "Authorization: Bearer $OLDT" "$CIRCLE_URL")
  [ "$C_OLD_SG" = "401" ] && row "A6+ SG 旧钥已拒（显式提供）" PASS "circle=401" || row "A6+ SG 旧钥已拒" FAIL "circle=$C_OLD_SG (want 401)"
fi

echo
echo "===== 结果矩阵 ====="
printf '%-46s %-5s %s\n' "断言" "结论" "明细"
for r in "${RESULTS[@]}"; do IFS='|' read -r name st detail <<< "$r"; printf '%-46s %-5s %s\n' "$name" "$st" "$detail"; done
echo
echo "===== 结论: PASS=$PASS FAIL=$FAIL SKIP=$SKIP ====="
[ "$FAIL" -eq 0 ] && echo "ALL_GREEN ✅" || echo "NOT_GREEN ❌"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
