# Vultr-Genzltd

> **genz-ltd 海外机（Vultr `139.180.184.25`）的部署栈**——变更集枢纽 + 本地干跑 + 可回滚应用。
>
> 范本：`GenzLTD/szbolent-cn`（阿里云 `47.115.168.107` 的自包含部署栈）。

## 一、这个仓干什么

不是为了"再复制一套部署脚本"，而是补上 Vultr 侧缺的四样东西：

| 缺口（Vultr 现状） | 本仓的回应 |
|---|---|
| 配置与运行态自相矛盾（443/HSTS 死配置、端口裸奔） | `baseline/` 冻结现网快照 + `scripts/plan.sh` 只读比对，矛盾无处藏 |
| 变更直接上生产 | `scripts/dryrun.sh` 本地全验，**通过才谈动真机** |
| 发版重写 `.env` → 密钥漂移 | `scripts/seed-env.sh` 仅首次种入，永不覆盖 |
| 无健康门禁 / 无服务清单 | `scripts/healthcheck.sh`（退出码即门禁）+ `CATALOG.md` |

## 二、边界（重要）

**本仓不是 szbolent-cn 的等价物，原因必须写明白：**

- szbolent-cn 那台机器只跑**第三方镜像**（wordpress / mysql / pgvector），所以能做到"`git clone` + CI 即可复现整台机器"。
- Vultr 这台机器跑的是 **`looma-zervi` 源码本地构建的镜像**，且 compose 用的是**相对路径**：

  ```yaml
  build:  { context: ../backend, dockerfile: ../docker/Dockerfile.backend }
  env_file: ../backend/.env
  volumes: [ ../backend:/app, ../data/poetry_full:/app/poetry_data:ro ]
  ```

  这些路径只有在 `/opt/looma-zervi/{docker,backend,data}` 这个布局下才成立。

**结论**：本仓当前的角色是「**变更集枢纽**」——修正后的 `compose/` 与 `nginx/` 由此产出，
经 dryrun 验证后**投递到 `/opt/looma-zervi/docker/`** 生效。要真正做成"一机一仓"，
需先把镜像推到 registry（见 `CATALOG.md` §四 P2），那时 compose 只留 `image:`，才能彻底解耦。

**另一条纪律**：产品代码仍由 `looma-zervi` 的 CI 投递，本仓**不接管**代码部署。

## 三、目录

```
.
├── baseline/                  # 现网冻结快照（md5 可核，兼作回滚物）
│   ├── docker-compose.yml      #   8aace57b…（= 机器 /opt/looma-zervi/docker/）
│   ├── nginx.conf              #   0f505e33…（= 机器 /etc/nginx/nginx.conf）
│   └── MANIFEST.md
├── compose/docker-compose.yml # 修正版（P0：端口收内网）
├── nginx/nginx.conf           # 与基线逐字节一致（P0 不改 nginx）
├── scripts/
│   ├── dryrun.sh              # 本地干跑（六步断言）
│   ├── plan.sh                # 真机只读比对
│   ├── healthcheck.sh         # 健康门禁（带重试 + 收内网断言）
│   ├── seed-env.sh            # .env 仅首次种入
│   └── bootstrap.sh           # 幂等初始化（只读式体检）
├── docs/DIFF-vs-live.md       # 精确变更集与回滚步骤
├── proposals/                 # 上游（looma-zervi）补丁提案
└── .github/workflows/deploy.yml  # CI：默认只干跑，真机部署需人工放行
```

## 四、怎么用

```bash
# 1) 本地干跑（不动真机，必过）
bash scripts/dryrun.sh            # 全量
bash scripts/dryrun.sh --static   # 不拉镜像，只做静态校验

# 2) 看真机与期望差在哪（严格只读，随时可跑）
bash scripts/plan.sh

# 3) 授权后才执行真机应用（见 docs/DIFF-vs-live.md，含回滚）
```

