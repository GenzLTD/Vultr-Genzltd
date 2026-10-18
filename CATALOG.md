# 本机服务清单（CATALOG）

> 机器：Vultr Singapore `139.180.184.25`（Ubuntu 22.04 · hostname `genz-ltd`）
> 与 docs 仓《资源-主体-服务对账表》对齐；**本表只管本机**。
> 采集方式：只读 SSH（`docker ps` / `ss -tlnp` / `ufw status` / `md5sum`），采集时间 2026-09-18。

## 一、服务

| # | 服务 | 容器 | 端口 | 主体 | 备注 |
|---|---|---|---|---|---|
| 1 | Looma Backend (Flask) | `looma-backend` | 宿主 `5200` → 容器 5200 | 组织 / 海外 | 源码本地构建 + bind mount |
| 2 | ChromaDB | `looma-chromadb` | ~~宿主 `8000`~~ | 组织 / 实验 | 向量库；backend 经 `looma-net` 访问 |
| 3 | Redis | `looma-redis` | ~~宿主 `6379`~~ | 组织 | 限流 + 缓存；**无 requirepass** |
| 4 | 宿主 nginx | 系统服务 | `80`、`443`（443 公网不可达） | — | 反代 → `127.0.0.1:5200` |
| 5 | SSH | 系统服务 | `22` | — | |

**服务启动来源**：`/opt/looma-zervi/docker/docker-compose.yml`（`docker inspect` 标签实证）。

## 二、运行环境（2026-09-18 只读探明）

### 2.1 平台与运行时

| 项 | 实测值 | 含义 |
|---|---|---|
| 主机 | Vultr **VHP** · Ubuntu 22.04.5 LTS · kernel 5.15.0-185 · hostname `genz-ltd` · region **SG(SGP)** | — |
| Docker | **29.6.1**（client = server）· storage `overlayfs` · cgroup **v2** · root `/var/lib/docker` | 容器化早已成立 |
| Compose | **v5.3.1 插件**；**无**独立 `docker-compose` | 只能用 `docker compose`（连字符版会 not found） |
| 编排归属 | project=`looma-zervi` · cfg=`/opt/looma-zervi/docker/docker-compose.yml` · wd=`/opt/looma-zervi/docker` | 本仓此前的全部假设成立 |
| 磁盘 | `/` 94G，用 24G，**余 67G** | 拉镜像空间充裕 |
| 内存 | 3.9G（可用 3.0G） | 在真机构建偏紧，CI 构建更合适 |
| 磁盘占用 | 镜像 1.93G · **build cache 5.06G（可回收 4.02G）** | build cache = "曾在真机构建"的痕迹 |
| 出口连通 | `ghcr.io/v2/` → **401**（正常鉴权挑战）· `registry-1.docker.io/v2/` → **401** | **镜像仓库化的网络前提成立** |

### 2.2 关键事实：镜像只装依赖，代码靠 bind mount

`Dockerfile.backend` 注释原话「应用代码由 compose volume 挂载，镜像只装依赖」。
实测印证：容器 `Created=2026-09-17T13:27Z`，而镜像 `looma-zervi-backend` **Created=2026-09-03T16:30Z**
——**镜像两周未重建**。

| 类型 | 源 | 目标 | rw |
|---|---|---|---|
| bind | `/opt/looma-zervi/backend` | `/app` | ✅ |
| bind | `/opt/looma-zervi/data/poetry_full` | `/app/poetry_data` | ❌ |
| bind | `/opt/looma-zervi/data/chroma_models` | `/root/.cache/chroma/onnx_models` | ✅ |
| volume | `looma-zervi_backend-data` | `/app/data` | ✅ |
| volume | `looma-zervi_chroma-data` | `/app/chroma_data` | ✅ |

**两个推论**：
1. **P0 无需重建镜像**——端口只在 compose 里，`up -d` 即生效（这也解释了 P0 的 502 只有几秒量级）。
2. **C2（镜像仓库化）不是小改**——它必须删掉 `backend/` 这条 bind mount、把代码 `COPY` 进镜像。

### 2.3 版本锚点现状（脆弱 → 要用 stack-v* 取代）

