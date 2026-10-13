# 预发演练方案：PR #18 冒烟与回滚的真机验证

> ## ⚠️ 当前状态：**暂缓执行**（2026-10-13 更新）
>
> `stack-v0.1.5` 已于 2026-10-13 发布成功（CI 三 job 全绿，线上 `/health`
> `git_commit = e4e7227`）。**但发布成功 ≠ 回滚可用**：`scripts/rollback-release.sh`
> 与四条业务断言只在部署**失败**时才执行，v0.1.5 全程未触发 —— **回滚路径仍是零次真机执行**。
> 故本文不作废、不关闭，作为**未偿债务**保留，待有预发机后按 A–H 阶段执行。
>
> **v0.1.5 顺带回答的**：
> - 第 1 问（断言不误报）：已验证 ✅ —— 生产 endpoint 总数 **183** ≥ 阈值 `SMOKE_MIN_ENDPOINTS=150`，
>   模块含 `membership` / `account`，两条断言通过，未触发误回滚。（阈值余量仅 33 条，
>   若日后整块蓝图下线需同步下调阈值。）
> - 第 2 / 3 问：**已验证**（见下方演练结果）
> - 第 4 问：**已验证** —— 坏进程上两份脚本结论相反
> - 第 5 问：**已验证，但暴露设计缺陷** —— 分支选择正确，救不回服务（见 §8.7）
> - 第 6 问：**已验证** —— 纯代码不重建则标记不生效，步骤 7 确有必要
> - 第 6 问（`--force-recreate` 对照实验）：**已验证** ✅
>
> **预发演练结果（2026-10-13，win 侧实操；未经第三方复核，代码层面事实已本地核对）**：
> - 第 2 / 3 问：**已验证** ✅ —— 摘掉 membership 注册后健康检查退出码 1（真失败），
>   回滚确实换掉了 backend 进程，`/health.git_commit` = `rolled-back:staging-r2`。
> - 第 4 问：复检确实用了 `releases/staging-r3/scripts/healthcheck.sh` ✅；但 r3 与回滚
>   目标 r2 的脚本**同版本**，故「软链翻到旧脚本」的对照**尚未做出**（需 staging-r1）。
> - 第 1 问：预发侧再证一次 ✅（staging-r2 11 项全绿）。
> - 第 5 / 6 问：仍未做 ❓
> - **新发现**：路由总数断言对「只摘掉 membership」这类故障**无区分度** —— 详见 §8。
>
> **原定适用窗口（已过）**：`PR #18`（merge commit `e4e72279`）合入 `main` 之后、
> 首个 `stack-v*` 发布之前。
>
> **核心口径：合入 `main` ≠ 验证过。** PR #18 给部署加了四条业务断言与分层回滚，
> 但截至本文撰写，`scripts/rollback-release.sh` 与新增断言**从未在真机运行过一次**。
> 若直接打 `stack-v*`，那次发布就是它们的首次真机执行，失败代价由生产承担。
> 本文的目的：把首次执行搬到预发机，验证通过后再上生产。
>
> 机器地址不写入本仓（本仓为公开仓），以 `<STAGING_HOST>` 占位。

---

## 0. 这次演练要回答的六个问题

| # | 问题 | 阶段 | 不验证的后果 |
|---|---|---|---|
| 1 | 四条业务断言在真实服务上是否全绿（**不误报**） | D | 误报即误回滚，每次发布都可能自我回滚 |
| 2 | 断言失败时是否真的触发回滚 | E | 门禁形同虚设 |
| 3 | 回滚后**进程**是否真的换了（而非只换了文件） | E | 文件回滚、进程仍跑坏版本，服务依旧是坏的 |
| 4 | 复检用的是本次发布带去的脚本，而非软链翻回的旧脚本 | E | 用旧标准自我通过 |
| 5 | `/health` 死掉时走"恢复 compose"分支，而非代码回滚分支 | F | 该分支从未执行过，可能根本不工作 |
| 6 | 步骤 7 的 `--force-recreate` 是否确有必要的（对照实验） | G | 若没必要，纯代码发布本可不重建；若有必要而删了，发布停在旧 sha |

---

## 1. 红线（全程不变，任何阶段不得越过）

