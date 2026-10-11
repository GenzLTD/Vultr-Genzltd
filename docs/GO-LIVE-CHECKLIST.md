# 海外站上线（真实收款）Checklist

> 适用：`Vultr-Genzltd` 作为海外部署唯一真源后的首次切栈，以及此后每次发版。
>
> **核心口径：代码合入 `main` ≠ 上线。** `deploy` job 需要
> `vars.DEPLOY_ENABLED == 'true'` **且**由 tag `stack-v*`（或手动 dispatch 且
> `dry_run=false`）触发；否则永远 `skipped`。

---

## 0. 现状（本文档撰写时的实测事实，动手前先复测）

- 现网 `/opt/looma-zervi` 的容器**已经在跑真实支付**：`DEPLOY_REGION=SG` +
  `PAYMENT_STUB_MODE=false`，由 `looma-zervi` 仓的 `deploy-overseas.yml`
  （`rsync -avz --delete` 全树）驱动。
- 本仓 `deploy` job 恒 `skipped`（`vars.DEPLOY_ENABLED` 非 true）
  ⇒ **本仓合并 main 不影响现网**。
- 「切栈」= 让本仓接管那条通道。§3 的阻塞没清掉之前，**不要**临时打开
  `DEPLOY_ENABLED`。

---

## 1. 硬门（缺一不可）

| # | 项 | 位置 | 不做的后果 |
|---|---|---|---|
| 1 | `PAYMENT_STUB_MODE=false` | 机器 `backend/.env`（`bootstrap-env.sh` 已设） | 默认值是 **true**；不设则 `POST /v1/membership/subscribe` 直接 400 `stub_mode`，收银台根本不开 |
| 2 | `STRIPE_SECRET_KEY` = live key | GitHub secret `ENV_STRIPE_SECRET_KEY` | 空或 test key → `payment_not_configured` 503 |
| 3 | `STRIPE_WEBHOOK_SECRET` = live `whsec` | GitHub secret `ENV_STRIPE_WEBHOOK_SECRET` | 与 Dashboard 的 endpoint 不匹配 → 验签失败，订阅永不激活 |
| 4 | Stripe 账户：KYC 完成、Test→Live 可用 | Stripe Dashboard | 未「激活收款」前无法创建真实收款 |
| 5 | Stripe Tax 激活 + 税务注册地 | Stripe Dashboard → Tax | 代码侧 `STRIPE_TAX_ENABLED=true` / `tax_code=txcd_10103000` 已默认开，但**没有注册地就不会实际计税** |
| 6 | Billing Portal 打开「取消订阅」 | Stripe Dashboard → Billing → Customer portal | 代码只负责开会话；不开则 Portal 里取消不了，`POST /v1/membership/portal` 形同虚设 |
| 7 | `MEMBERSHIP_PORTAL_RETURN_HOSTS` | 机器 env | 前后端不同源时 Portal 回跳被拒 → 400 `invalid_return_url` |
| 8 | `OPENAI_API_KEY` | GitHub secret `ENV_OPENAI_API_KEY` | 海外区 `deepseek` 被出境守卫剔除，见 §2 |
| 9 | `vars.DEPLOY_ENABLED=true` | GitHub repo variables | 不打开则 deploy 永远跳过 |
| 10 | 打 tag `stack-vX.Y.Z` | git（先 push 分支，再单独 push tag） | `deploy.yml` 只认 `stack-v*` |

> **命名坑（别照 env 名建 secret）**：GitHub secret 名带 `ENV_` 前缀——`deploy.yml`
> 就是这么引用的（`secrets.ENV_STRIPE_SECRET_KEY`、`secrets.ENV_OPENAI_API_KEY`）。
> 而 `bootstrap-env.sh` 写到机器 `backend/.env` 的键名**不带**前缀
> （`STRIPE_SECRET_KEY` / `OPENAI_API_KEY`）。少写 `ENV_` 会**静默注入为空**，
> 不报错，只表现为功能不可用。

**关于 Price ID**：会员订阅走的是 `price_data`（金额内联，取契约
`backend/contracts/payment.v1.json` 的 `price_monthly`），**不需要**预先在 Stripe
建 Price 对象。`stripe_price_id` 只在通用 `/v1/payment/checkout` 链路里作为可选覆盖。

### 1.1 Stripe Tax 登记 —— YEDALL 侧要单独做的（与代码无关）

税码已由代码改为 **`txcd_10103000`（SaaS - personal use）**：官方目录确认它是
「卖给个人的托管 SaaS」唯一正确码。原用的 `txcd_30040001` 属物理商品段
（txcd_3xxxxxx = 服装/口罩类），对数字 SaaS 无效；且 PR #14 证实税码必须放在
**内联 Product**（`price_data[product_data][tax_code]`）上，放 Price/line item 上
Stripe 回 `parameter_unknown`。business use 是 `txcd_10103001`，本项目不涉及。

代码换码只是"申报口径"对了；**没有税务登记，Stripe Tax 对任何辖区都算出 0 税**
（`not_collecting`）。剩下的登记与验收是 Stripe Dashboard / 税务顾问的事：

