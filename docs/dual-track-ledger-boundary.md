# 双轨账本边界（写死）

> Lock 2 / Lock 3 / Lock 4 仓内口径。配套 CI：`scripts/assert-payment-v1-same-blob.sh`、`scripts/assert-looma-join-semantics.sh`。  
> 未解除 `stack-v*` 生产禁令（仍以法兰克福 playbook：GFCC L0 1.6.0 + FRA 绿为准）。**本文件不授权 live SG 部署。**

---

## Lock 2 — 账本边界

| 项 | 口径 |
| --- | --- |
| 双轨 | **两本物理库**：大陆天翼（looma / Tianyi）vs 新加坡 Vultr（本仓 SG） |
| 认人规则 | 同轨内：`users.principal_sub` bootstrap=`users.id`；外部身份 `(issuer, subject)` ≔ `user_identities(provider, provider_uid)`（微信另认 `wechat_openid`） |
| 跨区余额合并 | **不是默认行为**。跨区同人 ≠ 自动并账；禁止把 CN 余额默认同步到 SG 或反向 |
| 「一本账」 | 仅指：**同部署 / 同物理库**内，多壳结算落到同一 `users.id` + `principal_sub` |

诚实范围：天翼 / FRA / SG 各一本库 —— 跨部署「全球一本余额」物理上不成立，除非另开显式迁移项目。

---

## Lock 1 — 契约同源

- `backend/contracts/payment.v1.json` 必须与 **looma tip** **同 git blob**。
- CI：`assert-payment-v1-same-blob.sh`（`Deploy stack` 扇入前必跑）。
- `contracts/gfcc/SOURCE.json`：两边都有时报告漂移；默认不因 SOURCE 漂移失败（`STRICT_GFCC_SOURCE=0`），对齐仍受 1.6.0 playbook 门禁。

---

## Lock 3 — 认人代码同源

SG 发布树必须携带：

1. `backend/src/identity/ledger_subject.py`（及 `__init__.py`）— 与 looma tip **同 blob**
2. `recompute_user_tier` 路径（`manager.py` + `settlement.py` 标记）

钉：`contracts/looma-join.PIN.json`（记录所需 looma SHA）。

**禁止**：用旧 Vultr 整树 overlay 盖掉 identity / join 标记（looma #39 事故：wholesale overlay 删海外 helper）。

`payment_routes.py` / 全量 `principal_sub` 接线：**验收清单强制**，本门禁不强制整文件同 blob（避免 wholesale）。

---

## Lock 4 — 验收 / 可观测

### `/health` 字段（可加、不破旧客户端）

| 字段 | 天翼 / looma | SG / vultr | 来源 |
| --- | --- | --- | --- |
| `deploy_track` | `"looma"` | `"vultr"` | `DEPLOY_REGION` / stack env 推断 |
| `git_commit` | **looma tip** | **Vultr tip** | `GIT_COMMIT` → `git_commit.txt` → rev-parse |
| `looma_sha` | **部署 tip**（=`git_commit`） | **join PIN only**（≠ tip） | CN：commit；SG：`LOOMA_SHA`←`looma-join.PIN.json` |
| `looma_sha_kind` | `"deploy_tip"` | `"join_pin"` | 与上配套 |
| `vultr_tag` | **null** | `stack-v*` | env `VULTR_TAG` / `STACK_TAG` |
| `stack_sha` | **null** | 本仓发布 SHA | env `STACK_SHA`（缺则回退 `git_commit`） |

**探活「认对树」（Issue #46 §2）：**
1. 天翼版本 → 只认 `looma_sha` / `git_commit`；`stack_sha`/`vultr_tag` 必须为 null
2. SG 版本 → 只认 `stack_sha` + `vultr_tag`；**禁止**用 SG.`looma_sha` 与天翼 tip 比先后（PIN 落后 ≠ 栈落后）
3. deploy 写入：`echo "$GITHUB_SHA" > backend/git_commit.txt` 必须是**本仓** tip；FRA/SG 不得写入 looma SHA

生产改 health 若暂缓：以 CI 门禁 + 本清单验收；缺 env 时 SG.`looma_sha` 可为 null，不失败 `/health`。

### 验收用例

| # | 用例 | 期望 |
| --- | --- | --- |
| A | **同区双登录同账**（同物理库：微信/email/华为等绑到同一 `users.id`） | `principal_sub` 一致；档位/订单一本可见 |
| B | **跨区负例**（天翼用户 ≠ 默认拥有 SG 余额） | 跨区登录不得静默并账；余额独立 |

---

## Secrets / CI 备注

| 项 | 说明 |
| --- | --- |
| 本门禁 | 无新 secret；`actions/checkout` looma 用 `contents: read`（public）或已有 org token |
| 部署 | 仍用既有 `SSH_PRIVATE_KEY` / `DEPLOY_*`；**不要**为验门禁打生产 `stack-v*` |
| looma 派发 | `VULTR_DEPLOY_DISPATCH_TOKEN` 仍只在 looma `deploy-sg.yml`；本仓门禁不读它 |
| 相关 PR | 见 Project Store `docs/dual-track-gate-prs.md` |
