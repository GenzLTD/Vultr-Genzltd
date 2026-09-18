# Vultr-Genzltd

Vultr 海外机（`api.genz.ltd` / `tspace.genz.ltd`）的**自包含部署仓**。

`git clone` 之后，以本仓为唯一依据做本地干跑和构建。不要再 clone `looma-zervi`，不要在笔记本上建 `/opt/looma-zervi`，也不要按 ServBay / 某台 Mac 的路径去对齐。

范本：`GenzLTD/szbolent-cn`（一机一仓、clone 即可干跑）。

---

## 跟谁 / 不跟谁

成员 clone 后只跟本仓这些路径：

| 你要动的 | 只改这里 |
|---|---|
| 容器端口与服务 | `compose/docker-compose.yml` |
| Host 分流（nginx） | `nginx/nginx.conf` |
| 后端代码（海外栈这一份） | `backend/` |
| 镜像构建 | `docker/Dockerfile.backend` |
| 环境变量键清单 | `.env.example`（真值永不入库） |
| 本地校验 | `scripts/dryrun.sh` |

**不要跟：**

| 容易误跟的 | 为什么不是真源 |
|---|---|
| `looma-zervi` 的 `docker/nginx.conf` / `nginx-vultr.conf` | 产品单仓里的历史件。`nginx-vultr.conf` 不被任何管线引用。海外机反代以**本仓** `nginx/nginx.conf` 为准 |
| 旁边再 clone 一份 `looma-zervi` 来补 `../backend` | 相对路径已经指向**本仓** `backend/`、`docker/`、`data/`。clone 本仓即可解析 |
| 笔记本上的 `/opt/looma-zervi` | 那是 **Vultr 生产机** 上的历史目录，不是本地布局。干跑不再组装这份假树 |
| `GenzLTD/genz-web` / Vercel 裸域 | 营销站不在本机 serve。本仓 nginx **不得**再出现 `server_name genz.ltd` / `www.genz.ltd` |
| 本机 ServBay 的 80/443 | 与本仓无关 |

产品功能若要回馈国内站和其他客户端，走 `looma-zervi` 自己的 PR。那是另一条线，不是本仓 clone 前置。

---

## 仓内布局

```
.
├── README.md                      # 本文件：clone 后只看这个
├── compose/docker-compose.yml     # 期望态（P0：端口只绑 127.0.0.1:5200）
├── nginx/nginx.conf               # 期望态（api + tspace；裸域已摘）
├── docker/                        # Dockerfile.backend + .dockerignore
├── backend/                       # 海外栈后端（本仓自带，不向本机系统借）
├── data/poetry_full/              # 诗词库挂载点（空目录即可干跑）
├── data/chroma_models/
├── baseline/                      # 2026-09-18 晨间现网冻结（回滚对照，不是期望态）
├── scripts/dryrun.sh              # 本地干跑（不碰真机）
├── .env.example                   # 键清单；compose 校验用桩
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
2. 对本仓 `compose/docker-compose.yml` 做 `docker compose config`
3. 断言唯一允许发布的宿主端口是 `127.0.0.1:5200`
4. 用容器跑 `nginx -t`（本仓 `nginx/nginx.conf`）
5. 断言 nginx **没有**裸域 `server_name`，且 compose 相对 `baseline/` 仍是端口收敛
6. （全量）证明 `127.0.0.1` 绑定在其它网卡不可达

退出码 0 才算过。Windows 用 Git Bash 或 WSL 跑上述脚本（仓库里没有 bash.exe 时，ServBay 的 `packages\git\usr\bin\sh.exe` 也可以）。不要用本机系统 nginx 去替代第 4 步。若 Git Bash 找不到 Python，指定后重跑：

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

## 本仓不管什么

这些不要放进「clone 后我要在本仓验证」的清单：

- Stripe Live webhook 轮换、真实收款
- Cloudflare DNS / 回源模式切换
- `genz.ltd` / `www.genz.ltd` 营销站（Vercel）
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
| nginx 期望态 | api + tspace；裸域已摘，与 2026-09-18 真机手操一致 |
| compose 期望态 | 端口收内网（相对 `baseline/` 的 P0） |
| 真机应用 P0 / 停旧通道 | 未授权，未做 |
| 镜像仓库化（compose 只留 `image:`） | 已选方向，未实施。落地前仍用本仓 `backend/` bind mount |
