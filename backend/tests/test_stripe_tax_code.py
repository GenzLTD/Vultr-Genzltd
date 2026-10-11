"""Stripe 税码契约 —— SaaS 必须用数字产品段税码，且放在内联 Product 上。

两层教训（各踩过一次）：

1. **码值**：现网曾配 `txcd_30040001`（txcd_3xxxxxx = 服装/口罩等物理商品段），
   Stripe 对数字 SaaS 视为无效税码。官方目录（docs.stripe.com/tax/tax-codes）：

     txcd_10103000  Software as a service (SaaS) - personal use   ← 本项目（买家为个人）
     txcd_10103001  Software as a service (SaaS) - business use  ← 不涉及
     txcd_1xxxxxxx  数字产品段
     txcd_3xxxxxxx  物理商品段

2. **放置**：税码必须挂在**内联 Product**（`price_data[product_data][tax_code]`），
   放 `price_data[tax_code]` 或 line item 上 Stripe 回 `parameter_unknown`
   （PR #14 的教训）。

本文件锁两件事：配置默认值落在数字产品段；结账会话把税码放到正确的位置。
"""
from __future__ import annotations

from src.payment.providers.stripe import StripeProvider

SAAS_PERSONAL_USE = "txcd_10103000"  # 官方：SaaS - personal use


def _base_config(**overrides) -> dict:
    cfg = {
        "STRIPE_SECRET_KEY": "sk_test_unit",
        "STRIPE_TAX_ENABLED": "true",
        "STRIPE_TAX_CODE": SAAS_PERSONAL_USE,
    }
    cfg.update(overrides)
    return cfg


class _CaptureApi:
    """替身 _api_request：记录请求体，返回最小可用会话。"""

    def __init__(self):
        self.data: dict[str, str] | None = None

    def __call__(self, method, path, secret_key, data):
        self.data = dict(data)
        return {"id": "cs_test_capture", "url": "https://checkout.stripe.com/c/pay/x"}


def _checkout(config: dict, mode: str, metadata: dict | None = None) -> dict[str, str]:
    provider = StripeProvider()
    cap = _CaptureApi()
    provider._api_request = cap  # type: ignore[method-assign]
    provider.create_checkout(
        config,
        out_trade_no="OUT-1",
        tier="supporter",
        amount=1.99,
        currency="USD",
        plan_name="Supporter",
        customer_email="buyer@example.com",
        mode=mode,
        metadata=metadata,
    )
    assert cap.data is not None
    return cap.data


class TestTaxCodeDefault:
    def test_default_is_official_saas_personal_use_code(self):
        from src import config as config_mod

        assert config_mod.Config.STRIPE_TAX_CODE == SAAS_PERSONAL_USE

    def test_default_is_in_digital_goods_family(self):
        """数字产品税码必须落在 txcd_1xxxxxxx 段；3xxxxxx 是物理商品。"""
        from src import config as config_mod

        code = config_mod.Config.STRIPE_TAX_CODE
        assert code.startswith("txcd_1"), (
            f"税码 {code} 不在数字产品段（txcd_1xxxxxxx）；"
            "物理商品段（txcd_3xxxxxx）会让 Stripe 拒绝建结账会话"
        )


class TestCheckoutTaxCodePlacement:
    def test_subscription_checkout_puts_tax_code_on_inline_product(self):
        data = _checkout(_base_config(), mode="subscription")
        assert data["automatic_tax[enabled]"] == "true"
        assert data["tax_id_collection[enabled]"] == "true"
        assert data["line_items[0][price_data][product_data][tax_code]"] == SAAS_PERSONAL_USE
        # 放错位置的历史形态必须绝迹（Stripe: parameter_unknown）
        assert "line_items[0][price_data][tax_code]" not in data
        assert "line_items[0][tax_code]" not in data

    def test_payment_checkout_puts_tax_code_on_inline_product(self):
        data = _checkout(_base_config(), mode="payment")
        assert data["line_items[0][price_data][product_data][tax_code]"] == SAAS_PERSONAL_USE
        assert "line_items[0][tax_code]" not in data

    def test_price_id_path_sends_no_inline_tax_code(self):
        """带 Price ID 的订阅沿用该 Price 上的 Product，不再塞 price_data。"""
        data = _checkout(
            _base_config(), mode="subscription", metadata={"stripe_price_id": "price_123"}
        )
        assert data["line_items[0][price]"] == "price_123"
        assert not any("tax_code" in k for k in data)

    def test_tax_code_env_override_respected(self):
        data = _checkout(_base_config(STRIPE_TAX_CODE="txcd_10103001"), mode="subscription")
        assert data["line_items[0][price_data][product_data][tax_code]"] == "txcd_10103001"

    def test_tax_disabled_omits_tax_fields_entirely(self):
        data = _checkout(_base_config(STRIPE_TAX_ENABLED="false"), mode="subscription")
        assert not any("tax" in k for k in data), (
            "关掉 Stripe Tax 后不应残留任何 tax 字段"
        )


class TestContractDeclaresSaasCode:
    """membership.v1.json 是税务口径的单一声明处，别和代码漂移。"""

    def test_membership_contract_tax_code_matches_code_default(self):
        import json
        from pathlib import Path

        contract = json.loads(
            (Path(__file__).resolve().parents[1] / "contracts" / "membership.v1.json")
            .read_text(encoding="utf-8")
        )
        assert contract["tax"]["tax_code"] == SAAS_PERSONAL_USE
        assert contract["tax"]["automatic_tax_enabled"] is True