- `backend/git_commit.txt` = **`a52638e5017de7eb18171ab6af0769aadeb53038`**（root，09-17 13:27）——旧流水线写入，**目前唯一的现网版本锚点**。
- `/opt/looma-zervi/.git` 存在，但是**零 commit 的空仓**：`branch main` 却 `git log` 报
  *"does not have any commits yet"*，所有文件 `??` untracked（`.git` 由 root 于 09-18 04:28 创建）。
  → **git 无法用于版本对账或回滚**。这正是本仓要打 `stack-v*`、把树落到 `/opt/vultr-genzltd-stack/releases/<tag>/` 的原因。
- GFCC 契约钉（仓内，随 tag 上机）：Ask/五端口 **1.3.0**、信号 **1.0.0**，来源 `GenzLTD/gfcc@3dcb0846`。没有这份钉，回滚只能还原文件，不知道协议是哪一版。
- C2 落地后镜像 digest 与 `stack-v*` 并列，取代 `git_commit.txt`。

### 2.4 其他实测

- `/etc/nginx/sites-enabled/` **为空**，nginx **1.18.0** 全靠 `/etc/nginx/nginx.conf` 内嵌 server 块
  → "改 nginx 只需改这一个文件"成立。
- 基线仍精确：**采集当时** `docker-compose.yml` md5 = `8aace57b…`、`nginx.conf` = `0f505e33…`
  → 与 `baseline/` 逐字节一致。**之后**真机 nginx 已按摘块手操换成无裸域块（md5 `fb490978…`）；
  本仓期望态是 `nginx/nginx.conf`，不要把 `baseline/nginx.conf` 当现行配置。
- `Dockerfile.backend` 的已写明坑：`ARG PIP_INDEX_URL` 默认 aliyun，**海外机构建必须覆盖为
  `https://pypi.org/simple`**（注释原话：海外机访问 aliyun 镜像会卡死）。定 C2 构建位置时要用到。

## 三、防火墙（ufw）

| 端口 | 状态 |
|---|---|
| `22/tcp` | ALLOW Anywhere |
| `80/tcp` | ALLOW Anywhere |
| 其余 | 默认 DROP |

### ⚠️ 关键事实：ufw 挡不住 Docker 发布的端口

`DOCKER-USER` 链为空（`iptables -S DOCKER-USER` 仅 `-N`），`/etc/ufw/after.rules` 中
`DOCKER-USER` 出现 **0** 次，且未装 `ufw-docker`。Docker 发布端口走
`nat/PREROUTING → DOCKER` 链 DNAT，**不经过 INPUT**，因此 ufw 的 `-P INPUT DROP` 对其无效。

**实测（2026-09-18，从公网）**：

| 端口 | 发布者 | ufw 是否管辖 | 结果 |
|---|---|---|---|
| 22 / 80 | 宿主 `sshd` / `nginx` | ✅ | 通（预期） |
| **5200** | `docker-proxy` | ❌ | **通**（绕过 nginx 的限流与审计） |
| **6379** | `docker-proxy` | ❌ | **通**（Redis 无认证 → 可读写/清空限流存储） |
| **8000** | `docker-proxy` | ❌ | **通**（ChromaDB 裸露） |
| 443 | 宿主 `nginx`（在 `0.0.0.0:443` 监听中） | ✅ | **filtered**（ufw 未放行 443） |

**这一组数字本身就是"云防火墙是否在生效"的对照实验**：同一次探测、同一个 ufw，
宿主进程的 443 被拦下（受 ufw 管辖），Docker 的 5200/6379/8000 却穿透
→ ① 主机层 ufw 对 Docker 端口无效；② **当前没有任何云防火墙在遮挡**。

→ 故 szbolent-cn 的「**安全组 + 容器绑定双保险**」在 Vultr 上**第二层缺失**，
本仓 P0 即补此层（`compose/docker-compose.yml` 端口收内网）。

### ⚠️ 云安全组的能力边界（回答"自动化部署 + 人工控制安全组"）

- Vultr 的 **Firewall Group 属数据中心层**，机器内部（含 metadata `169.254.169.254`）**读不到**，
  只能在 Vultr Console 人工配置、或用 Vultr API 自动化。
- 本机**没有** `VULTR_API_KEY` / `vultr-cli` / `terraform`
  → 要**自动化**控制安全组，须先提供 Vultr API token；否则只能是**人工 Console 操作**。
- **加云防火墙会削弱验收力**：一旦挂上"只放 22/80"，公网打不通 5200 将变成**恒真**
  （无论容器绑 `0.0.0.0` 还是 `127.0.0.1`），公网探针从"强判据"退化为"假阳性"。
  → 分工必须固定：**`docker port` = 正确性判据；云防火墙 = 容错层**，不可互相替代。