| # | 红线 | 理由 |
|---|---|---|
| 1 | **不打 `stack-v*` tag** | 那是生产 `deploy` 的唯一触发条件 |
| 2 | release 目录统一命名 `staging-r1`…`staging-r4` | 从命名上杜绝误 push 触发生产 |
| 3 | **不 push 任何东西到远端** | 预发机上的改动只留在预发机 |
| 4 | 不碰生产机、不碰生产数据 | 预发 `.env` 用最小本地集（`PAYMENT_STUB_MODE=true`，本地 DB），不接 Stripe / Supabase 生产凭据 |
| 5 | 端口只绑 `127.0.0.1:5200` | compose 现状即如此；预发会被故意弄坏，不得对外可见 |
| 6 | **不在预发机上修改仓内脚本** | 发现缺陷 → 回本机开分支提 PR；否则"预发绿了、生产那份还是旧的" |

---

## 2. 环境：预发与生产的差异

| 项 | 生产 | 预发 | 影响 |
|---|---|---|---|
| backend 端口 | `127.0.0.1:5200`（宿主 nginx 反代） | 同 | 无 |
| 宿主 nginx | 有，`/etc/nginx/nginx.conf` ← 本仓 `nginx/nginx.conf` | 装，证书用**自签** | `healthcheck.sh` 第 1 条断言（`:80` + `Host: api.genz.ltd`）需 nginx |
| 域名 / CF | `api.genz.ltd` 经 Cloudflare | 无域名，仅 `127.0.0.1` | 公网侧冒烟（workflow 中 `curl https://api.genz.ltd/...`）**不在预发验证** |
| 支付 | 真实 Stripe | `PAYMENT_STUB_MODE=true` | `/v1/membership/plans` 不需要真 key |
| 数据库 | 生产库 | 本地（`DATABASE_PATH`） | 演练不碰生产数据 |
| 镜像 | 已存在（部署用 `--no-build`） | 首次需 `build` | 见阶段 C |

目录：

```
/opt/looma-zervi            DEPLOY_PATH（运行态：backend/、docker/、data/）
/opt/vultr-genzltd-stack    STACK_DIR（releases/、current、CURRENT_RELEASE、backups/）
/opt/src/Vultr-Genzltd      clone 出来的本仓（rsync 源，不 --delete）
```

---

## 3. 阶段 A–H

### A 摸底（只读）

OS / 内存 / 磁盘 / `docker`、`nginx`、`rsync`、`git`、`openssl` 是否已有 / `/opt` 现状。

**验收**：内存 ≥ 2GB（chromadb 与 backend 并存）；否则停下请示（见 §5）。

### B 环境准备

```bash
apt-get update && apt-get install -y docker.io docker-compose-plugin nginx rsync git openssl
mkdir -p /opt/looma-zervi/{backend,docker,data} /opt/vultr-genzltd-stack/{releases,backups,scripts}
git clone https://github.com/GenzLTD/Vultr-Genzltd.git /opt/src/Vultr-Genzltd   # 本仓 PUBLIC，无需 deploy key
```

- **nginx + 自签证书**：证书路径以 `nginx/nginx.conf` 中 `ssl_certificate` / `ssl_certificate_key` 声明为准（A 阶段确认），用 `openssl req -x509` 自签一份放进去，使 `nginx -t` 能通过。
- **`.env` 最小集**：以 `backend/.env.example` 为模板，设 `PAYMENT_STUB_MODE=true`、本地 `DATABASE_PATH`、随机 `JWT_SECRET`、`RATE_LIMIT_STORAGE_URI=redis://redis:6379/0`、`CHROMA_MODE` + `CHROMA_HOST=chromadb`、`FLASK_PORT=5200`。缺什么以实测补。

**验收**：`nginx -t` 通过；`docker ps` 可执行。

### C 首次构建镜像

生产部署是 `--no-build`，即镜像必须**事先存在**。预发是空机，必须先构建一次：

```bash
cd /opt/looma-zervi/docker && docker compose build backend
```

**验收**：`docker images` 中有 backend 镜像；此后 `--no-build` 可用。

### D 基线部署 R1、R2（手工复现 workflow 步骤 2→7）

对 `TAG=staging-r1`（代码 `stack-v0.1.4`，生产当前版本）与 `staging-r2`（`main` @ `e4e72279`）各执行一次：

