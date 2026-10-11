"""支付漏斗埋点测试 —— 「有购买意向」这一段必须可观测。

Run: pytest tests/test_payment_funnel.py -v

背景（2026-10-11）：后端 `VALID_EVENTS` 白名单里此前**没有任何支付事件**，
`get_funnel_stats` 的漏斗步骤也只到 `trial_started`。后果是双重的：

  * 前端即使埋了点订阅，服务端也会 400 拒收（unknown event_name）
  * 即使收了也进不了漏斗聚合 —— 转化率根本算不出来

实质影响：`GET /v1/analytics/funnel` 看不到任何「有人想付钱」的迹象，
而真实订单表里也只有结果、没有过程。等于**付费漏斗是断的**。

本文件锁死三件事：

1. 白名单必须接受支付漏斗事件（前后端事件名必须一致，否则静默 400）。
2. 结算成功必须由**服务端**写入 `payment_succeeded` —— 前端上报的付款成功
   可以伪造，不能作为漏斗终点的依据。
3. `get_funnel_stats` 必须把支付漏斗纳入 `steps` + `conversion`，
   且零流量时返回 None 而不是 0 或除零。
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.manager import DatabaseManager  # noqa: E402
from src.services.membership.service import MembershipService  # noqa: E402


CONFIG = {"STRIPE_WEBHOOK_SECRET": ""}


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    manager = DatabaseManager(path)
    manager.init_schema()
    yield manager
    os.unlink(path)


def _register(client, email="funnel-api@test.local"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test-pass-123", "name": "Funnel"},
    )
    assert resp.status_code == 201
    return resp.get_json()["access_token"]


def _checkout_completed(out_trade_no, sub="sub_funnel_1"):
    return json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": out_trade_no,
            "payment_intent": "pi_funnel_1",
            "customer": "cus_funnel_1",
            "subscription": sub,
            "amount_total": 199,
            "currency": "usd",
            "metadata": {"tier": "supporter"},
        }},
    }).encode()


# ── 1. 白名单接受支付漏斗事件 ──

def test_whitelist_accepts_payment_funnel_events(client):
    token = _register(client, "funnel-whitelist@test.local")
    resp = client.post(
        "/v1/analytics/events",
        json={"events": [
            {"event_name": "pricing_viewed", "session_id": "s1", "platform": "tspace_web"},
            {"event_name": "subscribe_clicked", "session_id": "s1", "platform": "tspace_web"},
            {"event_name": "checkout_redirected", "session_id": "s1", "platform": "tspace_web"},
            {"event_name": "checkout_failed", "session_id": "s1", "platform": "tspace_web"},
        ]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["ingested"] == 4


# ── 2. 服务端在结算成功时写 payment_succeeded ──

def test_settlement_records_payment_succeeded(db):
    uid = db.create_user(email="funnel-buyer@example.com")
    db.create_order(
        user_id=uid, plan_id="supporter_us", tier="supporter",
        amount=1.99, currency="USD", out_trade_no="LOOMAFUNNEL01",
    )

    MembershipService().handle_stripe_webhook(
        db, CONFIG, _checkout_completed("LOOMAFUNNEL01"), {},
    )

    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM product_events WHERE event_name = 'payment_succeeded'",
        ).fetchall()

    assert len(rows) == 1, "结算成功必须留下一条服务端埋点"
    ev = dict(rows[0])
    assert ev["source"] == "server", "必须标记来源为服务端，与客户端上报区分"
    assert ev["user_id"] == uid
    assert json.loads(ev["properties_json"])["tier"] == "supporter"


def test_idempotent_replay_does_not_double_record(db):
    """Stripe 重投同一 session.completed 时不得重复埋点。"""
    uid = db.create_user(email="funnel-replay@example.com")
    db.create_order(
        user_id=uid, plan_id="supporter_us", tier="supporter",
        amount=1.99, currency="USD", out_trade_no="LOOMAFUNNEL02",
    )
    svc = MembershipService()
    payload = _checkout_completed("LOOMAFUNNEL02")

    svc.handle_stripe_webhook(db, CONFIG, payload, {})
    svc.handle_stripe_webhook(db, CONFIG, payload, {})

    with db.get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM product_events WHERE event_name = 'payment_succeeded'",
        ).fetchone()["c"]
    assert count == 1


# ── 3. 漏斗聚合纳入支付步骤 ──

def test_funnel_stats_include_payment_steps(db):
    uid = db.create_user(email="funnel-steps@example.com")
    for name in ("pricing_viewed", "pricing_viewed", "subscribe_clicked", "checkout_redirected"):
        db.log_product_event(
            event_name=name, user_id=uid, platform="tspace_web", source="client",
        )

    stats = db.get_funnel_stats(days=30)

    assert stats["steps"]["pricing_viewed"] == 2
    assert stats["steps"]["subscribe_clicked"] == 1
    assert stats["steps"]["checkout_redirected"] == 1
    assert stats["steps"]["payment_succeeded"] == 0
    # 点击率 1/2；进收银台率 1/1；付费率 0/1（真实付费为 0 时的读数）
    assert stats["conversion"]["click_after_view"] == 0.5
    assert stats["conversion"]["checkout_after_click"] == 1.0
    assert stats["conversion"]["paid_after_checkout"] == 0.0


def test_funnel_conversion_is_none_without_traffic(db):
    stats = db.get_funnel_stats(days=30)
    assert stats["conversion"]["click_after_view"] is None, (
        "零流量时不应给出 0 或除零结果 —— 那会把「没人来」误读成「来了不付」"
    )
