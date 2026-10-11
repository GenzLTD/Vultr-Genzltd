"""部署契约测试 — 守本仓管线与 GFCC 协议钉。

唯一协议真源是 contracts/gfcc（GenzLTD/gfcc）。backend/ 是海外运行时，
可以按管辖分叉，不是 looma-zervi 的冻结钉。

管线层另守：

  - .github/workflows/deploy.yml   双门禁扇入 8 步部署
  - scripts/bootstrap-env.sh        set_kv 非密钥每轮对齐 / seed_kv 密钥不覆盖
  - .env.example                   环境变量键清单与回调意图
  - frontend/.../Pricing.tsx       收银台回调 URL 的运行时真源

本文件不放进 backend/：参考国内实现时整树拷贝，不能把本仓管线不变量盖掉。
禁止把 workflow/bootstrap 断言加回 backend/tests/。

可直接运行（dryrun.sh 第 3 步调用，无需 pytest），也可被 pytest 收集。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_YML = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
BOOTSTRAP_ENV = REPO_ROOT / "scripts" / "bootstrap-env.sh"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
GFCC_SOURCE = REPO_ROOT / "contracts" / "gfcc" / "SOURCE.json"
BACKEND_SOURCE = REPO_ROOT / "backend" / "SOURCE.json"
BACKEND_CONTRACTS = REPO_ROOT / "backend" / "contracts"
PRICING_TSX = (
    REPO_ROOT / "frontend" / "packages" / "saas" / "src" / "features" / "pricing" / "Pricing.tsx"
)

TSPACE_SUCCESS = "https://tspace.genz.ltd/pricing?status=success"
TSPACE_CANCEL = "https://tspace.genz.ltd/pricing?status=cancel"


class TestStripeHostIntent:
    """Config-intent lock only — Python 不读 STRIPE_SUCCESS_URL。

    运行时回调用 Pricing.tsx 的 window.location.origin（见
    TestPricingReturnUrlSource）。这里防止的是 bootstrap-env.sh /
    .env.example 把回调意图滚回裸域 genz.ltd。
    """

    def test_bootstrap_env_writes_tspace_host(self):
        text = BOOTSTRAP_ENV.read_text(encoding="utf-8")
        assert f"set_kv STRIPE_SUCCESS_URL {TSPACE_SUCCESS}" in text, (
            "bootstrap-env.sh 必须以 set_kv 写入 tspace 回调 Success URL"
        )
        assert f"set_kv STRIPE_CANCEL_URL {TSPACE_CANCEL}" in text, (
            "bootstrap-env.sh 必须以 set_kv 写入 tspace 回调 Cancel URL"
        )
        for line in text.splitlines():
            if "STRIPE_SUCCESS_URL" in line or "STRIPE_CANCEL_URL" in line:
                assert "tspace.genz.ltd" in line, f"回调意图滚回非 tspace 域: {line}"

    def test_env_example_matches_intent(self):
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert f"STRIPE_SUCCESS_URL={TSPACE_SUCCESS}" in text
        assert f"STRIPE_CANCEL_URL={TSPACE_CANCEL}" in text

    def test_stripe_secrets_are_seed_kv_not_set_kv(self):
        """密钥只允许 seed_kv（缺失才写），禁止 set_kv 每轮覆盖。

        set_kv 会把机器上的 Live 验签密钥打回旧值（looma-zervi #19
        钉死的反漂移不变量，在本仓的等价物）。
        """
        text = BOOTSTRAP_ENV.read_text(encoding="utf-8")
        for key in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
            seed = [l for l in text.splitlines() if f"seed_kv {key}" in l]
            overwrite = [l for l in text.splitlines() if f"set_kv {key}" in l]
            assert seed, f"{key} 必须有 seed_kv 行"
            assert not overwrite, f"{key} 是密钥，禁止 set_kv 覆盖: {overwrite}"


class TestDeployOrder:
    def test_git_commit_marker_is_written_before_compose_up(self):
        """版本溯源标记必须先于任何 compose up 写入（对齐 looma-zervi 契约）。"""
        lines = DEPLOY_YML.read_text(encoding="utf-8").splitlines()
        marker = [i for i, l in enumerate(lines)
                  if "github.sha" in l and "git_commit.txt" in l]
        ups = [i for i, l in enumerate(lines)
               if " up -d" in l and "backend" in l]
        assert marker, "deploy.yml 必须写 git_commit 标记"
        assert ups, "deploy.yml 必须有 compose up 步骤"
        assert min(marker) < min(ups), "git_commit 必须先于第一个 compose up"


class TestPricingReturnUrlSource:
    def test_pricing_checkout_uses_window_location_origin(self):
        """运行时收银台回调：浏览器 origin，不是硬编码域。

        tspace.genz.ltd 上的用户因此回到
        https://tspace.genz.ltd/pricing?status=success。在这里硬编码
        genz.ltd（或任何其他域）都会破坏该契约。
        """
        text = PRICING_TSX.read_text(encoding="utf-8")
        assert "success_url: `${window.location.origin}/pricing?status=success`" in text
        assert "cancel_url: `${window.location.origin}/pricing?status=cancel`" in text
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("success_url:") or stripped.startswith("cancel_url:"):
                assert "window.location.origin" in line
                assert "genz.ltd" not in line
                assert "http://" not in line
                assert "https://" not in line


class TestGfccIsUniqueProtocolSource:
    """协议只认 GFCC；backend 是运行时，可以变。"""

    def test_gfcc_source_is_the_authority(self):
        pin = json.loads(GFCC_SOURCE.read_text(encoding="utf-8"))
        assert pin.get("authority") == "GenzLTD/gfcc"
        assert pin.get("layer") == "L0-pin"
        assert pin.get("unique_protocol_source") is True
        assert len(pin.get("commit") or "") >= 40

    def test_backend_source_defers_protocol_to_gfcc(self):
        doc = json.loads(BACKEND_SOURCE.read_text(encoding="utf-8"))
        assert BACKEND_SOURCE.is_file(), "backend/ 必须声明自己不是协议真源"
        assert doc.get("role") == "overseas-runtime"
        assert doc.get("not") == "protocol source"
        assert doc.get("protocol") == "contracts/gfcc"
        assert doc.get("protocol_authority") == "GenzLTD/gfcc"
        assert doc.get("may_diverge") is True

    def test_backend_product_contracts_do_not_name_looma_as_protocol_source(self):
        files = sorted(BACKEND_CONTRACTS.glob("*.json"))
        assert files, "backend/contracts 应有产品契约"
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert "真源：looma-zervi" not in text, (
                f"{path.name} 仍把 looma-zervi 写成协议真源"
            )
            desc = json.loads(text).get("description") or ""
            assert "looma-zervi/backend/contracts" not in desc, (
                f"{path.name} description 仍指向 looma 产品契约路径"
            )

    def test_deploy_yml_asserts_gfcc_before_pytest(self):
        lines = DEPLOY_YML.read_text(encoding="utf-8").splitlines()
        ac = [i for i, line in enumerate(lines) if "assert-contracts.sh" in line]
        py = [i for i, line in enumerate(lines) if "pytest" in line and "tests/" in line]
        assert ac, "deploy.yml 必须跑 GFCC 契约门禁"
        assert py, "deploy.yml 必须跑 backend pytest"
        assert min(ac) < min(py), "GFCC 契约门禁必须先于 pytest"

    def test_this_file_is_outside_backend(self):
        rel = Path(__file__).resolve().relative_to(REPO_ROOT)
        assert "backend" not in rel.parts, "管线契约不得放进 backend/"


class TestOverseasDataPlane:
    """钱和海外管理号以 Vultr 为准；整库不是对齐面。"""

    DOC = REPO_ROOT / "docs" / "looma-overseas" / "DATA-PLANE.md"

    def test_data_plane_doc_exists(self):
        assert self.DOC.is_file(), "缺少海外数据面对账册"

    def test_vultr_is_payment_write_authority(self):
        text = self.DOC.read_text(encoding="utf-8")
        assert "Stripe 订单" in text
        assert "Vultr" in text
        assert "禁止" in text
        assert "覆盖" in text
        assert "zervi@genz.ltd" in text
        assert "DEPLOY_ENABLED" in text


class TestOverseasEgressGuardsInBootstrap:
    """海外区数据出境守卫的**配置侧**不变量。

    运行时行为在 backend/tests/（`test_overseas_provider_isolation.py` 与
    `test_overseas_readiness_consistency.py`）。这里只守纯文本配置 —— 本文件必须
    能被 runpy 独立执行，不 import backend。

    守的原因：`bootstrap-env.sh` 是目标机 `.env` 的每轮对齐源，而海外区的运行时
    还要过一层守卫。两边一旦脱节，就会出现「.env 写着 deepseek、运行时被静默
    剔除」「开关 true、调用全失败」这类不报错、但上线后功能莫名不可用的错配。
    """

    def test_llm_order_keeps_a_non_inland_candidate(self):
        """海外区会剔除境内 provider(deepseek)，候选里必须留非境内的。

        否则过滤后为空 —— 那不算「安全降级」，是 LLM 主链整体不可用。
        """
        lines = [
            line for line in BOOTSTRAP_ENV.read_text(encoding="utf-8").splitlines()
            if line.startswith("set_kv LLM_PROVIDER_ORDER")
        ]
        assert lines, "bootstrap-env.sh 必须声明 LLM_PROVIDER_ORDER"
        assert ("openai" in lines[0]) or ("ollama" in lines[0]), (
            f"候选里没有非境内 provider，海外区会被过滤成空: {lines[0]}"
        )

    def test_qcc_enabled_is_derived_from_the_endpoint_scheme(self):
        """QCC_ENABLED 不得写死。

        海外区拒绝明文 HTTP 端点（`credit.qcc_client.qcc_disabled_reason`）。
        写死 true 就成了「开关开着、每次调用都失败」。
        """
        text = BOOTSTRAP_ENV.read_text(encoding="utf-8")
        assert 'set_kv QCC_ENABLED "$QCC_ENABLED_AUTO"' in text, (
            "QCC_ENABLED 必须由端点 scheme 推导"
        )
        mapping = dict(re.findall(r"^\s*(\S+)\)\s*QCC_ENABLED_AUTO=(\w+)", text, re.M))
        assert mapping.get("https://*") == "true", "HTTPS 端点应放行 QCC"
        assert mapping.get("*") == "false", "非 HTTPS（含明文 HTTP）端点应关闭 QCC"

    def test_qcc_base_default_is_explicit(self):
        """QCC 端点默认值要显式写出，便于一处切换 —— 不留隐含兜底。"""
        text = BOOTSTRAP_ENV.read_text(encoding="utf-8")
        assert re.search(r'QCC_BASE="\$\{QCC_MCP_BASE_URL:-[^}]+\}"', text), (
            'bootstrap-env.sh 必须以 QCC_BASE="${QCC_MCP_BASE_URL:-<默认>}" 定义端点'
        )


class TestGatesAndDeployConcurrency:
    """门禁按 ref 隔离、部署全局串行且**不可取消**。

    旧的单组写法（workflow 级 `group: deploy-stack` + `cancel-in-progress: true`）
    让所有 ref 共用一个组，并发到达的运行互相取消 —— 实测被取消 4 次。PR 门禁被
    取消尤其危险：界面显示「跑过了」，实际一条断言都没执行。
    """

    def test_gate_concurrency_is_ref_scoped(self):
        text = DEPLOY_YML.read_text(encoding="utf-8")
        assert "group: stack-gates-${{ github.ref }}" in text, (
            "门禁的 concurrency 组必须按 ref 隔离，否则并发 PR 的运行互相取消"
        )

    def test_deploy_is_serialized_and_not_cancellable(self):
        text = DEPLOY_YML.read_text(encoding="utf-8")
        assert "group: deploy-stack" in text, "部署要有独立的全局组"
        assert "cancel-in-progress: false" in text, (
            "部署不能中途被取消：中断会留下半套栈"
        )


class TestSaasTaxCodeConfig:
    """税码配置意图锁：SaaS 必须配数字产品段税码（txcd_1xxxxxxx）。

    历史教训：bootstrap-env.sh / .env.example 曾写 txcd_30040001
    （物理商品段），Stripe 对数字 SaaS 视为无效，建结账会话直接报错。
    官方定义见 docs.stripe.com/tax/tax-codes：
    txcd_10103000 = "Software as a service (SaaS) - personal use"。
    """

    SAAS_PERSONAL_USE = "txcd_10103000"

    def test_bootstrap_env_writes_saas_tax_code(self):
        text = BOOTSTRAP_ENV.read_text(encoding="utf-8")
        assert f"set_kv STRIPE_TAX_CODE {self.SAAS_PERSONAL_USE}" in text, (
            "bootstrap-env.sh 必须写入官方 SaaS - personal use 税码"
        )

    def test_env_example_declares_saas_tax_code(self):
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert f"STRIPE_TAX_CODE={self.SAAS_PERSONAL_USE}" in text

    def test_no_physical_goods_tax_code_anywhere_in_pipeline(self):
        for path in (BOOTSTRAP_ENV, ENV_EXAMPLE):
            for line in path.read_text(encoding="utf-8").splitlines():
                if "STRIPE_TAX_CODE" in line and "txcd_" in line:
                    assert "txcd_3" not in line, (
                        f"{path.name} 的税码落在物理商品段（txcd_3xxxxxx）: {line}"
                    )


if __name__ == "__main__":
    import sys

    failures = 0
    for cls_name in sorted(n for n in dir() if n.startswith("Test")):
        cls = globals()[cls_name]
        for meth_name in sorted(m for m in dir(cls) if m.startswith("test_")):
            label = f"{cls_name}.{meth_name}"
            try:
                getattr(cls(), meth_name)()
            except Exception as exc:  # noqa: BLE001 — 直接运行模式要逐项报全
                failures += 1
                print(f"  \033[31m✗\033[0m {label}: {exc}")
            else:
                print(f"  \033[32m✓\033[0m {label}")
    sys.exit(1 if failures else 0)
