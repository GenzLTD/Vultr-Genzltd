# looma-overseas

境内同事用来对号的**境内外区别归集**。薄册，不是第三套运行时，也不是 `looma-zervi` 的又一条分支。

| 名字 | 是什么 | 不是什么 |
|---|---|---|
| **looma-overseas** | 境内运行时 ↔ 海外运行时：哪里分叉、哪里必须同号 | 不是再 clone 的 backend |
| **Vultr-Genzltd** | 海外运行时 + 海外部署真源 | 不是 looma 的冻结钉 |
| **looma-zervi** | 境内运行时（远端 **10** 个 `heads`、**68** 个 tag，2026-09-19 `ls-remote` 实测；tag 几乎全是 `overseas-v*`；`release/overseas` 仍在远端、已硬停） | 不是海外发版入口 |
| **GenzLTD/gfcc** | 唯一协议真源 | 不是某一边的实现 |

对齐只走 GFCC。海外改动不推进 `looma-zervi`。

---

## 边界（这本册不管什么）

| 账本 | 管什么 | 放哪 |
|---|---|---|
| **本册** | 境内产品运行时 vs 海外产品运行时 | `docs/looma-overseas/` |
| **本仓 vs 海外现网** | Vultr 机 `/opt/looma-zervi` 还没收到仓内期望态 | [`../DIFF-vs-live.md`](../DIFF-vs-live.md) |
| **境内机 vs 境内机** | 腾讯云 `1.14.202.161` vs 天翼云 `14.29.216.219`（compose 孤本、明文密钥、端口裸奔、CHROMA remote/local……） | **不进本册**。等境内仓（szbolent-cn 式）立起来后放那边 |

名字叫 overseas，就只管境内外。境内已经漂成两种物种，是境内仓要收敛的账，塞进这里是语义污染。

本册出现腾讯 / 天翼，**只当取样**：说明「境内现状还没达到海外已经钉住的形态」。不在这里拍板那台机算几个域、circle/demoppi 进不进境内盘子。

---

## 同号规则（每条必须挂钉）

「要同号」不能只写一行字。海外的钉在本仓；境内的钉在 `looma-zervi`。没钉的标 **待补**，叙述会腐烂。

| # | 规则 | 同号？ | 钉（仓 · 测试 / 脚本） | 钉状态 |
|---|---|---|---|---|
| P1 | GFCC 字段 / 枚举 / `$ref` / 家族版本 | **要**。变了升 Semver，两边各自改实现 | 本仓 `tools/validate_contracts.py` + `scripts/assert-contracts.sh` + `TestGfccIsUniqueProtocolSource.test_gfcc_source_is_the_authority`（`authority=GenzLTD/gfcc`，`unique_protocol_source=true`） | 有钉 |
| P2 | 禁止把 GFCC 字段改成「海外专用名字」 | **要**（改名 = 拆协议） | 无独立「禁止改名」断言；目前只钉版本一致与 `$ref` 可解析 | **无钉，待补** |
| P3 | 契约入口在册的 HTTP（如 `POST /v1/ask`） | **要** | SOURCE.json `kernel.entry`；无路由实测钉 | **无钉，待补** |
| P4 | 微信收款海外不可用 | 分叉（海外 403 / stub） | 本仓 `backend/tests/test_overseas_billing_gate.py` · `TestWechatRegionGate` | 有钉（产品行为） |
| P5 | Stripe 回调意图 = tspace，密钥只 `seed_kv`、禁止 `set_kv` | 分叉（海外 Stripe；境内微信）。**密钥纪律两边同号** | 本仓 `TestStripeHostIntent`（×3）；境内 `looma-zervi` #19 + `TestOverseasWorkflowContract`（守 `deploy-overseas.yml`） | 有钉（各守各的 yml） |
| P6 | 收银台回调用 `window.location.origin` | 海外运行时要 | 本仓 `TestPricingReturnUrlSource` | 有钉 |
| P7 | `git_commit.txt` 写在任何 `compose up` 之前 | **要**（形态同号，文件不同） | 本仓 `TestDeployOrder`（`deploy.yml`）；境内 `test_overseas_billing_gate.py::TestOverseasWorkflowContract::test_git_commit_marker_is_written_before_compose_up` | 有钉 |
| P8 | 宿主只发布 `127.0.0.1:5200`；chroma/redis 不发布 | **要**（海外仓已钉；境内两机尚未对齐） | 本仓 `scripts/dryrun.sh` 第 5 步 | 有钉（**仓内期望态**；海外现网未应用，见下表） |
| P9 | compose 入 git、真值不入库；非密钥 `set_kv`、密钥 `seed_kv` | **要** | 本仓 `bootstrap-env.sh` + P5；dryrun 用 `.env.example` 桩 | 有钉（海外仓）。境内两机取样见下表，**收敛方案不在本册** |
| P10 | 发版管线不合成一条 | 分叉 | 无「禁止引用 deploy-overseas.yml」的 CI 钉；纪律靠本册 + 不向 looma 开海外 PR | **无钉，待补** |
| P11 | JWT `iss` / 品牌包名 | 分叉（白标待做） | 无钉 | **无钉，待补** |

CI 覆盖：`backend-test` 先 `assert-contracts.sh`（P1）再 `dryrun.sh --static`（P5–P9），再 `backend/tests`（P4）。

---

## 分叉表（境内外）

