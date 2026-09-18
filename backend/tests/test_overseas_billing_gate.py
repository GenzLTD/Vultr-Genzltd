"""Overseas billing product tests (WeChat region gate + Stripe stub/checkout).

This directory is the overseas runtime. It may diverge from looma-zervi
(Stripe vs WeChat, identity, Host). The unique protocol source is
contracts/gfcc — not this file, not looma-zervi's workflows.

Pipeline assertions live in tests/deploy-contract/ so a tree copy of
backend/ cannot wipe THIS stack's deploy.yml invariants. Do not add
deploy.yml / bootstrap-env / deploy-overseas.yml assertions here.
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager

from src.app import create_app


def _register(client, email, password="secret123"):
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "name": "GateTest"},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def _client(stub_mode: str):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    os.environ["JWT_SECRET"] = "test-secret-32bytes-long-enough!!"
    os.environ["PAYMENT_STUB_MODE"] = stub_mode
    os.environ["JWT_EXPIRY_HOURS"] = "168"
    try:
        app = create_app("testing")
        yield app.test_client()
    finally:
        os.environ["PAYMENT_STUB_MODE"] = "true"
        if os.path.exists(path):
            os.unlink(path)


class TestWechatRegionGate:
    def test_unauthenticated_is_401_before_stub_or_region(self):
        with _client("false") as c:
            resp = c.post(
                "/v1/payment/wechat/order?region=US",
                json={"tier": "supporter", "trade_type": "NATIVE"},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"] == "unauthorized"

    def test_stub_mode_short_circuits_before_region_gate(self):
        """Live Vultr still has PAYMENT_STUB_MODE=true; region=US never reaches 403."""
        with _client("true") as c:
            token = _register(c, "wx_stub_us@test.com")
            resp = c.post(
                "/v1/payment/wechat/order?region=US",
                json={"tier": "supporter", "trade_type": "NATIVE"},
                headers=_auth(token),
            )
            assert resp.status_code == 400
            assert resp.get_json()["error"] == "stub_mode"

    def test_us_region_rejected_with_403_when_stub_off(self):
        with _client("false") as c:
            token = _register(c, "wx_us_gate@test.com")
            resp = c.post(
                "/v1/payment/wechat/order?region=US",
                json={"tier": "supporter", "trade_type": "NATIVE"},
                headers=_auth(token),
            )
            body = resp.get_json()
            assert resp.status_code == 403
            assert body["error"] == "region_not_supported"

    def test_cn_region_does_not_use_overseas_gate(self):
        """CN is allowed through the region gate; missing creds → 503, not 403."""
        os.environ.pop("WECHAT_MCHID", None)
        os.environ.pop("WECHAT_API_V3_KEY", None)
        with _client("false") as c:
            token = _register(c, "wx_cn_gate@test.com")
            resp = c.post(
                "/v1/payment/wechat/order?region=CN",
                json={"tier": "supporter", "trade_type": "NATIVE"},
                headers=_auth(token),
            )
            body = resp.get_json()
            assert resp.status_code != 403
            assert body.get("error") != "region_not_supported"
            assert resp.status_code == 503
            assert body["error"] == "payment_not_configured"


class TestStripeCheckoutStub:
    def test_stripe_checkout_blocked_in_stub_mode(self):
        with _client("true") as c:
            token = _register(c, "stripe_stub@test.com")
            resp = c.post(
                "/v1/payment/stripe/checkout",
                json={"tier": "supporter", "mode": "payment"},
                headers=_auth(token),
            )
            assert resp.status_code == 400
            assert resp.get_json()["error"] == "stub_mode"

    def test_stripe_checkout_unauthenticated_401(self):
        with _client("false") as c:
            resp = c.post(
                "/v1/payment/stripe/checkout",
                json={"tier": "supporter"},
            )
            assert resp.status_code == 401

    def test_stripe_alias_checkout_maps_provider_fields_when_stub_off(self):
        """Deprecated /v1/payment/stripe/checkout hid AttributeError behind stub.

        CheckoutResult has provider_checkout_id / checkout_url, not session_id /
        session_url. Mock the provider so this fails without hitting Stripe.
        """
        from unittest.mock import patch

        from src.payment.providers.base import CheckoutResult

        fake = CheckoutResult(
            provider="stripe",
            checkout_url="https://checkout.stripe.com/c/pay/cs_test_mock",
            out_trade_no="LOOMAFAKE",
            provider_checkout_id="cs_test_mock",
        )
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_mock_not_real"
        try:
            with _client("false") as c:
                token = _register(c, "stripe_alias_ok@test.com")
                with patch(
                    "src.api.routes.payment_routes.stripe_create_checkout",
                    return_value=fake,
                ):
                    resp = c.post(
                        "/v1/payment/stripe/checkout",
                        json={"tier": "supporter", "mode": "payment"},
                        headers=_auth(token),
                    )
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)

        body = resp.get_json()
        assert resp.status_code == 201, body
        assert body["session_id"] == "cs_test_mock"
        assert body["session_url"] == "https://checkout.stripe.com/c/pay/cs_test_mock"
        assert body["tier"] == "supporter"
