"""会员自助管理（Stripe Billing Portal）测试。

Run: pytest tests/test_membership_billing_portal.py -v

背景（2026-10-11）：订阅能一键买，却**没有任何自助取消入口** —— 既不合规
（EU 消费者权利指令 / FTC negative-option 都要求"取消要和订阅一样容易"），
也把退订压力全推给客服。

本文件锁死三件事：

1. 没有 Stripe 客户留痕时给 404，不伪造一个"看起来能用"的管理页；
2. 有留痕时把正确的 customer id 交给 Stripe，并原样带上 return_url；
3. `return_url` 是开放重定向的现成入口 —— 站外 host 一律拒绝，
   绝不把用户从 Stripe 弹到钓鱼站。
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.manager import DatabaseManager  # noqa: E402
from src.payment.providers import stripe as stripe_mod  # noqa: E402
from src.services.membership.service import MembershipService  # noqa: E402

CONFIG = {"STRIPE_SECRET_KEY": "sk_test_dummy"}


class _Resp:
    """最小 requests.Response 替身。"""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    manager = DatabaseManager(path)
    manager.init_schema()
    yield manager
    os.unlink(path)


def _seed_paid(db, uid, out_trade_no, customer, sub, created_at=None):
    """建一笔已带 Stripe 引用留痕的订单（模拟 checkout 结算后的状态）。"""
    db.create_order(
        user_id=uid, plan_id="supporter_us", tier="supporter",
        amount=1.99, currency="USD", out_trade_no=out_trade_no,
    )
    order = db.get_order_by_out_trade_no(out_trade_no)
    db.merge_order_metadata(
        order["id"],
        {"stripe_customer_id": customer, "stripe_subscription_id": sub},
    )
    if created_at:
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE orders SET created_at = ? WHERE id = ?", (created_at, order["id"])
            )
    return order


# ── 1. 数据层：按用户反查 Stripe 引用 ──


class TestFindStripeRefs:
    def test_empty_when_no_order(self, db):
        uid = db.create_user(email="none@example.com")
        assert db.find_stripe_refs_for_user(uid) == {}

    def test_reads_latest_order(self, db):
        uid = db.create_user(email="refs@example.com")
        _seed_paid(db, uid, "LOOMA0001", "cus_old", "sub_old",
                   created_at="2026-01-01 00:00:00")
        _seed_paid(db, uid, "LOOMA0002", "cus_new", "sub_new",
                   created_at="2026-02-01 00:00:00")

        refs = db.find_stripe_refs_for_user(uid)
        assert refs["stripe_customer_id"] == "cus_new"
        assert refs["stripe_subscription_id"] == "sub_new"

    def test_ignores_orders_without_customer(self, db):
        uid = db.create_user(email="plain@example.com")
        db.create_order(
            user_id=uid, plan_id="supporter_us", tier="supporter",
            amount=1.99, currency="USD", out_trade_no="LOOMA0003",
        )
        assert db.find_stripe_refs_for_user(uid) == {}


# ── 2. 服务层：开会话 ──


class TestBillingPortalService:
    def test_no_customer_is_404_not_a_fake_page(self, db):
        uid = db.create_user(email="nocust@example.com")
        body, code = MembershipService().create_billing_portal(db, CONFIG, uid, "")
        assert code == 404
        assert body["error"] == "no_billing_customer"

    def test_session_carries_customer_and_return_url(self, db, monkeypatch):
        uid = db.create_user(email="cust@example.com")
        _seed_paid(db, uid, "LOOMA0010", "cus_1", "sub_1")

        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            captured["url"] = url
            captured["data"] = dict(data or {})
            captured["headers"] = dict(headers or {})
            return _Resp(
                {"url": "https://billing.stripe.com/p/session/test_1", "id": "bps_1"}
            )

        monkeypatch.setattr(stripe_mod.requests, "post", fake_post)

        body, code = MembershipService().create_billing_portal(
            db, CONFIG, uid, "https://app.example.com/account",
        )

        assert code == 200
        assert body["url"] == "https://billing.stripe.com/p/session/test_1"
        assert captured["url"].endswith("/billing_portal/sessions")
        assert captured["data"]["customer"] == "cus_1"
        assert captured["data"]["return_url"] == "https://app.example.com/account"
        assert captured["headers"]["Authorization"] == "Bearer sk_test_dummy"

    def test_return_url_omitted_when_empty(self, db, monkeypatch):
        uid = db.create_user(email="noret@example.com")
        _seed_paid(db, uid, "LOOMA0011", "cus_2", "sub_2")
        captured = {}

        def fake_post(url, data=None, headers=None, timeout=None):
            captured["data"] = dict(data or {})
            return _Resp({"url": "https://billing.stripe.com/p/session/test_2"})

        monkeypatch.setattr(stripe_mod.requests, "post", fake_post)
        MembershipService().create_billing_portal(db, CONFIG, uid, "")

        assert "return_url" not in captured["data"]

    def test_not_configured_is_503(self, db):
        uid = db.create_user(email="unconf@example.com")
        _seed_paid(db, uid, "LOOMA0012", "cus_3", "sub_3")
        body, code = MembershipService().create_billing_portal(db, {}, uid, "")
        assert code == 503
        assert body["error"] == "payment_not_configured"

    def test_upstream_error_is_502_without_leaking_details(self, db, monkeypatch):
        uid = db.create_user(email="boom@example.com")
        _seed_paid(db, uid, "LOOMA0013", "cus_4", "sub_4")

        def fake_post(url, data=None, headers=None, timeout=None):
            return _Resp({"error": {"message": "portal not configured for this account"}},
                         status_code=400)

        monkeypatch.setattr(stripe_mod.requests, "post", fake_post)
        body, code = MembershipService().create_billing_portal(db, CONFIG, uid, "")

        assert code == 502
        assert body["error"] == "portal_unavailable"
        # 上游原文不外泄给客户端（只留在日志里）
        assert "portal not configured" not in json.dumps(body, ensure_ascii=False)

    def test_missing_url_is_502(self, db, monkeypatch):
        uid = db.create_user(email="nourl@example.com")
        _seed_paid(db, uid, "LOOMA0014", "cus_5", "sub_5")
        monkeypatch.setattr(
            stripe_mod.requests, "post",
            lambda *a, **k: _Resp({"id": "bps_no_url"}),
        )
        body, code = MembershipService().create_billing_portal(db, CONFIG, uid, "")
        assert code == 502
        assert body["error"] == "portal_unavailable"


# ── 3. 路由层：return_url 开放重定向防护 ──


def _register(client, email, password="secret123"):
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "name": "Portal"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestMembershipRouteContract:
    """蓝图前缀回归：``/v1/membership/*`` 是前端与 nginx 共同约定的契约。

    曾经的配置：蓝图内路由已带 ``/membership/``，而注册前缀又写了
    ``/v1/membership`` → 实际拼成 ``/v1/membership/membership/*``。
    前端 Subscription.tsx 调 ``/v1/membership/plans``、nginx 配
    ``location /v1/membership/webhook/``，两边都对不上 —— 会员端点整体不可达。
    """

    def test_plans_reachable_at_contract_url(self, client):
        r = client.get("/v1/membership/plans")
        assert r.status_code == 200, r.get_data(as_text=True)

    def test_no_double_prefix(self, client):
        assert client.get("/v1/membership/membership/plans").status_code == 404

    def test_config_env_is_wired(self, monkeypatch):
        """MEMBERSHIP_PORTAL_RETURN_HOSTS 必须真的从 env 进到 app.config。

        config.py 是逐项 os.getenv 的显式列表 —— 漏接一行就会出现
        「.env 里写了、运行时读不到」的静默失效，所以在这里锁一下。
        """
        monkeypatch.setenv("MEMBERSHIP_PORTAL_RETURN_HOSTS", "app.example.com,www.example.com")
        monkeypatch.setenv("DATABASE_PATH", tempfile.mktemp(suffix=".db"))
        monkeypatch.setenv("JWT_SECRET", "x" * 32)

        from src.app import create_app

        app = create_app("testing")
        assert (
            app.config["MEMBERSHIP_PORTAL_RETURN_HOSTS"]
            == "app.example.com,www.example.com"
        )


class TestPortalRoute:
    def test_requires_auth(self, client):
        assert client.post("/v1/membership/portal", json={}).status_code == 401

    def test_rejects_foreign_host(self, client):
        token = _register(client, "portal-a@test.local")
        r = client.post(
            "/v1/membership/portal",
            headers=_auth(token),
            json={"return_url": "https://evil.example.com/phish"},
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_return_url"

    def test_rejects_non_http_scheme(self, client):
        token = _register(client, "portal-b@test.local")
        for bad in ("javascript:alert(1)", "/relative", "ftp://localhost/x"):
            r = client.post(
                "/v1/membership/portal",
                headers=_auth(token),
                json={"return_url": bad},
            )
            assert r.status_code == 400, bad
            assert r.get_json()["error"] == "invalid_return_url"

    def test_same_origin_passes_gate(self, client):
        """同源 return_url 通过校验，随后因无 Stripe 留痕而 404（而非 400）。"""
        token = _register(client, "portal-c@test.local")
        r = client.post(
            "/v1/membership/portal",
            headers=_auth(token),
            json={"return_url": "http://localhost/account"},
        )
        assert r.status_code == 404
        assert r.get_json()["error"] == "no_billing_customer"

    def test_no_return_url_passes_gate(self, client):
        token = _register(client, "portal-d@test.local")
        r = client.post("/v1/membership/portal", headers=_auth(token), json={})
        assert r.status_code == 404
        assert r.get_json()["error"] == "no_billing_customer"

    def test_whitelisted_host_passes_gate(self, client):
        token = _register(client, "portal-e@test.local")
        client.application.config["MEMBERSHIP_PORTAL_RETURN_HOSTS"] = "app.example.com"
        r = client.post(
            "/v1/membership/portal",
            headers=_auth(token),
            json={"return_url": "https://app.example.com/account"},
        )
        assert r.status_code == 404
        assert r.get_json()["error"] == "no_billing_customer"

    def test_origin_header_is_used_as_fallback_and_checked(self, client):
        token = _register(client, "portal-f@test.local")
        # 站外 Origin 不该被信任
        r = client.post(
            "/v1/membership/portal",
            headers={**_auth(token), "Origin": "https://evil.example.com"},
            json={},
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_return_url"

        # 同源 Origin 放行
        r2 = client.post(
            "/v1/membership/portal",
            headers={**_auth(token), "Origin": "http://localhost"},
            json={},
        )
        assert r2.status_code == 404

    def test_full_flow_returns_stripe_url(self, client, monkeypatch):
        """有留痕的用户走完整链路，拿到 Stripe 管理页 URL。"""
        token = _register(client, "portal-g@test.local")
        db = client.application._db
        with db.get_conn() as conn:
            uid = conn.execute(
                "SELECT id FROM users WHERE email = ?", ("portal-g@test.local",)
            ).fetchone()[0]
        _seed_paid(db, uid, "LOOMA0099", "cus_9", "sub_9")

        client.application.config["STRIPE_SECRET_KEY"] = "sk_test_dummy"
        monkeypatch.setattr(
            stripe_mod.requests, "post",
            lambda *a, **k: _Resp({"url": "https://billing.stripe.com/p/session/e2e"}),
        )

        r = client.post(
            "/v1/membership/portal",
            headers=_auth(token),
            json={"return_url": "http://localhost/account"},
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["url"] == "https://billing.stripe.com/p/session/e2e"
