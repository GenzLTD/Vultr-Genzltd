# Vultr-Genzltd

Vultr 海外机（`api.genz.ltd` / `tspace.genz.ltd`，以及后续 `circle.genz.ltd`）的**海外运行时仓**。

**唯一协议真源是 GFCC**（`contracts/gfcc/`，写作汇合处 `GenzLTD/gfcc`）。本来要的是**一套** looma 后端同时服务境内和海外。备案和管辖把它拆成两套运行时：境内 `looma-zervi`，海外本仓。两边对齐的不是代码树，是这份契约。实现按管辖分叉——支付、身份、Host、发版管线都可以变；契约的字段、枚举、入口变了才升版本。

本仓是**海外部署与海外实现**的真源（compose / nginx / Stripe / `stack-v*`），不是现网 `/opt` 的复刻，也不是 `looma-zervi` 的冻结钉。`backend/` 按海外环境改；clone 之后以本仓干跑和构建，不要再借 `looma-zervi` 补路径。

范本：`GenzLTD/szbolent-cn`（一机一仓、clone 即可干跑）。

---

## 跟谁 / 不跟谁

成员 clone 后只跟本仓这些路径：

| 你要动的 | 只改这里 |
|---|---|
| GFCC 契约（两套运行时的共享协议） | `contracts/gfcc/`（协议可以升版本；实现不必等国内仓先合） |
| tspace 前端（CI 打 dist） | `frontend/packages/saas`（依赖 `frontend/packages/shared-core`） |
| 容器端口与服务 | `compose/docker-compose.yml` |
| Host 分流（现行：api + tspace） | `nginx/nginx.conf` |
| `circle.genz.ltd` 片段 | `nginx/sites/`（默认不进现行 conf） |
| 后端代码（海外运行时，可按管辖分叉） | `backend/`（起步拷贝见 `backend/SOURCE.json`；协议不在这里） |
| 镜像构建 | `docker/Dockerfile.backend` |
| 环境变量键清单 | `.env.example`（真值永不入库） |
| 本地校验 | `scripts/dryrun.sh` |
| 部署管线契约 | `tests/deploy-contract/`（管线层，不放进 `backend/`） |
| 与境内的区别归集 | `docs/looma-overseas/`（对照册，不是第三套代码） |
| 打发版 tag | `scripts/release-tag.sh` |
| 按 tag 回滚 | `scripts/rollback-tag.sh` |
| 可选：Windows ServBay 旁路演示 | `local/`（只绑 18080/18081/18082） |

**不要跟：**

| 容易误跟的 | 为什么不是真源 |
|---|---|
| `looma-zervi` 的 `docker/nginx.conf` / `nginx-vultr.conf` | 产品单仓里的历史件。`nginx-vultr.conf` 不被任何管线引用。海外机反代以**本仓** `nginx/nginx.conf` 为准 |
| 旁边再 clone 一份 `looma-zervi` 来补 `../backend` | 相对路径已经指向**本仓** `backend/`、`docker/`、`data/`。clone 本仓即可解析 |
| 笔记本上的 `/opt/looma-zervi` | 那是 **Vultr 生产机** 上的历史目录，不是本地布局。干跑不再组装这份假树 |
| `GenzLTD/genz-web` / Vercel 裸域 | 营销站生产仍在 Vercel。**生产** `nginx/nginx.conf` **不得**再出现 `server_name genz.ltd` / `www.genz.ltd`。本机若要用 `local/` 仿真官网，只允许绑 18080，不得占用 80/443 |
| 本机 ServBay 的 80/443 | 与本仓生产期望态无关。旁路演示见 `local/` |
| 把 `backend/` 当 looma 冻结钉、等国内 PR 再覆盖 | 海外实现以本仓为准；协议以 GFCC 为准。参考国内实现可以，整树覆盖会把本仓已改的东西盖掉 |

海外功能直接改本仓 `backend/` / `frontend/`。只有**协议字段、枚举、入口**变了，才改 `contracts/gfcc` 并升版本——国内仓按新契约适配，不是国内仓先合、本仓再钉一份。反向亦然。

---

## 仓内布局

```
.
├── README.md                      # 本文件：clone 后只看这个
├── contracts/gfcc/                # GFCC L0 钉（Ask 1.2.0 / 信号 1.0.0 + SOURCE.json）
├── compose/docker-compose.yml     # 期望态（P0：端口只绑 127.0.0.1:5200）
├── nginx/nginx.conf               # 期望态（api + tspace；裸域已摘）
├── nginx/sites/                   # circle 等 Host 片段（解开 include = 独立 tag）
├── frontend/                      # tspace：saas-build 打 dist，禁止手搓上传
│   ├── packages/saas/
│   └── packages/shared-core/
├── backend/                       # 海外运行时（可分叉；协议真源在 contracts/gfcc）
├── data/poetry_full/              # 诗词库挂载点（空目录即可干跑）
├── data/chroma_models/
├── baseline/                      # 2026-09-18 晨间现网冻结（回滚对照，不是期望态）
├── scripts/dryrun.sh              # 本地干跑（不碰真机）
├── scripts/release-tag.sh         # 契约+干跑全绿才允许打 stack-v*
├── scripts/rollback-tag.sh        # 从 STACK_DIR/releases/<tag>/ 回滚
├── .env.example                   # 键清单；compose 校验用桩
├── docs/looma-overseas/           # 境内 vs 海外区别归集（不是第三套运行时）
└── docs/LIVE-FORENSICS-2026-09-18.md  # 当时真机调查笔记（归档，不是入门）
```