## 四、已知跨机依赖

| 依赖 | 现状 | 解耦方向 |
|---|---|---|
| 营销站 `/var/www/genz-web` | **已从本机删除**（2026-09-18）；真源 `GenzLTD/genz-web` → Vercel | 本仓不再托管 |
| 静态站 `/var/www/saas/dist` | tspace 构建产物 | 本仓 nginx 的 tspace root |
| `szbolent.cn` 门户 `/v1/` → 本机 | 对端反代到本机 API | 对端登记，见 szbolent-cn `CATALOG.md` §三 |
| 企查查 MCP `1.14.202.161:8998` | 本机后端出网调用 | 外部服务，非本机部署 |

## 五、待决事项（需 Owner 定，不在 P0 内擅自改）

| # | 事项 | 现状矛盾 | 选项 |
|---|---|---|---|
| D1 | **Cloudflare 回源模式** | `nginx.conf:24` 注释写「Flexible → port 80」，`scripts/deploy-overseas.sh` 写「self-signed cert + Full mode」——**同一套部署自相矛盾** | A) Full + Origin 证书 + 放行 443（安全，需 CF 侧操作）；B) 明确 Flexible + 删除 443 块与 HSTS（最小改动，但 CF↔origin 明文） |
| D2 | 443 上 HTTPS server 块 + HSTS；`circle.genz.ltd` 是否收进本机 | 公网 443 仍 filtered；摘块后只留 api / tspace。仓内已有 `nginx/sites/circle.genz.ltd.conf`，**未** include。DNS 现仍可能指天翼 | 随 D1 处置 443。circle 进现网必须是独立 `stack-v*`（kernel :5211 + DNS 已切），禁止手改 nginx |
| ~~D3~~ | ~~镜像未仓库化~~ | **已拍板**：C2 镜像仓库化 | 待实施；调查笔记见 `docs/LIVE-FORENSICS-2026-09-18.md` |
| D4 | 发版重写 `.env` | `looma-zervi` 的 `deploy-overseas.yml` 用 `set_kv` 每轮覆盖约 20 键（含 `STRIPE_WEBHOOK_SECRET`）→ 下次 tag 发版会把旧值写回 | 见 `proposals/looma-zervi-set_kv-seed-only.md`（上游补丁） |
| D5 | 是否挂 Vultr Firewall Group | 当前无云防火墙；ufw 对 Docker 端口无效 | **建议 S4 之后再挂**（只放 22/80）作为容错层；需 Vultr Console 或 API token |

## 六、决策记录

| 日期 | 决策 | 依据 |
|---|---|---|
| 2026-09-18 | **本仓 = 海外部署唯一真源**；`looma-zervi` 的 `deploy-overseas.yml` 废弃 | Owner 口径 |
| 2026-09-18 | **S6 = C2 镜像仓库化**（compose 只留 `image:`，栈目录自包含） | Owner 选择；网络前提已实证（§2.1 出口 401） |
| 2026-09-18 | **端口临时访问只走 SSH 隧道**，不开公网窗口 | Owner 口径 |
| 2026-09-18 | **仓内必须有 GFCC 契约层**；发版骨架 = 双门禁并行 → tspace artifact → 单点 8 步；**现在禁止打 tag 部署** | 现网服务仍在跑；tspace 源码已进 `frontend/packages/saas`；`DEPLOY_ENABLED` 关 |
| 2026-09-19 | **GFCC 才是唯一协议真源**；本仓是海外运行时与海外部署真源；`backend/` 不是 looma 冻结钉，按管辖分叉 | 两套运行时靠契约对齐，不靠整树覆盖 |

## 七、归属与治理

- **协议唯一真源**是 `contracts/gfcc/`（`GenzLTD/gfcc`）。本仓是海外运行时与海外部署真源；`looma-zervi` 是境内运行时。实现按备案与管辖分叉，契约变了才升版本。
- 变更纪律：改本仓文件 → `scripts/assert-contracts.sh` + `scripts/dryrun.sh` 全绿 → `stack-v*` tag → 授权后才动真机。`baseline/` 只作回滚对照，不是期望态。契约可变，发版记录必须跟上。
- 回滚纪律：只从 `/opt/vultr-genzltd-stack/releases/<tag>/` 取树；目录不存在则拒绝。
- 资源↔主体↔服务的完整对账以 docs 仓《资源-主体-服务对账表》为准。
