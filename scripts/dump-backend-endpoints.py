#!/usr/bin/env python3
"""Dump **本仓**后端（即将发布的版本）的 Flask url_map。

契约门禁要拿"即将发布"的后端路由去对线上前端 bundle，
不能用线上 api.genz.ltd 的 GET /v1/endpoints —— 那是**当前**版本。

用法（working-directory: backend）：
    PYTHONPATH=. python ../scripts/dump-backend-endpoints.py \
        > /tmp/backend-endpoints.json

stdout 是 JSON（供 check-frontend-contract.py 消费），
所有日志走 stderr，避免污染输出。
"""

from __future__ import annotations

import json
import os
import sys

# 只为把 app 构造出来读 url_map，不连任何外部依赖；
# 与 backend/tests/conftest.py 的 CI 环境变量口径一致。
DEFAULT_ENV = {
    "JWT_SECRET": "contract-gate",
    "DATABASE_PATH": ":memory:",
    "DEPLOY_REGION": "SG",
    "WECHAT_DEV_MODE": "true",
    "WECHAT_APPID": "test_appid",
    "WECHAT_SECRET": "test_secret",
    "DEEPSEEK_API_KEY": "skip",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
    "CHROMA_PERSIST_DIR": "/tmp/chroma_ci",
}


def main() -> int:
    backend_dir = os.environ.get("BACKEND_DIR", ".")
    sys.path.insert(0, os.path.abspath(backend_dir))

    for key, value in DEFAULT_ENV.items():
        os.environ.setdefault(key, value)

    from src.app import create_app  # noqa: E402  (必须在 sys.path 之后导入)

    # production 最接近线上注册结果；若缺配置则逐级回退，保证门禁不会因为
    # 构造不出 app 而静默失效（构造不出来 = 直接 fail，不跳过检查）。
    envs = os.environ.get("DUMP_APP_ENV", "production,testing,development").split(",")
    last_err: BaseException | None = None

    for env in envs:
        try:
            app = create_app(env)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[dump] create_app({env!r}) 失败: {exc}", file=sys.stderr)
            continue

        rules = []
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            rules.append({
                "rule": rule.rule,
                "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            })
        json.dump({"env": env, "rules": rules}, sys.stdout, ensure_ascii=False, indent=2)
        print(f"[dump] env={env!r}, {len(rules)} 条规则", file=sys.stderr)
        return 0

    print(f"::error::无法构造 app（最后错误: {last_err}）", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