`compose/docker-compose.yml` 里的 `../backend`、`../docker`、`../data` 都是相对**本文件所在目录**解析的，所以只在本仓内成立。

---

## 本地怎么干跑

前置：Docker Desktop（或等价引擎）+ `docker compose` 插件 + bash + python3 + openssl。

不需要：looma-zervi 工作副本、ServBay、`/opt/looma-zervi`、生产 SSH、Stripe 真密钥。

```bash
git clone git@github.com:GenzLTD/Vultr-Genzltd.git
cd Vultr-Genzltd

# 静态校验（CI 同款，不拉运行时探针镜像以外的东西）
bash scripts/dryrun.sh --static

# 全量（含回环绑定实证；需要能拉 nginx 镜像）
bash scripts/dryrun.sh
```

干跑会：

1. 在本仓内补齐 `data/` 空目录，以及（仅当不存在时）用 `.env.example` 生成 `backend/.env` 桩——**不含真密钥**
2. 校验 `contracts/gfcc`（SOURCE 钉、家族版本、仓内 `$ref`）
3. 跑 `tests/deploy-contract/`（守 `deploy.yml` 顺序、Stripe tspace 回调意图、`Pricing.tsx` 回调源）
4. 对本仓 `compose/docker-compose.yml` 做 `docker compose config`
5. 断言唯一允许发布的宿主端口是 `127.0.0.1:5200`
6. 用容器跑 `nginx -t`（本仓 `nginx/nginx.conf`）
7. 断言 nginx **没有**裸域 `server_name`；`circle.genz.ltd` 只在 `nginx/sites/`，未混进现行 conf
8. （全量）证明 `127.0.0.1` 绑定在其它网卡不可达

退出码 0 才算过。Windows 用 Git Bash 或 WSL 跑上述脚本（仓库里没有 bash.exe 时，ServBay 的 `packages\git\usr\bin\sh.exe` 也可以）。不要用本机系统 nginx 去替代第 6 步。若 Git Bash 找不到 Python，指定后重跑：

```bash
export PYTHON_BIN=/c/path/to/python.exe
bash scripts/dryrun.sh --static
```

首次本地构建镜像（可选，干跑不强制）：

```bash
docker compose -f compose/docker-compose.yml build \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple/
```

本仓默认 PyPI 官方源（面向海外）。若在国内网构建卡住，再加：

