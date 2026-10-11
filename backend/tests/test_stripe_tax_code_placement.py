"""Stripe Checkout 的税码必须挂在内联 Product 上。

2026-10-12 现网订阅结账 502：请求把税码放在
``line_items[0][price_data][tax_code]``，Stripe 回 parameter_unknown。
合法位置是 ``price_data.product_data.tax_code``。一次性付款同样不能放在
line item 顶层。已有 Price ID 的订阅不带 price_data。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.payment.providers.stripe import StripeProvider  # noqa: E402


def _capture(monkeypatch):
    seen = {}

    def fake_api(method, path, secret_key, data=None, params=None):
        seen["data"] = dict(data or {})
        return {"id": "cs_test", "url": "https://checkout.stripe.com/c/pay/cs_test"}

    monkeypatch.setattr(StripeProvider, "_api_request", staticmethod(fake_api))
    return seen


def test_subscription_tax_code_sits_on_product_data(monkeypatch):
    seen = _capture(monkeypatch)
    StripeProvider().create_checkout(
        config={"STRIPE_SECRET_KEY": "sk_test_x", "STRIPE_TAX_CODE": "txcd_10103000"},
        out_trade_no="M1",
        tier="supporter",
        amount=1.99,
        mode="subscription",
    )
    data = seen["data"]
    assert data["line_items[0][price_data][product_data][tax_code]"] == "txcd_10103000"
    assert "line_items[0][price_data][tax_code]" not in data
    assert "line_items[0][tax_code]" not in data
    assert data["automatic_tax[enabled]"] == "true"


def test_payment_tax_code_sits_on_product_data(monkeypatch):
    seen = _capture(monkeypatch)
    StripeProvider().create_checkout(
        config={"STRIPE_SECRET_KEY": "sk_test_x"},
        out_trade_no="P1",
        tier="supporter",
        amount=1.99,
        mode="payment",
    )
    data = seen["data"]
    assert data["line_items[0][price_data][product_data][tax_code]"] == "txcd_10103000"
    assert "line_items[0][tax_code]" not in data


def test_subscription_price_id_does_not_send_inline_tax_code(monkeypatch):
    seen = _capture(monkeypatch)
    StripeProvider().create_checkout(
        config={"STRIPE_SECRET_KEY": "sk_test_x", "STRIPE_TAX_CODE": "txcd_10103000"},
        out_trade_no="M2",
        tier="pro",
        amount=5.99,
        mode="subscription",
        metadata={"stripe_price_id": "price_123"},
    )
    data = seen["data"]
    assert data["line_items[0][price]"] == "price_123"
    assert "line_items[0][price_data][product_data][tax_code]" not in data
    assert data["automatic_tax[enabled]"] == "true"
