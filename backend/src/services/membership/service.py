"""海外会员产品层 —— 复用 payment 引擎，不重复报价。

定价/区域价目来自 contracts/payment.v1.json（US 区），
本模块只负责：权益组装、Stripe Tax 税务配置注入、订单/订阅结算编排。
"""
from __future__ import annotations

import logging
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

logger = logging.getLogger("looma.membership")


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

    def create_billing_portal(
        self,
        db: Any,
        config: dict[str, Any],
        user_id: str,
        return_url: str = "",
    ) -> tuple[dict[str, Any], int]:
        """创建 Stripe Billing Portal 会话 —— 用户自助取消 / 换卡 / 取发票。

        为什么给一个托管页 URL 而不是自己做取消按钮：自助管理页是「取消要和
        订阅一样容易」的最省事落法（EU 消费者权利指令 / FTC negative-option），
        且不必为每个地区各写一套 UI。

        本方法**只开会话、不改库**：真正的订阅状态变化仍由 webhook 驱动
        （见 handle_stripe_webhook），避免两处各自推理订阅状态而互相打架。
        """
        refs = db.find_stripe_refs_for_user(user_id) or {}
        customer_id = refs.get("stripe_customer_id") or ""
        if not customer_id:
            return (
                {
                    "error": "no_billing_customer",
                    "message": "当前账号没有可管理的订阅记录（尚未完成过 Stripe 结账）。",
                },
                404,
            )

        provider = get_provider(PROVIDER_NAME)
        if not provider.is_configured(config):
            return (
                {
                    "error": "payment_not_configured",
                    "message": "Stripe not configured. Set STRIPE_SECRET_KEY env var.",
                },
                503,
            )

        try:
            session = provider.create_billing_portal_session(
                config=config, customer_id=customer_id, return_url=return_url,
            )
        except Exception as e:  # noqa: BLE001 — 上游失败如实回报，不能假装成功
            logger.warning(
                "[membership] billing portal failed: user=%s err=%s", user_id, e
            )
            return (
                {"error": "portal_unavailable", "message": "订阅管理页暂时不可用，请稍后重试。"},
                502,
            )

        if not session.get("url"):
            logger.warning("[membership] billing portal returned no url: user=%s", user_id)
            return (
                {"error": "portal_unavailable", "message": "订阅管理页暂时不可用，请稍后重试。"},
                502,
            )
        return ({"url": session["url"], "provider": PROVIDER_NAME}, 200)

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
            settle_payment(
                db,
                result.out_trade_no,
                result.transaction_id,
                "stripe-membership",
                customer_id=result.customer_id,
                subscription_id=result.subscription_id,
            )
        elif result.event_type == "subscription.renewed":
            return self._handle_renewal(db, result)
        elif result.event_type == "subscription.cancelled":
            return self._handle_cancellation(db, result)

        return ({"status": "ok"}, 200)

    # ── 订阅生命周期（续费 / 取消）──────────────────────────

    @staticmethod
    def _resolve_user_id(db: Any, result: Any) -> str | None:
        """为一个生命周期事件定位归属用户。

        续费事件带 out_trade_no（已随订阅元数据下发）；取消事件只带
        provider 侧 id，故回退到结算时留在订单上的 stripe_* 引用。
        """
        if result.out_trade_no:
            order = db.get_order_by_out_trade_no(result.out_trade_no)
            if order:
                return order.get("user_id")
        for attr, key in (
            ("find_order_by_stripe_subscription", result.subscription_id),
            ("find_order_by_stripe_customer", result.customer_id),
        ):
            if not key:
                continue
            finder = getattr(db, attr, None)
            if finder is None:
                continue
            order = finder(key)
            if order:
                return order.get("user_id")
        return None

    def _handle_renewal(self, db: Any, result: Any) -> tuple[dict[str, Any], int]:
        """subscription.renewed：顺延已购时长。

        刻意不走 settle_payment()——原始订单已是 paid，
        那里的幂等守卫（status == 'paid' → return None）会把续费整个吞掉。
        """
        user_id = self._resolve_user_id(db, result)
        if not user_id:
            logger.warning(
                "[membership] renewal unresolvable: sub=%s customer=%s out_trade_no=%s",
                result.subscription_id or "-",
                result.customer_id or "-",
                result.out_trade_no or "-",
            )
            # 回 200，避免 Stripe 对无法处理的再投递无限重试。
            return ({"status": "ok", "resolved": False}, 200)

        sub = db.renew_subscription(user_id, days=30)
        logger.info(
            "[membership] renewal applied: user=%s expires_at=%s",
            user_id, (sub or {}).get("expires_at"),
        )
        return ({"status": "ok", "expires_at": (sub or {}).get("expires_at")}, 200)

    def _handle_cancellation(self, db: Any, result: Any) -> tuple[dict[str, Any], int]:
        """subscription.cancelled：订阅结束，标记过期并降级 free。"""
        user_id = self._resolve_user_id(db, result)
        if not user_id:
            logger.warning(
                "[membership] cancellation unresolvable: sub=%s customer=%s",
                result.subscription_id or "-", result.customer_id or "-",
            )
            return ({"status": "ok", "resolved": False}, 200)

        db.expire_subscription(user_id)
        logger.info("[membership] subscription cancelled: user=%s", user_id)
        return ({"status": "ok"}, 200)