```bash
REL=$STACK_DIR/releases/$TAG
mkdir -p "$REL" && rsync -a --exclude='.git' /opt/src/Vultr-Genzltd/ "$REL/"   # 排除项以 deploy.yml 步骤 3 为准
ln -sfn "$REL" "$STACK_DIR/current"
echo "$TAG <sha> $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STACK_DIR/CURRENT_RELEASE"
cp "$DEPLOY_PATH/docker/docker-compose.yml" "$STACK_DIR/backups/docker-compose.yml.$(date +%Y%m%d-%H%M%S)"
rsync -a "$REL/compose/docker-compose.yml" "$DEPLOY_PATH/docker/docker-compose.yml"
rsync -a "$REL/backend/" "$DEPLOY_PATH/backend/"                 # 排除 .env
echo "<sha>" > "$DEPLOY_PATH/backend/git_commit.txt"             # 必须在容器启动前
cd "$DEPLOY_PATH/docker" && docker compose up -d --force-recreate --no-deps --no-build backend
bash "$STACK_DIR/current/scripts/healthcheck.sh"
```

**验收**：两次 `healthcheck.sh` 全绿（8 条前置 + 4 条业务断言）；`/health.git_commit` = 对应 sha。

**附带验证（R1 之后立刻做）**：此时还没有"上一个 release"，执行一次回滚 —— 期望**明确报错并拒绝动作**，而不是回滚到不存在的目标或误改 `CURRENT_RELEASE`。

### E 主演练：坏版本 → 回滚

1. 造 `staging-r3` = `staging-r2` + 注释掉 `app.py` 中 membership 蓝图注册
   （复现历史上 `rsync --delete` 用旧 `app.py` 覆盖、业务静默消失的事故）
2. 按 D 的流程部署 R3 → `healthcheck.sh` 应失败：`/v1/membership/plans` 404、`url_map` 缺 membership
3. 触发回滚（复现 workflow `if: failure()` 分支）：

```bash
curl -sf -m 5 http://127.0.0.1:5200/health && bash "$STACK_DIR/current/scripts/rollback-release.sh" --apply
bash "$STACK_DIR/releases/staging-r3/scripts/healthcheck.sh"    # 必须用本次带去的脚本复检
```

**五个验收点（缺一不可）**：

| # | 验收点 | 怎么验 |
|---|---|---|
| 1 | `/health.git_commit` = `rolled-back:<回滚落地到的那份 release>`（实测 `rolled-back:staging-r2`） | 证明**进程**换了（`lru_cache` 已空）。**更正**：标记是回滚**后**跑的那一份（r2），不是失败的那一份（r3）——脚本语义正确，运维一眼即知当前处于哪个版本的回滚态。本文初版误写为 `staging-r3` |
| 2 | 复检脚本 = `releases/staging-r3/scripts/healthcheck.sh` | 日志中确认路径，不是 `current` 软链 |
| 3 | 服务恢复：`/v1/endpoints` 含 membership + account，`/v1/membership/plans` 200 | 业务真的回来了 |
| 4 | `looma-redis` / `looma-chromadb` **未被重建** | `docker ps` 的 Up 时间未变（`--no-deps` 生效） |
| 5 | compose 未被回滚，`docker ps` 仍 `127.0.0.1:5200`，无 `0.0.0.0:5200` | 未被旧 compose 暴露端口 |

### F `/health` 死掉的分支

造 R4：让 gunicorn 起不来（如 `app.py` 语法错误）。部署后 `/health` 不可达，
复现 workflow 中 `curl 127.0.0.1:5200/health` 失败的那一路 —— 应走**恢复 compose**（`backups/docker-compose.yml.*`），
而不是代码回滚。

**验收**：脚本输出表明走的是 compose 恢复分支；恢复后容器能起。

> 已知待改进点：这段"活则回滚代码、死则恢复 compose"的分支判断目前**内联在 `deploy.yml`**，
> 不在 `rollback-release.sh` 里。预发只能手工复现该判断，无法直接调用脚本验证。
> 若演练确认其有效，值得另开议题把它抽到脚本里（届时预发可直接测）。

### G 步骤 7 的对照实验

在 R2 基础上做一个**纯 Python 改动**（不动 `requirements.txt` / `Dockerfile`），做成 `staging-r4b`：

1. 先按**旧行为**部署（`up -d`，不带 `--force-recreate`）→ 观察 `/health.git_commit` 是否仍显示 R2 的 sha
2. 再按 PR #18 的行为部署（带 `--force-recreate`）→ `git_commit` 应更新为本次 sha

