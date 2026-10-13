# 海外部署拓扑（genz.ltd 族谱）与回滚真源

> 适用：`genz.ltd` 族谱的**海外**成员。与 [`CATALOG.md`](CATALOG.md) 分工：
> `CATALOG.md` 只管 SG 本机（容器、端口、运行时），本表管**跨仓跨平台**的全景。
>
> **核心口径：发布开关各自为政，回滚语义必须统一。** 每个成员都有自己的发布方式
> （这未必是缺陷，见 §2），但出事时的真问题是「退回到 30 分钟前，每个域名分别怎么做、
> 谁来做」——这个问题跨域名，且此前没人能答。本表先把现状与回滚方式钉成事实。
>
> 边界：境内机（腾讯云、天翼云）不进本表，依
> [`docs/looma-overseas/README.md`](looma-overseas/README.md) 的约定——境内两种物种
> 塞进海外册是语义污染。
>
> 采集时间 2026-10-13。**标「待核实」的项未经实证，动手前先核。**
>
> **当前状态（2026-10-13）：本表为事实记录，未授权据此动手。** `circle` 维持关闭、
> 不杀进程；不跳到 P2 去改生产编排。

---

## 1. 拓扑真源表

| 域名 | 服务 | 代码真源 | 平台 / CI | 触发条件 | 部署目标 | **回滚方式** | 现状 |
|---|---|---|---|---|---|---|---|
| `api.genz.ltd` | backend (Flask :5200) | 本仓 `Vultr-Genzltd` `backend/` | 本仓 `deploy.yml` | `stack-v*` tag（且 `DEPLOY_ENABLED=true`） | SG `/opt/looma-zervi` | `scripts/rollback-release.sh --apply`；`/health` 死则恢复 compose 备份 | `stack-v0.1.5` = `e4e72279`（2026-10-13） |
| `tspace.genz.ltd` | saas 前端 | 本仓 `frontend/`（`SOURCE.json` 声明海外 tspace 在本仓维护） | 同 `deploy.yml` 步骤 5 | 同 `stack-v*` | SG `/var/www/saas/dist` | **无独立回滚**：随后端 release 一起发布，但 `rollback-release.sh` 只 rsync `backend/`，不含前端 | 同 `stack-v0.1.5` |
| `app.genz.ltd` | planet-x | `looma-zervi` → Vercel | Vercel（team `team_7yn...`） | Vercel 侧 git push 自动部署 | Vercel 边缘 | Vercel Instant Rollback（与本仓**无联动**） | 构建源停 `d8f4c8d2`（2026-08-17），与后端差约 55 天 |
| `circle.genz.ltd` | kernel | — | **无** | **无** | SG `:5211` 裸 uvicorn（不在 compose） | **无回滚概念**（根本没有发布） | 公网 404，nginx include 仍注释，进程仍在跑 |
| `genz.ltd` | genz-web | `GenzLTD/genz-web` | Vercel | Vercel git 集成 | Vercel 边缘 | Vercel 回滚 | 部署时间未提供 |
| `www.genz.ltd` | Genzer-Terminal | `GenzLTD/Genzer-Terminal` | Vercel | Vercel git 集成 | Vercel 边缘 | Vercel 回滚 | 部署时间未提供 |

证书：`CN=genz.ltd`、`SAN=genz.ltd,*.genz.ltd`，有效期至 2036-07-11（通配覆盖 `app` / `circle`）。

---

## 2. 刻意边界：这些「各自为政」是有意为之，不应收敛

| 边界 | 依据 | 为什么不该收敛 |
|---|---|---|
| 本仓 vs `looma-zervi` | `looma-overseas/README.md`：本仓 = 海外运行时 + 海外部署真源；`looma-zervi` = 境内运行时；**对齐只走 GFCC** | 收敛会让海外 UX 改动被境内 PR 卡住 |
| `PlanetX` / `genz-web` / miniprogram | `frontend/SOURCE.json` 原话："out of this runtime. Do not wait for looma-zervi PRs before changing overseas UX" | 明确划出本运行时，属架构决策 |
| 境内机不进本表 | `looma-overseas/README.md` 边界约定 | 语义污染 |