干跑六步：布局组装 → compose 语法 → **端口断言（唯一允许 `127.0.0.1:5200`）**
→ `nginx -t` → **基线指纹断言 + 精确 diff** → **回环绑定运行时实证**。

## 五、当前状态

- 本次变更集：**P0 端口收内网**（`compose/docker-compose.yml` 三处），见 `docs/DIFF-vs-live.md`。
- 尚未动真机。真机应用需显式授权。
- 待决：Cloudflare 回源模式（Flexible/Full）→ 决定 443 与 ufw；见 `CATALOG.md` §四。

## 六、CI 行为与需要配置的参数

### 工作流行为（默认安全）

| 触发 | 行为 |
|---|---|
| `push` / `pull_request`（compose / nginx / scripts / 本工作流变更时） | **只跑干跑**，无 SSH、不可能碰真机 |
| 手动 `workflow_dispatch`，`dry_run=true`（默认） | 只跑干跑 |
| 手动 `workflow_dispatch`，`dry_run=false` **且** `DEPLOY_ENABLED=true` | 干跑通过 → 投递 → 重建容器 → 健康门禁（受 `production` 环境审批保护） |
| ↑ 但 `DEPLOY_ENABLED` 未设/非 `true` | **部署 job 永不执行**（当前默认状态，见 §七） |
| `apply_nginx=true`（默认 false） | 额外应用 nginx：`nginx -t` 通过才 `reload`，**绝不停服** |

CI 里的干跑用 `--static`（跳过第 6 步"回环绑定运行时实证"，那步需要真实网卡、在开发机本地跑）。

### 需要配置的参数

**Secrets**（Settings → Secrets and variables → Actions → Secrets）：

```bash
gh secret set SSH_PRIVATE_KEY -R GenzLTD/Vultr-Genzltd   # 交互粘贴私钥全文，命令行不留值
```

**Variables**（同一页 → Variables）：

```bash
gh variable set DEPLOY_HOST -R GenzLTD/Vultr-Genzltd --body "139.180.184.25"
gh variable set DEPLOY_USER -R GenzLTD/Vultr-Genzltd --body "root"   # 可选，缺省 root
```

| 参数 | 类型 | 必填 | 用途 |
|---|---|---|---|
| `SSH_PRIVATE_KEY` | secret | ✅ | 登录目标机的私钥（对应 `~/.ssh/vultr_overseas`） |
| `DEPLOY_HOST` | var | ✅ | 目标机 IP / 域名 |
| `DEPLOY_USER` | var | ⬜ | 登录用户，缺省 `root` |
| `DEPLOY_ENABLED` | var | ⛔ | 安全硬开关。**在 §七 的双写冲突解决前不要设置**；只有等于 `'true'` 时部署 job 才可能出现 |

**环境**：Settings → Environments 建 `production`，建议配 **Required reviewers**——
这样 `dry_run=false` 也必须人工批一次才能落到真机。

**不需要配**：`DEPLOY_PATH`（`/opt/looma-zervi`）与 `STACK_DIR`（`/opt/vultr-genzltd-stack`）
写在 workflow 的 `env` 里，非敏感；`.env` 的真值不需要进 Secrets——目标机 `.env` 已存在，
`seed-env.sh` 会直接跳过，永不覆盖。

### 首次启用建议

先只跑 `dry_run=true` 一次，确认干跑五步全绿。**部署那一步先别开**——原因见 §七。

## 七、与 looma-zervi 流水线的撞车事实（2026-09-18 只读核实）

> 结论先说：**P0 若只落在本仓，会被静默回滚；而部署本身不会崩。**

### 已证「不会崩」

