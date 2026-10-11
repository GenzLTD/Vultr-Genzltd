"""海外会员产品层 —— 复用 payment 引擎，不重复报价。

定价/区域价目来自 contracts/payment.v1.json（US 区），
本模块只负责：权益组装、Stripe Tax 税务配置注入、订单/订阅结算编排。
"""
from __future__ import annotations

from typing import Any

from src.payment.plans import get_plan_for_tier, list_plans_for_region
from src.payment.providers import get_provider
from src.payment.settlement import settle_payment
from src.payment.stripe_pay import generate_out_trade_no
from src.services.membership import contract as membership_contract

MEMBERSHIP_TIERS = ("supporter", "pro")
BILLING_REGION = "US"
BILLING_ENTITY = "YEDALL LIMITED"
PROVIDER_NAME = "stripe"


class MembershipService:
    """海外会员产品服务：套餐罗列、订阅下单、状态查询、Stripe webhook 结算。"""

    def list_plans(self, config: dict[str, Any]) -> dict[str, Any]:
        """返回三档套餐 + 税务说明 + 账单主体（价格取自 payment.v1.json US）。"""
        region_payload = list_plans_for_region(BILLING_REGION)
        entitlements = membership_contract.get_entitlements()
        tax = membership_contract.get_tax_config()
        plans: list[dict[str, Any]] = []
        for plan in region_payload["plans"]:
            tier = plan["tier"]
            ent = entitlements.get(tier, {})
            plans.append(
                {
                    **plan,
                    "billing_entity": BILLING_ENTITY,
                    "entitlements": ent.get("features", []),
                    "quota": ent.get("quota", {}),
                }
            )
        return {
            "region": BILLING_REGION,
            "currency": region_payload["currency"],
            "billing_entity": BILLING_ENTITY,
            "tax": tax,
            "payment_provider": PROVIDER_NAME,
            "payment_methods": ["card", "apple_pay", "google_pay"],
            "plans": plans,
        }

    def subscribe(
        self,
        db: Any,
        config: dict[str, Any],
        user_id: str,
        tier: str | None,
        success_url: str,
        cancel_url: str,
        origin: str,
    ) -> tuple[dict[str, Any], int]:
        """创建会员订阅 Checkout Session（Stripe 订阅模式 + Stripe Tax）。

        Returns (body, status_code).
        """
        if tier not in MEMBERSHIP_TIERS:
            return (
                {"error": "invalid_tier", "message": "Choose: supporter, pro"},
                400,
            )

        # Stub 模式下不开真实收银台（与 /v1/payment/checkout 一致）
        if config.get("PAYMENT_STUB_MODE", True):
            return (
                {
                    "error": "stub_mode",
                    "message": "Payment stub mode is enabled. Set PAYMENT_STUB_MODE=false to enable real membership checkout.",
                },
                400,
            )

        try:
            plan = get_plan_for_tier(tier, BILLING_REGION)
        except KeyError:
            return (
                {
                    "error": "bad_request",
                    "message": f"No {BILLING_REGION} price configured for tier: {tier}",
                },
                400,
            )

        amount = plan["price_monthly"]
        currency = plan["currency"]

        provider = get_provider(PROVIDER_NAME)
        if not provider.is_configured(config):
            return (
                {
                    "error": "payment_not_configured",
                    "message": "Stripe not configured. Set STRIPE_SECRET_KEY env var.",
                },
                503,
            )

        out_trade_no = generate_out_trade_no()
        user = db.get_user_by_id(user_id)
        customer_email = user.get("email", "") if user else ""

        if not success_url:
            success_url = f"{origin}/subscribe?status=success"
        if not cancel_url:
            cancel_url = f"{origin}/subscribe?status=cancel"

        try:
            result = provider.create_checkout(
                config=config,
                out_trade_no=out_trade_no,
                tier=tier,
                amount=amount,
                currency=currency,
                plan_name=f"Looma {plan['name']}",
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                mode="subscription",
                metadata={
                    "product": "overseas-membership",
                    "region": BILLING_REGION,
                },
            )
        except ValueError as e:
            return (
                {"error": "stripe_error", "message": str(e)},
                502,
            )

        order = db.create_order(
            user_id=user_id,
            plan_id=plan["plan_id"],
            tier=tier,
            amount=amount,
            currency=currency,
            out_trade_no=out_trade_no,
            metadata_json={
                "product": "overseas-membership",
                "provider": PROVIDER_NAME,
                "mode": "subscription",
                "region": BILLING_REGION,
            },
        )

        return (
            {
                "order_id": order["id"],
                "out_trade_no": out_trade_no,
                "provider": PROVIDER_NAME,
                "checkout_url": result.checkout_url,
                "amount": amount,
                "currency": currency,
                "tier": tier,
            },
            201,
        )

    def get_status(self, db: Any, user_id: str) -> dict[str, Any]:
        """查询当前用户的会员订阅状态。"""
        sub = db.get_subscription(user_id)
        user = db.get_user_by_id(user_id)
        tier = (user or {}).get("tier", "free") if user else "free"
        status = sub["status"] if sub else ("active" if tier != "free" else "inactive")
        return {
            "tier": tier,
            "status": status,
            "expires_at": sub["expires_at"] if sub else None,
            "auto_renew": bool(sub["auto_renew"]) if sub else False,
            "billing_entity": BILLING_ENTITY,
        }

    def handle_stripe_webhook(
        self,
        db: Any,
        config: dict[str, Any],
        payload: bytes,
        headers: dict[str, str],
    ) -> tuple[dict[str, Any], int]:
        """处理 Stripe 会员订阅 webhook（验签 + 解析 + 结算）。"""
        provider = get_provider(PROVIDER_NAME)
        try:
            provider.verify_webhook(config, payload, headers)
        except ValueError as e:
            return (
                {"error": "invalid_signature", "message": str(e)},
                400,
            )

        result = provider.parse_webhook(payload)
        if not result.success:
            return ({"error": "parse_error", "message": result.error}, 400)

        if result.event_type == "checkout.completed":
            if not result.out_trade_no:
                return ({"status": "ok"}, 200)
            settle_payment(db, result.out_trade_no, result.transaction_id, "stripe-membership")
        elif result.event_type == "subscription.renewed":
            # TODO: 续期延展订阅有效期 +30 天（依赖 Stripe invoice 携带 out_trade_no）
            pass
        elif result.event_type == "subscription.cancelled":
            # TODO: 按 Stripe customer_id 定位用户并降级 free
            pass

        return ({"status": "ok"}, 200)