**验收**：第 1 步若是旧 sha，即实证步骤 7 的 `--force-recreate` 确有必要（纯代码发布否则不生效）。

### H 收尾

- 记录：六个问题各自的结果（通过 / 不符 / 未覆盖）
- 发现脚本缺陷 → **回本机开分支提 PR**，不在预发机上热改
- 预发机保留作长期预发场（见 §7）

---

## 4. 中断条件（出现即停下请示，不自行推进）

| 情况 | 为什么停 |
|---|---|
| 内存 < 2GB 且 chromadb 起不来 | 需决策：裁 chromadb（改验证范围）还是升配 |
| `compose build` 拉不动依赖 | 需决策：换源 / 精简依赖 |
| `nginx -t` 因证书或路径失败且自签无法解决 | 需决策：完整复现 vs 接受第 1 条断言在预发恒失败 |
| 任何脚本行为与 PR #18 设计不符 | 这是**演练的产出**，应回本机开 PR，不该在预发绕过 |
| 出现"必须改仓内脚本才能继续" | 同上 |

---

## 5. 演练自身失败如何恢复

预发可推平重建，代价为零：`docker compose down` → `rm -rf /opt/looma-zervi` → 从阶段 B 重来。
**这正是不在生产上做的原因**：预发炸了不心疼，生产炸了是真实中断。

---

## 6. 演练后：预发机转为长期预发场

保留 `/opt/src` 与 `releases/`。此后每次 `stack-v*` 之前，在预发机上先跑 D + E 的最小集：
部署目标版本 → 冒烟 → 通过才打 tag。必要时可另开议题把预发纳入 CI
（`workflow_dispatch` 增加 staging 目标），使预发与生产共用同一份编排。

---

## 7. 未覆盖范围（明确边界，勿据此认为已验证）

- **不做**真实支付（stub 模式），不验证 Stripe 链路
- **不验证**公网侧冒烟（`https://api.genz.ltd/...`、tspace/app 登录注册）—— 预发无域名、在 CF 之外
- **不验证**前端 `rsync --delete`（workflow 步骤 5）与前端产物
- **不验证 workflow 编排本身**：预发是手工复现步骤 2→7；编排正确性靠 code review，不靠本次演练
- **不覆盖**"回滚成功但服务仍坏"这类双重故障的组合场景

---

## 8. 演练结果记录（2026-10-13，win 侧实操）

### 8.1 已验证

| 项 | 结果 |
|---|---|
| staging-r2（`e4e72279`）健康检查 | 11 项全绿 |
| staging-r3（只注释 `app.register_blueprint(membership_bp, url_prefix="/v1")`） | `/health` **仍 200**，健康检查**退出码 1**；失败两条：`/v1/membership/plans` 不应答、`url_map` 无 membership |
| 回滚 | `rollback-release.sh --apply`，backend 容器 id 变更（**进程真换了**），`/health.git_commit` = `rolled-back:staging-r2` |
| 复检 | 用 `releases/staging-r3/scripts/healthcheck.sh`，11 项转绿 |
| redis / chromadb | 容器 id 与启动时间均未变（`--no-deps` 生效） |
| 端口 | 仍 `127.0.0.1:5200`，compose 未被回滚 |

### 8.2 新发现：路由总数断言对模块级故障无区分度

- membership 蓝图**仅 5 个端点**（`backend/src/api/routes/membership_routes.py` 实测）；account 2 个
- 摘掉整块 membership：183 → 178，仍 ≥ `SMOKE_MIN_ENDPOINTS=150`
  **（178 为按 5 条推算，未在坏进程上实测总数）**；坏进程上该断言**再次通过**，
  确认对「只摘掉 membership」这类故障无区分度
- 即：**该断言的设计意图（「整块蓝图缺失时总数下降」）在 membership 这种规模下根本不触发**
- 真正抓到故障的是第 2 条（模块名存在性），总数阈值目前形同**冗余**
- 建议：改为**相对阈值**（如「较上一 release 下降超过 2%」），或明确写清「总数阈值只防大规模缺失，模块级缺失靠模块名断言」。**不要保留「有总数保护」的错觉**

### 8.3 `/health` 仍 200 的意义

