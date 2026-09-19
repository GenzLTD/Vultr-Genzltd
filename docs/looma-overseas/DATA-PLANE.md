# 海外数据面（Owner 对账）

2026-09-19 只读对账。不依赖境内仓、不等天翼库。快照包 `looma-db-aligned-20260919.zip`。

| 资产 | 权威 | 不是 |
|---|---|---|
| Stripe 订单 / webhook 发货 | **本机 Vultr** `looma.db` | 腾讯库、任何「对齐后覆盖」 |
| 海外管理号 `zervi@genz.ltd` | 只在 Vultr | 不要灌进境内 |
| 5 个真人 UUID | 两边已同号（身份层） | 不等于整库可镜像 |
| `beta_*@looma.test` | 各环境多种子 | 邮箱相同、UUID 不同，不是同一个人 |

包内 `vultr-looma.db` SHA256 = 现网 `/app/data/looma.db`（mtime 2026-09-17 14:26）。`PRAGMA integrity_check=ok`。

## 现网（2026-09-19 Win SSH）

- `PAYMENT_STUB_MODE=false`，`DEPLOY_REGION=SG`
- 用户 10：4 beta + 5 真人 + `zervi@genz.ltd`（`tier=free`）
- 订单 1：`b935165e` / `aac7a4fc` / supporter / **1.99 USD** / **`pending`** / `paid_at` 空
- `git_commit` 仍是 `a52638e`（不是境内 `9751945`）
- 同日海外 Owner 对标腾讯 P0：`DOCKER-USER` 封公网 `5200/6379/8000`，unit `block-docker-ports.service` enabled。compose 仍是 `0.0.0.0`（根因留给受控发版）。回环 `/health` 与 `https://api.genz.ltd/health` 仍 200。未开 `DEPLOY_ENABLED`。

钱没入账是 webhook 验签问题，不是库没对齐。禁止伪造事件、禁止把腾讯库拷上来「补齐」。下一步仍是：对齐或轮换 Live `whsec`，再 Dashboard Resend；手术刀是 `rotate-overseas-stripe.yml`（保留，只 Win 触发）。

## 禁止

- 用腾讯 `looma.db` 覆盖 Vultr，或反向覆盖。
- 把 `zervi@genz.ltd` 或 pending 订单同步进境内。
- 等天翼再出一份库才动海外。天翼缺快照只影响境内仓，不影响本面。
- 打开 `DEPLOY_ENABLED` 当对账的收口。对账不授权自动发版。

## 钉

`TestOverseasDataPlane`（`tests/deploy-contract/`）：本文件必须存在，且写明 Vultr 是支付写权威、禁止整库覆盖、`zervi` 只在海外。
