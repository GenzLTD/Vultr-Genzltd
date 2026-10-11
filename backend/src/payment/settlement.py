"""统一支付结算路径 —— 供 payment 与 membership 两套路由共用。

职责：查单 → 幂等校验 → mark_order_paid → update_user_tier →
upsert_subscription(+30天)。抽此函数避免两处结算逻辑漂移：
payment webhook 与 membership webhook 必须走同一核销路径。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def settle_payment(
    db: Any,
    out_trade_no: str,
    transaction_id: str,
    provider_name: str,
) -> dict | None:
    """Settle a completed payment: mark paid + upgrade tier + create subscription.

    Shared by Stripe / WeChat / PayPal webhooks and the membership webhook.
    Returns the paid order dict, or None on idempotent skip / not-found.
    """
    order = db.get_order_by_out_trade_no(out_trade_no)
    if not order:
        logger.error("[%s] Order not found: %s", provider_name, out_trade_no)
        return None

    if order["status"] == "paid":
        return None  # 幂等跳过

    paid_order = db.mark_order_paid(out_trade_no, transaction_id)
    if not paid_order:
        return None

    user_id = paid_order["user_id"]
    tier = paid_order["tier"]
    plan_id = paid_order["plan_id"]

    db.update_user_tier(user_id, tier)

    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.upsert_subscription(user_id, tier, plan_id, expires, auto_renew=False)

    logger.info(
        "[%s] Payment confirmed: user=%s tier=%s order=%s txn=%s",
        provider_name, user_id, tier, out_trade_no, transaction_id,
    )
    _record_payment_event(db, user_id, tier, out_trade_no, paid_order)
    return paid_order


def _record_payment_event(
    db: Any,
    user_id: str,
    tier: str,
    out_trade_no: str,
    order: dict,
) -> None:
    """服务端记一笔 payment_succeeded。

    漏斗终点必须由服务端产生 —— 前端上报的「付款成功」不可信（可伪造），
    而这里是唯一「钱确实到账」的地方。
    """
    log_event = getattr(db, "log_product_event", None)
    if log_event is None:
        return
    try:
        log_event(
            event_name="payment_succeeded",
            user_id=user_id,
            platform="tspace_web",
            source="server",
            success=True,
            properties={
                "tier": tier,
                "out_trade_no": out_trade_no,
                "amount": order.get("amount"),
                "currency": order.get("currency"),
            },
        )
    except Exception:  # 埋点失败绝不能影响结算结果
        logger.warning(
            "[settlement] failed to record payment_succeeded: order=%s",
            out_trade_no, exc_info=True,
        )
