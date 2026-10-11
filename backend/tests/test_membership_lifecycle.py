"""海外会员订阅生命周期测试 —— 续费 / 取消 / provider 引用留痕。

Run: pytest tests/test_membership_lifecycle.py -v

背景（2026-10-11）：`MembershipService.handle_stripe_webhook` 中
`subscription.renewed` 与 `subscription.cancelled` 两个分支长期是 `TODO: pass`，
等于：

  * 用户续费 → 钱收了，但 `expires_at` 不动（付费时长不延长）
  * 用户取消 → 订阅结束，但 `tier` 仍是 pro（不降级，白嫖）

本文件锁死四件事：

1. 首次结算必须把 Stripe `subscription` / `customer` id 落到订单 metadata 上。
   取消事件（`customer.subscription.deleted`）只带这两个 id，不带我们的
   out_trade_no —— 不留痕就永远定位不到用户。
2. 续费必须从 `max(now, 当前到期)` 顺延 30 天；提前续费不得吞掉已购时长。
3. 取消必须把 tier 降回 free、订阅置 expired。
4. 定位不到的再投递必须回 200（否则 Stripe 会无限重试）。

已知限制（本 PR 不处理，见 PR 描述）：未做 webhook 事件级去重，
若 Stripe 重投同一 `invoice.paid` 会重复顺延。当前所有分支均回 200，
正常路径下 Stripe 不会重投。
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.manager import DatabaseManager  # noqa: E402
from src.payment.providers.stripe import StripeProvider  # noqa: E402
from src.services.membership.service import MembershipService  # noqa: E402


# 空密钥 = dev 模式跳过验签（与 StripeProvider.verify_webhook 一致）
CONFIG = {"STRIPE_WEBHOOK_SECRET": ""}


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    manager = DatabaseManager(path)
    manager.init_schema()
    yield manager
    os.unlink(path)


def _checkout_completed(out_trade_no, customer="cus_test_1", sub="sub_test_1"):
    return json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": out_trade_no,
            "payment_intent": "pi_test_1",
            "customer": customer,
            "subscription": sub,
            "amount_total": 199,
            "currency": "usd",
            "metadata": {"tier": "supporter"},
        }},
    }).encode()


def _invoice_paid(out_trade_no, customer="cus_test_1", sub="sub_test_1",
                  invoice_id="in_test_1"):
    return json.dumps({
        "type": "invoice.paid",
        "data": {"object": {
            "id": invoice_id,
            "payment_intent": "pi_test_2",
            "customer": customer,
            "subscription": sub,
            "amount_paid": 199,
            "currency": "usd",
            "metadata": {"out_trade_no": out_trade_no},
        }},
    }).encode()


def _subscription_deleted(sub="sub_test_1", customer="cus_test_1"):
    return json.dumps({
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": sub, "customer": customer}},
    }).encode()


def _seed_order(db, uid, out_trade_no):
    return db.create_order(
        user_id=uid, plan_id="supporter_us", tier="supporter",
        amount=1.99, currency="USD", out_trade_no=out_trade_no,
    )


# ── 1. 首单结算 + provider 引用留痕 ──

def test_checkout_completed_settles_and_records_provider_refs(db):
    uid = db.create_user(email="buyer@example.com")
    _seed_order(db, uid, "LOOMATEST0001")
    svc = MembershipService()

    body, code = svc.handle_stripe_webhook(
        db, CONFIG, _checkout_completed("LOOMATEST0001"), {},
    )

    assert code == 200
    paid = db.get_order_by_out_trade_no("LOOMATEST0001")
    assert paid["status"] == "paid"

    meta = json.loads(paid["metadata_json"])
    assert meta["stripe_subscription_id"] == "sub_test_1"
    assert meta["stripe_customer_id"] == "cus_test_1"

    assert db.get_user_by_id(uid)["tier"] == "supporter"
    sub = db.get_subscription(uid)
    assert sub["status"] == "active"
    assert sub["auto_renew"] == 1, "带 subscription_id 的付款应标记为自动续费"

    # 反查链路可用 —— 这是取消事件唯一的定位方式
    assert db.find_order_by_stripe_subscription("sub_test_1")["id"] == paid["id"]
    assert db.find_order_by_stripe_customer("cus_test_1")["id"] == paid["id"]


def test_parse_webhook_extracts_subscription_id():
    r = StripeProvider().parse_webhook(_checkout_completed("X"))
    assert r.event_type == "checkout.completed"
    assert r.subscription_id == "sub_test_1"
    assert r.customer_id == "cus_test_1"
    assert r.out_trade_no == "X"


# ── 2. 续费顺延（不吞已购时长）──

def test_renewal_extends_from_current_expiry(db):
    uid = db.create_user(email="renew@example.com")
    _seed_order(db, uid, "LOOMATEST0002")
    svc = MembershipService()

    svc.handle_stripe_webhook(db, CONFIG, _checkout_completed("LOOMATEST0002"), {})

    # 模拟「周期尚未结束就续费」：把到期时间推到 10 天后
    future = (datetime.now() + timedelta(days=10)).isoformat()
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE subscriptions SET expires_at = ? WHERE user_id = ?", (future, uid),
        )

    body, code = svc.handle_stripe_webhook(
        db, CONFIG, _invoice_paid("LOOMATEST0002"), {},
    )

    assert code == 200
    new_exp = db.get_subscription(uid)["expires_at"]
    delta = datetime.fromisoformat(new_exp) - datetime.fromisoformat(future)
    assert abs(delta.days - 30) <= 1, (
        "续费应从当前到期时间顺延 30 天，而不是从 now 重算"
    )
    assert db.get_user_by_id(uid)["tier"] == "supporter"


def test_renewal_resolves_user_without_out_trade_no(db):
    """invoice.paid 丢失 out_trade_no 时，应能用 subscription id 反查。"""
    uid = db.create_user(email="fallback@example.com")
    _seed_order(db, uid, "LOOMATEST0003")
    svc = MembershipService()

    svc.handle_stripe_webhook(db, CONFIG, _checkout_completed("LOOMATEST0003"), {})

    # 续费事件的 metadata 为空 —— 只能靠 sub_test_1 反查
    body, code = svc.handle_stripe_webhook(
        db, CONFIG, _invoice_paid("", invoice_id="in_test_9"), {},
    )

    assert code == 200
    assert body.get("resolved") is not False
    assert db.get_subscription(uid)["auto_renew"] == 1


# ── 3. 取消降级 ──

def test_cancellation_downgrades_to_free(db):
    uid = db.create_user(email="cancel@example.com")
    _seed_order(db, uid, "LOOMATEST0004")
    svc = MembershipService()

    svc.handle_stripe_webhook(db, CONFIG, _checkout_completed("LOOMATEST0004"), {})
    assert db.get_user_by_id(uid)["tier"] == "supporter"

    body, code = svc.handle_stripe_webhook(
        db, CONFIG, _subscription_deleted(), {},
    )

    assert code == 200
    assert db.get_user_by_id(uid)["tier"] == "free"
    assert db.get_subscription(uid)["status"] == "expired"


# ── 4. 无法定位的再投递 ──

def test_unresolvable_cancellation_returns_ok(db):
    svc = MembershipService()
    body, code = svc.handle_stripe_webhook(
        db, CONFIG, _subscription_deleted("sub_ghost", "cus_ghost"), {},
    )
    assert code == 200, "定位不到的再投递必须回 200，否则 Stripe 会无限重试"
    assert body["resolved"] is False
