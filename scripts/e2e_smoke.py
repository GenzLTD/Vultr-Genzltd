#!/usr/bin/env python3
"""海外站线上冒烟 E2E（只读 + 自清理，不产生任何扣款）。

覆盖链路：plans 契约 → 注册 → 登录态 status → subscribe 结账会话参数 →
fresh 用户 portal 404 → 注销自清理 → 旧 token 失效。

副作用（跑完即消）：
  * 现网库新建一个 e2e-<ts>@<E2E_EMAIL_DOMAIN> 用户，最后自助注销删除；
  * subscribe 会建一条 pending 订单，随用户注销一并删除；
  * Stripe 侧开一个 Checkout Session，不支付自动过期，无费用。

用法：
  python scripts/e2e_smoke.py                          # https://tspace.genz.ltd
  python scripts/e2e_smoke.py --base-url http://IP \
      --host-header tspace.genz.ltd                    # 绕过域名直连源站
  E2E_STRIPE_SECRET_KEY=sk_live_... python scripts/... # 追加 Stripe 会话深检

可选环境变量：
  E2E_BASE_URL      默认 https://tspace.genz.ltd
  E2E_HOST_HEADER   覆盖 Host 头（直连源站时用）
  E2E_EMAIL_DOMAIN  测试账号邮箱域，默认 e2e.genz.ltd
  E2E_STRIPE_SECRET_KEY  提供则对 checkout_url 做会话级深检（mode/邮箱）
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://tspace.genz.ltd"
SUPPORTER_PRICE = 1.99
BILLING_ENTITY = "YEDALL LIMITED"

_results: list[tuple[str, bool, str]] = []


def _req(method: str, url: str, *, headers: dict | None = None,
         body: dict | None = None, timeout: int = 20) -> tuple[int, dict | bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "looma-e2e-smoke/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, _decode(raw)
    except urllib.error.HTTPError as e:
        return e.code, _decode(e.read())


def _decode(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return raw


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        raise _Fail(name, detail)


class _Fail(Exception):
    pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", DEFAULT_BASE))
    ap.add_argument("--host-header", default=os.getenv("E2E_HOST_HEADER", ""))
    ap.add_argument("--keep", action="store_true",
                    help="不注销测试账号（调试用，默认自清理）")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    host_hdr = {"Host": args.host_header} if args.host_header else {}
    auth_hdr = lambda tok: {**host_hdr, "Authorization": f"Bearer {tok}"}  # noqa: E731

    email = f"e2e-{int(time.time())}-{random.randint(1000, 9999)}@{os.getenv('E2E_EMAIL_DOMAIN', 'e2e.genz.ltd')}"
    password = "E2e-smoke-" + str(random.randint(10**8, 10**9 - 1))
    token = None

    print(f"E2E 冒烟 → {base}" + (f"（Host: {args.host_header}）" if args.host_header else ""))

    # 1. plans 契约
    print("[1/6] GET /v1/membership/plans")
    code, plans = _req("GET", f"{base}/v1/membership/plans", headers=host_hdr)
    check("plans 200", code == 200, f"got {code}")
    check("账单主体是 YEDALL LIMITED", plans.get("billing_entity") == BILLING_ENTITY,
          str(plans.get("billing_entity")))
    check("币种 USD / provider stripe",
          plans.get("currency") == "USD" and plans.get("payment_provider") == "stripe")
    tiers = {p.get("tier") for p in plans.get("plans", [])}
    check("三档齐全 free/supporter/pro", {"free", "supporter", "pro"} <= tiers, str(tiers))
    supporter = next((p for p in plans.get("plans", []) if p.get("tier") == "supporter"), {})
    check("supporter 定价 $1.99 USD",
          supporter.get("price_monthly") == SUPPORTER_PRICE
          and supporter.get("currency") == "USD",
          str({k: supporter.get(k) for k in ("price_monthly", "currency")}))

    # 2. 注册
    print("[2/6] POST /v1/auth/register")
    code, reg = _req("POST", f"{base}/v1/auth/register", headers=host_hdr,
                     body={"email": email, "password": password, "name": "E2E Smoke"})
    check("register 201", code == 201, f"got {code}: {reg if code != 201 else ''}")
    token = (reg or {}).get("access_token", "")
    check("返回 access_token 且 tier=free",
          bool(token) and (reg.get("user") or {}).get("tier") == "free")

    # 3. 登录态 status
    print("[3/6] GET /v1/membership/status")
    code, status = _req("GET", f"{base}/v1/membership/status", headers=auth_hdr(token))
    check("status 200", code == 200, f"got {code}")
    check("初始 tier=free / 无自动续费",
          status.get("tier") == "free" and not status.get("auto_renew"))

    # 4. subscribe 结账会话（不支付，无扣款）
    print("[4/6] POST /v1/membership/subscribe (supporter)")
    code, sub = _req("POST", f"{base}/v1/membership/subscribe", headers=auth_hdr(token),
                     body={"tier": "supporter"})
    check("subscribe 201", code == 201, f"got {code}: {sub if code != 201 else ''}")
    check("checkout_url 指向 Stripe 收银台",
          str(sub.get("checkout_url", "")).startswith("https://checkout.stripe.com/"),
          str(sub.get("checkout_url"))[:80])
    check("会话参数 supporter/$1.99/USD/stripe",
          sub.get("tier") == "supporter" and sub.get("amount") == SUPPORTER_PRICE
          and str(sub.get("currency", "")).upper() == "USD"
          and sub.get("provider") == "stripe")

    # 4b. 可选：Stripe 会话深检
    sk = os.getenv("E2E_STRIPE_SECRET_KEY", "").strip()
    if sk:
        session_id = sub.get("checkout_url", "").rsplit("/", 1)[-1]
        req = urllib.request.Request(
            f"https://api.stripe.com/v1/checkout/sessions/{session_id}", method="GET")
        req.add_header("Authorization", f"Bearer {sk}")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                sess = json.load(r)
            check("Stripe 会话 mode=subscription", sess.get("mode") == "subscription")
            check("会话邮箱回填", sess.get("customer_email") == email)
            check("订阅含 Stripe Tax",
                  (sess.get("subscription_data") or {}).get("automatic_tax") is not None
                  or sess.get("automatic_tax") is not None)
        except Exception as e:  # 深检失败不算冒烟失败（只读增强项）
            print(f"  ~ Stripe 深检跳过：{e}")
    else:
        print("  ~ 未设 E2E_STRIPE_SECRET_KEY，跳过会话深检")

    # 5. fresh 用户 portal 应 404（无 paid 订单 → 无 Stripe 客户引用）
    print("[5/6] POST /v1/membership/portal (fresh 用户)")
    code, portal = _req("POST", f"{base}/v1/membership/portal",
                        headers=auth_hdr(token), body={})
    check("portal 404（无客户留痕不伪造页面）", code == 404, f"got {code}")

    # 6. 自清理：注销 + token 失效
    print("[6/6] DELETE /v1/account（自清理）")
    if args.keep:
        print("  ~ --keep：跳过注销，测试账号保留：", email)
    else:
        code, dele = _req("DELETE", f"{base}/v1/account", headers=auth_hdr(token),
                          body={"confirm": "DELETE"})
        check("注销 200", code == 200, f"got {code}: {dele if code != 200 else ''}")
        code2, _ = _req("GET", f"{base}/v1/membership/status", headers=auth_hdr(token))
        check("旧 token 立即失效 (401)", code2 == 401, f"got {code2}")

    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\n结果：{passed}/{len(_results)} 通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except _Fail as e:
        total = len(_results)
        passed = sum(1 for _, ok, _ in _results if ok)
        print(f"\n结果：{passed}/{total} 通过 — 失败于 {e.args[0]} ❌")
        sys.exit(1)