坏版本下 `/health` 返回 200 —— 若无 PR #18 的四条业务断言，这次会被判「发布成功」。**PR #18 存在的理由已被实证。**

### 8.4 剩余项：已全部完成（2026-10-13）

三项均已完成，结果见 §8.6。

1. **第 4 问对照（staging-r1）**：**对着还在跑的坏进程做，不要在回滚成功之后做**。
   服务已回到好版本时旧脚本变绿是正常的，证明不了它会放过坏版本。正确做法：
   部署坏版本（如摘掉 membership 注册，此时 `/health` **仍返回 200**、服务仍是坏的），
   在同一状态下分别跑两份脚本：
   - `staging-r1`（`stack-v0.1.4`）的 `healthcheck.sh`（无业务断言）→ **应当退出 0**（放过坏版本）
   - `e4e72279` 那份（有四条业务断言）→ **应当退出 1**（抓住）

   两者结论相反，才是「复检必须用本次发布带去的脚本」的实证。
2. **第 5 问**：`/health` 起不来时是否走「恢复 compose」分支 —— 唯一完全没走过的分支。
3. **第 6 问**：不带 `--force-recreate` 的纯代码对照 —— 已有半证（v0.1.5 生产 `git_commit` 已更新；本次回滚进程确实换了），优先级最低。

### 8.5 数据来源与限制

本节结论来自 win 侧实操记录，**未经第三方复核**。代码层面事实（membership 5 端点、`rolled-back` 标记语义）已在本仓 `e4e72279` 本地核对；容器 id 变化、健康检查输出等运行时事实以操作者自报为准。


---

## 8.6 第 4 / 5 / 6 问演练结果（2026-10-13 同日，win 侧）

### 第 4 问：成立

坏进程始终是同一个容器 `3a334fdc`，`/health` 为 200、`/v1/membership/plans` 为 404；
**两份脚本之间没有回滚**（在同一坏状态下对比）。

| 脚本 | 退出码 | 结果 |
|---|---|---|
| `releases/staging-r1/scripts/healthcheck.sh`（`stack-v0.1.4`，无业务断言） | **0** | 七项全绿 |
| `releases/staging-r2/scripts/healthcheck.sh`（`e4e72279`，四条业务断言） | **1** | plans 与模块名失败 |

同一坏状态下**结论相反** → 复检若跟着 `current` 软链走到旧脚本，这次会被判成**发布成功**。
PR #18「复检不跟软链走」的设计得到实证。

### 第 5 问：分支选择正确，但救不回服务

`app.py` 加语法错误后 `/health` 不可达，未调用 `rollback-release.sh`，走的是 compose 备份恢复；
备份里没有 `0.0.0.0:5200`。恢复之后容器状态 `restarting`，`/health` 仍然是死的。
**坏代码还在磁盘上，换回 compose 不会让 gunicorn 起来**；
把 `staging-r2` 的代码重新放回并 `--force-recreate` 之后服务才恢复。

> 这条分支能救的是 **compose 被改坏**，救不了 **代码起不来**。详见 §8.7。

### 第 6 问：成立

只改 `git_commit.txt` 为 `q6-norecreate` 后 `up -d --no-build`：容器 id 仍 `69b5f3ca`，
`/health` 仍 `e4e72279`；再加上 `--force-recreate`：容器换成 `a9934af2`，`/health` 变成 `q6-norecreate`。

→ 纯代码发布不重建进程，新标记不会生效。**步骤 7 的 `--force-recreate` 确有必要。**
收尾时已写回 `e4e72279` 并重建，最终健康检查通过。

---

## 8.7 第 5 问暴露的设计缺陷（脚本修复另开 PR，不进本文档范围）

`/health` 不可达**不能区分**两种故障：

| 故障 | 换回 compose 是否有效 |
|---|---|
| compose 配置被改坏 | **有效** |
| 代码起不来（如语法错误） | **无效** —— 坏代码仍在磁盘上 |

而 workflow 当前正是用「`/health` 是否可达」来选分支：死 → 恢复 compose；活但冒烟失败 → 回滚代码。
结果是：**代码起不来时被判到「恢复 compose」分支，救不了**。

建议方向（不在本次范围，需另开 PR 改脚本）：

1. 恢复 compose 之后再判一次，仍死则继续回滚代码（两段式）；或
2. 按「本次发布是否改动了 compose 文件」选分支，而非按 `/health` 死活。