| 链路 | 实测证据 | 结论 |
|---|---|---|
| nginx → backend | 宿主 nginx：`upstream looma_backend { server 127.0.0.1:5200; }` | 收成 `127.0.0.1:5200:5200` **不影响回源** |
| backend → redis/chromadb | 三容器同在 `looma-zervi_looma-net` | 撤掉宿主端口发布后仍走服务名可达，**不断服** |
| compose 项目归属 | 文件首行 `name: looma-zervi`；容器 `wd=/opt/looma-zervi/docker` | 从任何目录 `up -d` 都是同一 project，**不会另起空库容器** |
| `.env` | 目标机 `backend/.env` 在位（1353B，root） | `seed-env.sh` 跳过，**不覆盖** |
| nginx 配置 | `/etc/nginx/nginx.conf` md5 `0f505e33…` = 基线；`conf.d/`、`sites-enabled/` 皆空 | 与基线逐字节一致；**非 certbot 管辖**（用 `/etc/nginx/ssl/` 手工证书） |

### 会撞车

**C1 变量漂移（会波及真实支付）**
looma-zervi 的流水线以
`docker compose --env-file backend/.env -f docker/docker-compose.yml -p looma-zervi` 调用。
而 `/opt/looma-zervi/docker/.env` **不存在** → 若缺 `--env-file`，插值源只剩 shell →
`${DEPLOY_REGION:-US}` 兜成 **US**，覆盖 `backend/.env` 里的 **SG**。
现役容器实测 `DEPLOY_REGION=SG`，且 `PAYMENT_STUB_MODE=false`（**真实支付在跑**）。
→ 本仓已对齐该调用方式，并加了插值断言（插值不是 SG 就拒绝重建）。

**C2 P0 被静默回滚（安全修复失效）**
`/opt/looma-zervi` 现由 looma-zervi 的 `deploy-overseas.yml` 以
`rsync -avz --delete` 全树同步（源仓 HEAD `a52638e5` = 线上 `health.git_commit`）。
而**源仓里的 `docker/docker-compose.yml` 仍是 `"5200:5200"`/`"8000:8000"`/`"6379:6379"`（未做 P0）**
→ 下次 `overseas-*` tag 发布即把 P0 覆盖回 `0.0.0.0`，**公网重新暴露且无人察觉**。
（该流水线触发条件：`push: tags: overseas-*` 或手动，非定时。）

**C3 污染对方部署树**
`/opt/looma-zervi/scripts/` 属 looma-zervi 仓；往那里 scp 本仓脚本会被 `rsync --delete` 清掉，
导致健康门禁脚本丢失。→ 本仓已改用独立目录 `STACK_DIR=/opt/vultr-genzltd-stack`。

### 两条出路（待 Owner 拍板）

**路径 A（推荐）**：本仓只做「干跑门禁 + 变更集枢纽」，**删掉 deploy job**；
P0 三处端口改动作为 PR 提到 `looma-zervi`，走它现成且完整的 `deploy-overseas.yml`
（该流水线本就 `up -d --remove-orphans --force-recreate --no-build` + 本地/公网双重健康检查）。
一条通道，零撞车。

**路径 B**：让本仓当唯一部署入口 → 必须先停用/剥离 looma-zervi 的部署段，
并把 P0 回灌 looma-zervi 仓（否则被 rsync 覆盖）；本仓已修的 C1/C3 保留。

### 顺带实证：`CATALOG.md` §四 待决 D1（Cloudflare 回源模式）

nginx 与部署脚本是按 **Cloudflare Full + 自签 origin 证书**准备的
（`/etc/nginx/ssl/fullchain.pem`；`deploy-overseas.yml` 注释明写 "Origin TLS for Cloudflare Full mode"）。
但**公网实测 443 为 filtered，`ufw` 仅放行 22/80**，而站点仍 200
→ 实际回源走的是 **80（Flexible）**。
**含义：切 Full 之前必须先 `ufw allow 443`，否则一切就全站 502。**

另注：`5200/6379/8000` 公网 OPEN 是 `docker-proxy` 绕过 `ufw` 的结果——
收内网只能靠 compose 端口绑定，指望 ufw 无效（这正是 P0 的意义）。
