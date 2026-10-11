"""
Stripe payment provider — implements BaseProvider interface.

Uses Stripe Checkout Sessions API.
Required env vars: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
Optional: STRIPE_CURRENCY (default: USD)

Refactored from src/payment/stripe_pay.py into the Provider pattern.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any

import requests

from src.payment.providers.base import BaseProvider, CheckoutResult, WebhookResult

STRIPE_API_BASE = "https://api.stripe.com/v1"


class StripeProvider(BaseProvider):
    provider_name = "stripe"

    # ── Configuration ──────────────────────────────────────

    def is_configured(self, config: dict[str, Any]) -> bool:
        return bool(
            config.get("STRIPE_SECRET_KEY", "")
        )

    # ── Checkout ───────────────────────────────────────────

    def create_checkout(
        self,
        config: dict[str, Any],
        out_trade_no: str,
        tier: str,
        amount: float,
        currency: str = "USD",
        plan_name: str = "Looma Plan",
        customer_email: str = "",
        success_url: str = "",
        cancel_url: str = "",
        mode: str = "payment",
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutResult:
        secret_key = config.get("STRIPE_SECRET_KEY", "")
        amount_cents = int(round(amount * 100))

        data: dict[str, str] = {
            "mode": mode,
            "client_reference_id": out_trade_no,
            "metadata[out_trade_no]": out_trade_no,
            "metadata[tier]": tier,
        }

        if success_url:
            data["success_url"] = success_url
        if cancel_url:
            data["cancel_url"] = cancel_url
        if customer_email:
            data["customer_email"] = customer_email

        # Attach extra metadata
        if metadata:
            for k, v in metadata.items():
                data[f"metadata[{k}]"] = str(v)

        if mode == "payment":
            data["line_items[0][quantity]"] = "1"
            data["line_items[0][price_data][currency]"] = currency.lower()
            data["line_items[0][price_data][unit_amount]"] = str(amount_cents)
            data["line_items[0][price_data][product_data][name]"] = plan_name
        elif mode == "subscription":
            # Use a configured Price ID if available
            price_id = metadata.get("stripe_price_id", "") if metadata else ""
            if price_id:
                data["line_items[0][quantity]"] = "1"
                data["line_items[0][price]"] = price_id
            else:
                # Fallback: create price_data for subscription mode
                data["line_items[0][quantity]"] = "1"
                data["line_items[0][price_data][currency]"] = currency.lower()
                data["line_items[0][price_data][unit_amount]"] = str(amount_cents)
                data["line_items[0][price_data][recurring][interval]"] = "month"
                data["line_items[0][price_data][product_data][name]"] = plan_name

            # Session metadata does NOT propagate to the Subscription object.
            # Set it on subscription_data so later renewals (invoice.paid) and
            # cancellations (customer.subscription.deleted) can be traced back
            # to our internal order / user.
            for k, v in (metadata or {}).items():
                if k == "stripe_price_id" or v is None:
                    continue
                data[f"subscription_data[metadata][{k}]"] = str(v)
            data["subscription_data[metadata][out_trade_no]"] = out_trade_no
            data["subscription_data[metadata][tier]"] = tier

        # ── Stripe Tax（香港主体 YEDALL LIMITED — Stripe Tax 自动算税并代缴）──
        # 对所有 Stripe 结账（含原 payment 链路）自动生效；不传开关则默认开启。
        # 税码属于内联 Product，不在 Price 或 line item 上。已有 Price ID 的
        # 订阅沿用该 Price 上的 Product，不再塞 price_data。
        tax_enabled = str(config.get("STRIPE_TAX_ENABLED", "true")).lower() in ("1", "true", "yes", "on")
        if tax_enabled:
            data["automatic_tax[enabled]"] = "true"
            data["tax_id_collection[enabled]"] = "true"
            if "line_items[0][price_data][currency]" in data:
                tax_code = config.get("STRIPE_TAX_CODE", "txcd_30040001")
                data["line_items[0][price_data][product_data][tax_code]"] = tax_code

        result = self._api_request("POST", "/checkout/sessions", secret_key, data)

        return CheckoutResult(
            provider="stripe",
            checkout_url=result.get("url", ""),
            out_trade_no=out_trade_no,
            provider_checkout_id=result.get("id", ""),
            amount=amount,
            currency=currency.upper(),
            raw={
                "stripe_session_id": result.get("id", ""),
                "payment_intent": result.get("payment_intent", ""),
            },
        )

    # ── Billing Portal ─────────────────────────────────────

    def create_billing_portal_session(
        self,
        config: dict[str, Any],
        customer_id: str,
        return_url: str = "",
    ) -> dict[str, Any]:
        """创建 Stripe Billing Portal 会话，返回 ``{"url", "id"}``。

        取消订阅 / 换卡 / 下载发票都在 Stripe 托管页面完成 —— 比自己为每个
        地区再造一套取消 UI 更省事，也更容易满足「取消要和订阅一样容易」的
        监管预期（EU 消费者权利指令 / FTC negative-option 规则）。

        注意：Portal 里具体开放哪些操作（能否取消、能否换套餐）由 Stripe
        Dashboard 的 Portal 配置决定，代码侧只负责开一个会话。
        """
        secret_key = config.get("STRIPE_SECRET_KEY", "")
        data: dict[str, str] = {"customer": customer_id}
        if return_url:
            data["return_url"] = return_url

        result = self._api_request("POST", "/billing_portal/sessions", secret_key, data)
        return {"url": result.get("url", ""), "id": result.get("id", "")}

    # ── Webhook ────────────────────────────────────────────

    def verify_webhook(
        self,
        config: dict[str, Any],
        payload: bytes,
        headers: dict[str, str],
    ) -> bool:
        webhook_secret = config.get("STRIPE_WEBHOOK_SECRET", "")
        sig_header = headers.get("Stripe-Signature", "")

        if not webhook_secret:
            return True  # dev mode: skip verification

        try:
            elements = dict(e.split("=", 1) for e in sig_header.split(","))
            timestamp = int(elements.get("t", "0"))
            v1_signature = elements.get("v1", "")
        except (ValueError, KeyError):
            raise ValueError("Invalid Stripe webhook header format")

        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            raise ValueError("Stripe webhook timestamp outside tolerance")

        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, v1_signature):
            raise ValueError("Stripe webhook signature verification failed")

        return True

    def parse_webhook(self, payload: bytes) -> WebhookResult:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return WebhookResult(success=False, provider="stripe", error="Invalid JSON")

        event_type = event.get("type", "")
        obj = event.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            return WebhookResult(
                success=True,
                provider="stripe",
                event_type="checkout.completed",
                out_trade_no=obj.get("client_reference_id", "") or "",
                transaction_id=obj.get("payment_intent", "") or "",
                customer_id=obj.get("customer", "") or "",
                subscription_id=obj.get("subscription", "") or "",
                amount_total=obj.get("amount_total", 0),
                currency=(obj.get("currency", "usd")).upper(),
                tier=(obj.get("metadata", {}) or {}).get("tier", ""),
                raw=event,
            )

        elif event_type == "invoice.paid":
            metadata = obj.get("metadata", {}) or {}
            return WebhookResult(
                success=True,
                provider="stripe",
                event_type="subscription.renewed",
                out_trade_no=metadata.get("out_trade_no", ""),
                transaction_id=obj.get("payment_intent", "") or "",
                customer_id=obj.get("customer", "") or "",
                subscription_id=obj.get("subscription", "") or "",
                amount_total=obj.get("amount_paid", 0),
                currency=(obj.get("currency", "usd")).upper(),
                raw=event,
            )

        elif event_type == "customer.subscription.deleted":
            return WebhookResult(
                success=True,
                provider="stripe",
                event_type="subscription.cancelled",
                customer_id=obj.get("customer", "") or "",
                subscription_id=obj.get("id", "") or "",
                raw=event,
            )

        return WebhookResult(
            success=True,
            provider="stripe",
            event_type=event_type,
            raw=event,
        )

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _api_request(method: str, path: str, secret_key: str,
                     data: dict = None, params: dict = None) -> dict:
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        url = f"{STRIPE_API_BASE}{path}"

        if method == "POST":
            resp = requests.post(url, data=data or {}, headers=headers, timeout=15)
        else:
            resp = requests.get(url, params=params or {}, headers=headers, timeout=15)

        if resp.status_code >= 400:
            raise ValueError(f"Stripe API error {resp.status_code}: {resp.text}")

        return resp.json()