```bash
--build-arg USE_CN_MIRROR=1 \
--build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

`backend/.env` 桩不能拿去连生产 Stripe。真值只存在于 Vultr 机上的 `.env`，由 `scripts/seed-env.sh` **仅首次种入、永不覆盖**。

---

## 发版：双门禁并行 → 单点扇入（现在还不能打 tag 部署）

旧 `deploy-overseas.yml` 的骨架保留：`backend-test` ∥ `saas-build`，两项全绿才进入 **一个** `deploy`，内部 8 步串行。前端产物必须是 artifact，保证后端、静态、`git_commit` 来自同一个 tag 的同一个 commit。

本仓把第 3 步的源换成 **Vultr-Genzltd 期望态**（`compose/` 收内网、`nginx/nginx.conf` 无裸域、`contracts/gfcc`），不再 rsync looma-zervi 那份 `0.0.0.0` + 产品仓历史 nginx。

| 步 | 动作 | 相对旧管线的进化 |
|---|---|---|
| 1 | 下载 `saas-dist` artifact | 同 |
| 2 | `set_kv` 非密钥每轮对齐 + `seed_kv` 密钥只在缺失时写 | 落地 #19，防 Live whsec 被打回 |
| 3 | rsync 本仓 → `STACK_DIR/releases/<tag>/`，再覆盖现役 compose/backend；**不** `--delete` `/opt/looma-zervi` | 源换本仓；禁止整树删除 |
| 4 | poetry 数据（仓里有才投） | 同 |
| 5 | 前端 → `/var/www/saas/dist` `--delete` | 同；缺 artifact 则根本进不了 deploy |
| 6 | 本仓 `nginx/nginx.conf`，`nginx -t` 过了才动；**reload 不停 80/443** | 现网收款在跑，禁止 kill 监听 |
| 7 | `git_commit.txt` 写在容器启动前；hash marker 决定是否重建镜像；**不 `compose down` 整栈** | redis/chroma 有状态 |
| 8 | 本机 5200 + `Host: api.genz.ltd`，再公网 api health + tspace 同源 login + `/register` | **不** curl `genz.ltd`（Vercel 不是本管线） |

工作流：`.github/workflows/deploy.yml`（已删掉另起的 `release.yml`，避免两项同步触发）。

**现在不要打 tag、不要 `--push`、不要开 `DEPLOY_ENABLED`。** 旧机服务仍在跑；`overseas-*` 还可能把 compose 盖回 `0.0.0.0`。tspace 已在 `frontend/packages/saas`，`saas-build` 会打出同源 dist；缺的不是前端，是旧通道还没停。

本地演练（不推远端）：

```bash
bash scripts/build-saas.sh                  # 打 dist；不要手搓上传
bash scripts/release-tag.sh 0.1.0           # 允许打本地 tag；--push 被拒绝
```

收口顺序（以后，不是现在）：停 `looma-zervi` 的 `overseas-*` → `main` 上双门禁全绿（含 tspace 构建）→ 再谈第一个 `stack-v*` 与 `DEPLOY_ENABLED`。

`circle.genz.ltd` 的 include 已随 circle 生产化 tag 解开：kernel 在基座 `compose/docker-compose.yml`（127.0.0.1:5211），deploy.yml reload nginx 前断言 kernel /health 200 且 `ETHOS_AUTH_SECRET` 非空（空=stub，假 JWT 可建圈）；DNS 切换是健康绿之后的人工动作。

---

## 可选：Windows ServBay 三端口演示

这不是 clone 前置，也不是真机 nginx。它用 ServBay 的 `nginx.exe` 另开前缀，**不改 80/443**，在本机仿真三站：

| 端口 | 仿真 | 路径 |
|---|---|---|
| 18080 | `genz.ltd` 官网 | `local/www/genz-web/`（自己 `pnpm --filter @looma/genz-web build` 拷进来） |
| 18081 | `api.genz.ltd` | 反代 `127.0.0.1:5200` |
| 18082 | `tspace.genz.ltd` | `local/www/tspace/`（`bash scripts/build-saas.sh` 后把 `frontend/packages/saas/dist` 拷进来） |

```powershell
# 仓库根目录
.\local\start.ps1
# 停
.\local\stop.ps1
```

`local/www/tspace/`、`local/www/genz-web/`、`backend/.env` 真值都不入库。生产期望态仍以 `nginx/nginx.conf` + `compose/docker-compose.yml` 为准。

---

## 本仓不管什么

这些不要放进「clone 后我要在本仓验证」的清单：

- Stripe Live webhook 轮换、真实收款
- Cloudflare DNS / 回源模式切换（含把 `circle.genz.ltd` 从天翼切到本机）
- `genz.ltd` / `www.genz.ltd` 营销站（Vercel）
- 围坐 **kernel 实现**（Tatha / gfcc 进程）；本仓先收契约和 Host 片段
- `szbolent.cn` 书店、橱窗
- 停用 `looma-zervi` 的 `deploy-overseas.yml`（那是维护者切通道，不是 clone 步骤）

---

## 生产机（给维护者，不是 clone 前置）

真机现在还跑在 `/opt/looma-zervi`（历史目录名）。那是 **Vultr 上的路径**，不是本仓的本地布局。

- CI 默认只干跑。`DEPLOY_ENABLED` 未打开时，部署 job 不会出现。
- 在双写通道（`looma-zervi` 的 `overseas-*` rsync）停掉之前，不要把本仓 compose 直接投到生产——会被静默盖回 `0.0.0.0`。
- 真机调查原文已挪到 [`docs/LIVE-FORENSICS-2026-09-18.md`](docs/LIVE-FORENSICS-2026-09-18.md)。
- 服务清单见 [`CATALOG.md`](CATALOG.md)。P0 应用步骤见 [`docs/DIFF-vs-live.md`](docs/DIFF-vs-live.md)。

### CI 需要配置的参数（仅维护者）

| 参数 | 类型 | 必填 | 用途 |
|---|---|---|---|
| `SSH_PRIVATE_KEY` | secret | 部署时才要 | 登录目标机 |
| `DEPLOY_HOST` | var | 部署时才要 | 目标机 IP |
| `DEPLOY_USER` | var | 否 | 缺省 `root` |
| `DEPLOY_ENABLED` | var | ⛔ 先别设 | 只有等于 `true` 时部署 job 才可能出现 |

本地 clone **不需要**这些。

---

## 当前状态（短）

| 项 | 状态 |
|---|---|
| 本仓自包含（backend / compose / nginx / docker） | 是。clone 即可干跑 |
| GFCC 契约钉 | Ask/五端口 **1.3.0**、信号 **1.0.0**，来源 gfcc `3dcb0846` |
| nginx 期望态 | api + tspace + circle（include 已解开）；裸域已摘 |
| compose 期望态 | 端口收内网（相对 `baseline/` 的 P0） |
| `stack-v*` 发版 / 真机 `releases/` | 双门禁 YAML 已就位（含 tspace 构建）；**禁止打 tag 部署**；`DEPLOY_ENABLED` 关 |
| 真机应用 P0 / 停旧通道 | 未授权，未做 |
| 镜像仓库化（compose 只留 `image:`） | 已选方向，未实施。落地前仍用本仓 `backend/` bind mount |
