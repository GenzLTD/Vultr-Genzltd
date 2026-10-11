"""Region isolation of outbound providers.

An overseas deploy (``DEPLOY_REGION != CN``) must not ship personal data to
mainland services. Two outbound dependencies are guarded:

* **LLM providers** — ``src.config.safe_llm_provider_order`` drops mainland
  providers (DeepSeek) and, crucially, does **not** fall back to them when the
  filtered list becomes empty. Resumes and chat bodies are sensitive personal
  data; cross-border transfer needs SCC + a transfer impact assessment
  (GDPR Art.44+) and a PIPL outbound mechanism. Degrading the feature is
  acceptable, silently exporting is not.
* **QCC (企查查) MCP** — ``src.credit.qcc_client`` refuses a plaintext-HTTP
  endpoint overseas, so the client reports itself disabled and the session
  manager refuses to build a session.

The autouse ``_billing_region_baseline`` fixture pins ``DEPLOY_REGION=CN`` for
the whole suite (see tests/conftest.py). Every test here overrides it on
purpose, so the suite keeps its domestic behaviour by default.
"""
from __future__ import annotations

import pytest

from src.agents import central_brain
from src.config import is_overseas_deploy, safe_llm_provider_order
from src.credit import qcc_client
from src.credit.qcc_client import QccMcpError, QccSessionManager

_HTTP_QCC = "http://1.14.202.161:8998/mcp"


class TestLlmProviderIsolation:
    def test_overseas_drops_mainland_providers(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        assert is_overseas_deploy() is True
        assert safe_llm_provider_order("deepseek,qwen,openai") == ["qwen", "openai"]

    def test_overseas_never_falls_back_to_mainland(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        # 全境内候选：宁可空，也不悄悄回退到 DeepSeek
        assert safe_llm_provider_order("deepseek") == []

    def test_overseas_empty_input_stays_empty(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        # 显式空 / 缺省值都不得被"补"回境内的 deepseek
        assert safe_llm_provider_order("") == []
        assert safe_llm_provider_order(None) == []
        assert safe_llm_provider_order("   ,  , ") == []

    def test_overseas_keeps_order_of_safe_providers(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        assert safe_llm_provider_order("openai,deepseek,ollama,qwen") == [
            "openai",
            "ollama",
            "qwen",
        ]

    def test_inland_is_unchanged(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "CN")
        assert is_overseas_deploy() is False
        assert safe_llm_provider_order("deepseek,qwen") == ["deepseek", "qwen"]

    def test_inland_default_order_is_deepseek(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "CN")
        assert safe_llm_provider_order(None) == ["deepseek"]

    def test_region_code_is_trimmed_and_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", " cn ")
        assert is_overseas_deploy() is False

    def test_unset_region_defaults_to_overseas(self, monkeypatch):
        # 默认安全：未配置区域时按海外处理，不能默认放行境内
        monkeypatch.delenv("DEPLOY_REGION", raising=False)
        assert is_overseas_deploy() is True
        assert safe_llm_provider_order("deepseek") == []

    def test_call_llm_never_reaches_mainland_overseas(self, app, monkeypatch):
        """接入点验证：海外区即使只剩 deepseek 候选，也不发出任何请求。"""
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        app.config["LLM_PROVIDER_ORDER"] = "deepseek"
        app.config["DEEPSEEK_API_KEY"] = "sk-a-real-looking-key"

        sent: list[tuple] = []
        monkeypatch.setattr(
            central_brain.requests, "post", lambda *a, **k: sent.append((a, k))
        )

        with app.app_context():
            assert central_brain._call_llm("hello") is None

        assert sent == [], "overseas deploy must not call a mainland LLM provider"


class TestQccEndpointIsolation:
    def test_overseas_plaintext_http_is_disabled(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        monkeypatch.setenv("QCC_MCP_BASE_URL", _HTTP_QCC)
        assert qcc_client.is_qcc_enabled() is False
        reason = qcc_client.qcc_disabled_reason()
        assert reason and "unencrypted" in reason

    def test_overseas_plaintext_returns_no_urls(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        monkeypatch.setenv("QCC_MCP_BASE_URL", _HTTP_QCC)
        assert qcc_client.get_qcc_base_urls() == {}

    def test_overseas_https_is_allowed(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        monkeypatch.setenv("QCC_MCP_BASE_URL", "https://agent.qcc.com/mcp")
        assert qcc_client.is_qcc_enabled() is True
        assert (
            qcc_client.get_qcc_base_urls()["company"]
            == "https://agent.qcc.com/mcp/company/stream"
        )

    def test_overseas_default_endpoint_is_https_and_enabled(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        monkeypatch.delenv("QCC_MCP_BASE_URL", raising=False)
        assert qcc_client.is_qcc_enabled() is True

    def test_inland_keeps_plaintext_behaviour(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "CN")
        monkeypatch.setenv("QCC_MCP_BASE_URL", _HTTP_QCC)
        assert qcc_client.is_qcc_enabled() is True
        assert qcc_client.get_qcc_base_urls()["company"].startswith("http://")

    def test_session_refuses_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        monkeypatch.setenv("QCC_MCP_BASE_URL", _HTTP_QCC)
        manager = QccSessionManager(auth_token="test-token")
        with pytest.raises(QccMcpError, match="disabled"):
            manager._get_session("company")

    def test_session_allowed_with_https(self, monkeypatch):
        monkeypatch.setenv("DEPLOY_REGION", "SG")
        monkeypatch.setenv("QCC_MCP_BASE_URL", "https://agent.qcc.com/mcp")
        manager = QccSessionManager(auth_token="test-token")
        session = manager._get_session("company")
        assert session.service_name == "company"
