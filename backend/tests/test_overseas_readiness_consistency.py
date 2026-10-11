"""海外区「对外呈现」与运行时守卫的自洽性。

海外区（`DEPLOY_REGION=SG`）有两道数据出境守卫会改变功能可用性：
`config.safe_llm_provider_order` 剔除境内 LLM，`credit.qcc_client.
qcc_disabled_reason` 拒绝明文 HTTP 端点。

守卫**本身**的行为由 `tests/test_overseas_provider_isolation.py` 覆盖。这里只盯
最容易出错的那一层：接口与就绪页不能声称「可用」，而实际每次调用都失败。

配置侧（`scripts/bootstrap-env.sh`、`deploy.yml`）的不变量不在这里 —— 按
`tests/deploy-contract/test_deploy_contract.py` 的约定，管线断言一律不进
`backend/tests/`。
"""
from __future__ import annotations

import pytest

PLAINTEXT_QCC = "http://1.14.202.161:8998/mcp"
HTTPS_QCC = "https://agent.qcc.com/mcp"


@pytest.fixture
def sg(_billing_region_baseline, monkeypatch):
    """海外区环境（依赖 conftest 的 autouse 基线以保证本 fixture 后应用）。"""
    monkeypatch.setenv("DEPLOY_REGION", "SG")


class TestCreditRouteMatchesTheGuard:
    """路由层必须与 qcc_client 的拒绝保持一致。"""

    def test_guard_blocks_even_when_the_flag_is_on(self, sg, app, monkeypatch):
        monkeypatch.setenv("QCC_MCP_BASE_URL", PLAINTEXT_QCC)
        monkeypatch.setenv("QCC_AUTH_TOKEN", "tok")
        with app.app_context():
            app.config["QCC_ENABLED"] = True
            from src.api.routes.credit_routes import _qcc_is_configured

            assert _qcc_is_configured() is False, (
                "开关开着但端点是明文 HTTP：海外区必须报不可用，"
                "否则接口对外说谎、调用却全失败"
            )

    def test_https_endpoint_with_token_reports_configured(self, sg, app, monkeypatch):
        monkeypatch.setenv("QCC_MCP_BASE_URL", HTTPS_QCC)
        monkeypatch.setenv("QCC_AUTH_TOKEN", "tok")
        with app.app_context():
            app.config["QCC_ENABLED"] = True
            from src.api.routes.credit_routes import _qcc_is_configured

            assert _qcc_is_configured() is True


class TestReadinessPageUsesTheRegionFilteredOrder:
    """就绪页的 LLM 项必须按区域过滤后判定。"""

    @staticmethod
    def _llm_item(app, order: str, **cfg_overrides) -> dict | None:
        """就绪页只列 open 项；这里返回该项，正常（done）时返回 None。"""
        from src.open_items import load_open_items

        with app.app_context():
            app.config["LLM_PROVIDER_ORDER"] = order
            app.config["OPENAI_API_KEY"] = ""
            for key, value in cfg_overrides.items():
                app.config[key] = value
            items = load_open_items(app)["list"]
        return next((i for i in items if i["id"] == "llm-provider"), None)

    def test_overseas_hides_inland_and_flags_the_missing_key(self, sg, app):
        item = self._llm_item(app, "openai,ollama")
        assert item is not None, "没有 OPENAI_API_KEY，海外区必须告警"
        assert "deepseek" not in item["notes"], "海外区不该再把 deepseek 当候选"
        assert item["priority"] == "P0"

    def test_inland_still_lists_deepseek_as_a_candidate(self, app):
        item = self._llm_item(app, "deepseek,openai,ollama")
        assert item is not None
        assert "deepseek" in item["notes"]

    def test_configured_provider_clears_the_item(self, sg, app):
        item = self._llm_item(
            app, "openai,ollama", OPENAI_API_KEY="sk-live-abcdefghijklmnopqrstuvwxyz"
        )
        assert item is None, "配好 key 后该项必须消警（不再出现在就绪页）"
