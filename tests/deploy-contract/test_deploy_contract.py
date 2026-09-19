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