| # | 事项 | 谁 | 说明 |
|---|---|---|---|
| 1 | 确定登记清单 | 税务顾问 | 按买家所在地定：哪里要登记 VAT / 销售税 / GST（欧盟 OSS、英国 VAT、美国各州 economic nexus、澳洲 GST 各有门槛）。Stripe 只会**代算代缴已登记辖区**，不会替你决定登记义务 |
| 2 | 把登记录进 Stripe Tax | YEDALL | Dashboard → Tax → Registrations。**美国部分州可由 Stripe 代办注册**；**美国以外经 Taxually 代办**。录入后该辖区才开始实际计税 |
| 3 | Webhook（live） | YEDALL | Dashboard 建 live endpoint（`/v1/membership/webhook/stripe`），把 live `whsec` 对齐 GitHub secret `ENV_STRIPE_WEBHOOK_SECRET`（§1 第 3 项） |
| 4 | Portal 打开「取消订阅」 | YEDALL | Dashboard → Billing → Customer portal（§1 第 6 项，代码只负责开会话） |
| 5 | 一笔真实 $1.99 验收 | YEDALL | supporter 档月付（`payment.v1.json` US 区单一真相源）。验收点见 §4 第 7 条；**重点看发票行**：税码=`txcd_10103000`、按买家地址出现对应税行（登记过的辖区）或 `not_collecting`（未登记） |

---

## 2. 海外区（`DEPLOY_REGION=SG`）的两处「有意降级」——必须知情

合入数据出境守卫后，SG 相对 CN 会有两处**故意的**行为差异：

| 功能 | 变化 | 原因 | 处理 |
|---|---|---|---|
| LLM | `deepseek` 从候选里剔除 | 简历 / 聊天正文是敏感个人数据，越境需要 SCC + 传输影响评估（GDPR Art.44+）与 PIPL 出境机制 | 配好 `OPENAI_API_KEY`；`bootstrap-env.sh` 的默认候选已改为 `openai,ollama`，且含非境内候选时守卫会放行 |
| 企查查 QCC | 明文 HTTP 端点被整体拒绝 ⇒ 功能不可用 | `http://1.14.202.161:8998/mcp` 是明文出境链路 | 把 GitHub 变量 `QCC_MCP_BASE_URL` 设为 **HTTPS** 端点（如官方 `https://agent.qcc.com/mcp`）；`bootstrap-env.sh` 会据此自动把 `QCC_ENABLED` 置 true。不设则等于**明确接受企查查在海外下线** |

**守卫的边界（别用错）**：`qcc_client` 只挡**明文 HTTP**，不挡 HTTPS 出境。
它是「传输加密守卫」，不是「司法辖区守卫」。要真正约束出境目的地，得另加白名单。

---

## 3. 切栈前必须先清掉的两个阻塞（来自 `docs/LIVE-FORENSICS-2026-09-18.md`）

- **C1 变量漂移**：`looma-zervi` 管线用 `--env-file backend/.env` 调用 compose；
  缺 `--env-file` 时 `${DEPLOY_REGION:-US}` 会兜成 `US`，**覆盖** `.env` 里的 `SG`。
  本仓已对齐调用方式并加了插值断言（插值不是 SG 就拒绝重建）。
- **C2 P0 被静默回滚**：`/opt/looma-zervi` 现由 `deploy-overseas.yml` 以
  `rsync -avz --delete` 全树同步，而源仓 compose 仍是 `0.0.0.0` 端口
  ⇒ 下一次 `overseas-*` tag 发布会把「端口收内网」的安全修复**覆盖回公网暴露**。
  **必须先停用 `overseas-*` 的 tag 触发。**

---

## 4. 上线顺序

1. 配齐 §1 的 1–8（密钥进 GitHub secrets，端点/开关进 vars）。
2. 本地干跑：`bash scripts/dryrun.sh --static`（不 SSH、不碰真机）。
3. 手动 dispatch：`dry_run=false` 但 `DEPLOY_ENABLED` 仍为 false → 只验双门禁（deploy 仍 skipped）。
4. 清 §3 的 C2（停用 `overseas-*` 触发）。
5. 打开 `vars.DEPLOY_ENABLED=true`。
6. 打 tag：`git tag stack-vX.Y.Z && git push origin stack-vX.Y.Z`
   （发版纪律：先 push 分支，再单独 push tag，避免 Actions 双记录）。
7. 线上验收：
   - `GET /v1/membership/plans` → 三档 + `billing_entity=YEDALL LIMITED`（**这条曾经 404**，见 §5）
   - 未登录 `POST /v1/membership/subscribe` → 401；登录后 → 拿到 Stripe Checkout URL
   - 走完一笔真实小额订阅 → Stripe Dashboard 出现 Subscription、webhook 返回 200
   - `POST /v1/membership/portal` 能进 Portal，**且真的能取消**
   - `GET /v1/account/export` 能下载 JSON；`DELETE /v1/account` 必须带 `{"confirm":"DELETE"}`
   - 漏斗有数：`pricing_viewed → subscribe_clicked → checkout_redirected → payment_succeeded`

---

## 5. 历史坑（已修，勿回退）

- **会员端点曾双层前缀、线上从未接通**：`membership_bp` 内路由自带 `/membership/`，
  而注册前缀又写了 `/v1/membership` → 实际拼成 `/v1/membership/membership/*`；
  前端 `Subscription.tsx` 调的是 `/v1/membership/plans`，nginx 配的是
  `location /v1/membership/webhook/` —— 两边都对不上。已改为 `url_prefix="/v1"`，
  并有路由契约回归测试锁死（`/v1/membership/plans` 必须 200、双层前缀必须 404）。
- **PR 门禁假绿**：`concurrency` 跨 ref 共用一组，导致并发运行被取消（结论记 `cancelled`），
  看起来「跑过了」实际一条断言都没执行。已改为门禁按 ref 隔离 + 部署全局串行不可取消。

---

## 6. 仍开放、但不阻塞上线

- Dependabot：默认分支 65 个漏洞（6 critical / 27 high / 31 moderate / 1 low）。
- 续费 / 取消 webhook 靠 `subscription_data[metadata]` 留痕定位内部订单；
  **留痕功能上线前开出的存量订阅没有该 metadata**，续费可能定位不到。
- 腾讯 `1.14.202.161:8998` QCC 网关退役（本仓 `open_items.json` 里的 P2 项）。