**结论**：族谱成员各有发布机制本身不是缺陷。要治理的是 §3 那几处**隔离了但没有闭环**的缺口。

---

## 3. 失控缺口：隔离了，但没闭环

| # | 缺口 | 症状 | 为什么算失控 |
|---|---|---|---|
| 1 | `tspace` 无独立回滚 | 回滚后端 release 时前端**不会跟着回退** | 前后端不兼容时，回滚后端后前端仍是新版，故障不解除 |
| 2 | `app.genz.ltd` | 划出本运行时 55 天未更新，却仍在生产服务 | 隔离了、没人维护，也没有「已冻结」的声明；漂移目前靠 `contract-gate` 发现（只覆盖「后端删了前端在用的」一个方向） |
| 3 | `circle.genz.ltd` | 裸 uvicorn 不在 compose、无 CI、公网 404，进程还活着 | **无归属**：既没上线也没收掉。「维持关闭」应是可验证的状态 |
| 4 | `looma-zervi` 双远端 | `GenzLTD/` 与 `szpeter2026/` 两个 fork 都在 | 双真源；`deploy-overseas.yml` 的反向通道即由此滋生（已删除） |
| 5 | 回滚语义不统一 | api 有脚本（未真机验证）、app 靠 Vercel、circle 无 | 出事时「每个域名怎么退」无人能答 |

---

## 4. 优化路线

| 级 | 内容 | 风险 | 前置 | 建议时机 |
|---|---|---|---|---|
| **P0** | ① 维护本表（事实层）② `circle` 收尾：**未授权，暂不执行** —— 当前口径「维持关闭、不杀进程」 | 零 / 需授权（涉及现网进程） | 无 | **待授权** |
| **P1** | ① `tspace` 回滚纳入 `rollback-release.sh`（或明确「前端不单独回滚」并记录理由）② 定性 `app` 是**冻结**还是**收编**；冻结需在文档与前端可见处声明 ③ 收敛 `looma-zervi` 双远端 | 低 | 预发演练走通（PR #19） | 演练后 |
| **P2** | ① 预发纳入 CI（`workflow_dispatch` 增加 staging 目标）② 统一发布编排（一个 `stack-v*` 发布后端 + 前端，可选触发 app hook） | 中：动真实收款的生产编排（`PAYMENT_STUB_MODE=false`） | 预发长期可用 | 预发跑通后 |
| **P3** | `app` 收编进主仓、境内仓治理 | 高 | — | 架构议题，已搁置 |

**不推荐跳到 P2**：生产正在真实收款，且预发尚未验证。没有安全网就改编排，等于把风险直接压在收款链路上。

---

## 5. P0 的两项具体动作（批准后执行）

### 5.1 `circle` 收尾

现状已部分符合「关闭」：公网 404、nginx include 注释、本机 hosts 灰度行已于 2026-10-12 删除。
**唯一残留**：SG 机上 `:5211` 的裸 uvicorn 进程仍在跑。

> **当前口径（2026-10-13）：维持关闭、不杀进程。** 本项未获授权，不执行。

> 注意：动现网进程需**单独授权**。此前口径为「circle 维持关闭，不要动现网的 uvicorn」，
> 故本项在获得明确授权前不执行。执行时动作仅为止进程（不删代码、不改 nginx）。

### 5.2 本表维护约定

- 任何成员的代码真源、CI、触发条件或回滚方式变更 → 同步更新本表，与变更同一 PR
- 新增域名接入 `genz.ltd` 族谱 → 必须先在表中补全「回滚方式」一列，否则视为未接入
- 标「待核实」的项（`genz.ltd`、`www.genz.ltd`）由知情人补齐，不臆测填写

---

## 6. 待核实（不臆造）

| 项 | 需要什么 |
|---|---|
| `genz.ltd` / `www.genz.ltd` 的代码仓、平台、触发、回滚 | 本机无这两个仓，需提供远端地址或授权查询 |
| `app.genz.ltd` 是否仍在被用户使用 | 决定「冻结」还是「收编」的前提；若无人使用，冻结声明即可 |