| 面 | 境内运行时 `looma-zervi` | 海外本仓 | 规则 |
|---|---|---|---|
| 协议 | 按 GFCC 适配 | `contracts/gfcc/` 钉 Ask **1.2.0** / 信号 **1.0.0** | P1 P2 |
| HTTP 产品面 | 微信 / 华为 / 小程序 / PlanetX | `api.genz.ltd` + `tspace.genz.ltd`，同源 `/v1` | P3 P4 |
| 支付 | 微信，CNY | Stripe，USD | P5 P6 |
| 身份会话 | `iss=looma`，`looma_token` | 邮箱 + Google；海外不读 PlanetX `looma_token` | P11 |
| Host | 备案域；circle 现挂天翼是**现网事实**，不是本册要境内拷贝的法 | 营销站 Vercel；api / tspace → Vultr；circle 片段在仓、未进现行 nginx | 分叉。不拷现网 |
| 发版 | `deploy-overseas.yml`，`overseas-*` | `deploy.yml` 双门禁 → `stack-v*`；`DEPLOY_ENABLED` 仍关 | P7 P10 |
| 品牌 / 包名 | `@looma/saas` 在 looma 单仓 | workspace 已是 `vultr-genzltd-tspace`，包名仍 `@looma/*` | P11 |
| 真机路径 | 境内两台机路径不同（不在此展开） | 仓内期望 `STACK_DIR=/opt/vultr-genzltd-stack`；Vultr 现网目录名仍是历史 | 旧通道停掉之前不改现网卷名 |

---

## 部署形态：海外已钉 vs 境内取样 vs 海外现网

代码版本可以相同，形态仍是分叉的真身。Mac 实勘（2026-09-19）：腾讯 / 天翼 `/health` 的 `git_commit` 均为 looma `21d908d`（`origin/main` 已核）。**Vultr 现网不是这枚**：2026-09-19 Win SSH `git_commit.txt` = `a52638e`。

「同一套产品拓扑」（nginx + PlanetX `/` + T-space + backend/redis/chroma）是历史同构，不是必须保持的法。海外仓已经按管辖拆 Host；境内怎么拆域，进境内仓。

| 形态 | Vultr-Genzltd **仓 / dryrun** | Vultr **现网** `139.180.184.25` | 腾讯云取样 `1.14.202.161` | 天翼云取样 `14.29.216.219` |
|---|---|---|---|---|
| 端口 | 只发 `127.0.0.1:5200`（dryrun 第 5 步钉死） | 仍 `0.0.0.0:5200/8000/6379`（2026-09-19 实测） | 三端口公网裸奔 + redis 无密码 | backend `127.0.0.1:5203`，chroma/redis 不发布 |
| 密钥 | compose 无真值；`seed_kv` / `set_kv`（P5 P9） | 历史 `.env`；旧 `overseas-*` 仍可能 `set_kv` 打回 | CI 生成 `.env`，12 键最小集 | 50+ 键内联进机上孤本 compose，含密钥明文 |
| compose 真源 | 本仓 `compose/docker-compose.yml` | 仍吃 `/opt/looma-zervi/docker/…` | 仓内标准 `docker/docker-compose.yml` | 机上孤本 `docker-compose.tianyi.full.yml`，不在 git |
| 代码投递 | 期望：本仓 rsync → `STACK_DIR`；镜像 hash 决定是否 build | 旧通道 rsync + bind mount；`DEPLOY_ENABLED` 关 | rsync → 镜像内 `build` | rsync → bind mount `--no-build` |
| CHROMA | compose 里 remote 容器，不发布宿主端口 | remote 容器且 **8000 仍公开** | remote | local（容器残留） |

读法：左边两列是海外（仓已对、现网还欠）；右边两列是境内取样，**证明病根在形态不在 SHA**。怎么把腾讯的 env 纪律和天翼的收端口合成境内仓，不在本册写方案。

---

## 禁止

- 把本仓 diff 开回 `looma-zervi`。
- 再开 `looma-zervi` 分支或复活 `release/overseas`。
- 再 clone `GenzLTD/looma-overseas` 当第三份 backend。
- 把 GFCC 字段改成「海外专用名字」。
- 把腾讯 vs 天翼的收敛、混部切仓、circle/demoppi 进哪个盘子写进本册。
- 把 [`../DIFF-vs-live.md`](../DIFF-vs-live.md) 和本册混成一本。

---

## 改完记在哪

1. **协议变了**：改 `contracts/gfcc/` + `SOURCE.json`，两边按新号适配（P1）。
2. **只有海外实现变了**：改本仓；若动到同号规则，先补钉再改叙述。
3. **只有境内实现变了**：改 `looma-zervi` 或未来境内仓；与本册无关，除非碰到 GFCC。
4. **境内两机怎么收**：境内仓的账，开新页，不要 PR 进本文件。

| 日期 | 面 | 记录 |
|---|---|---|
| 2026-09-19 | 治理 | 薄册成立；不建仓、不分树、不复活 `release/overseas` |
| 2026-09-19 | 边界 | 境内内部差异不进本册；Mac 腾讯/天翼实勘只作取样 |
| 2026-09-19 | 钉 | 同号规则 P1–P11；P2/P3/P10/P11 待补 |
| 2026-09-19 | 核数 | heads/tag 修正为 10/68（`ls-remote` 实测；此前 21/70 与本机 33 均为过期 tracking 数） |
