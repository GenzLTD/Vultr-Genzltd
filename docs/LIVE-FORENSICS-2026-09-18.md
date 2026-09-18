# 归档：2026-09-18 真机只读核实（S1）

> 这是当时的调查笔记，**不是 clone 指南**。成员本地构建请看仓库根目录 `README.md`。
> 生产机路径 `/opt/looma-zervi` 只描述当时 Vultr 上的历史布局，不要在笔记本上复刻。

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

**另一条纪律（2026-09-18 修订中）**：原文为「产品代码仍由 `looma-zervi` 的 CI 投递，
本仓**不接管**代码部署」。Owner 已把方向改为「本仓为海外部署唯一真源」，该条随之失效；
产品代码的进入方式（拉 `looma-zervi` 指定 ref / 镜像仓库化 / 过渡排除）见 §七「仍有待决」。

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

### 拍板结果（Owner 2026-09-18）：路径 B —— 本仓为海外部署唯一真源

**口径**：本仓将来是唯一海外部署真源；现况已探明 → 在本仓归集 → 本地实测 → 本仓部署 →
`looma-zervi` 的 `deploy-overseas.yml` **废弃**。

但必须先说清一件事：`deploy-overseas.yml` **不只是一条会撞车的流水线，它同时是海外站的
产品发版通道**（后端测试 → 构建 tspace 前端 → rsync 产品代码 → 同步诗词 Chroma →
部署 nginx → 构建/重建容器 → 本地+公网双重健康检查 → 清理镜像）。
所以"废弃它"= 本仓必须整体接管这条通道，否则海外将**无法再发版**。分阶段如下：

| 阶段 | 内容 | 状态 |
|---|---|---|
| S1 现况探明 | 真机只读核实（§七 撞车事实 + §八 运行环境与可行性） | ✅ 完成 |
| S2 契约归集 | 本仓持有 compose / nginx / scripts，且**部署终态 = 端口收内网** | ✅ 已具备 |
| S3 本地实测 | `dryrun.sh` 全绿 + 工作流 YAML 可解析 | ✅ |
| S4 本仓部署 | 本仓投递并重建；含端口收敛断言 + 公网不可达断言 + 失败回滚 | ⬜ 待授权执行 |
| S5 旧通道废弃 | 停用 `looma-zervi` 的部署段，消除 rsync 覆盖 | ⬜ S4 成功后立即执行 |
| S6 代码投递归属 | **C2 镜像仓库化**（Owner 2026-09-18 拍板）；子项见 §八·6 | ⬜ 待实施 |

**端口口径（Owner 2026-09-18）**：端口「公开 / 收内网」由**部署流程掌控**——每次部署的
**终态**必须是收内网，并由两道独立门禁把关：**服务端 `docker port` 权威断言** +
**runner 侧公网不可达断言**。临时访问一律走 **SSH 隧道**（`ssh -L`），不开公网窗口：
端口每开一次都要重建容器（几秒~几十秒 502），而隧道零中断、零暴露。

**S5 之前必须知道的风险窗**：只要 `deploy-overseas.yml` 还没停用，一次 `overseas-*` tag
发布就会用 rsync 把端口收敛**覆盖回 `0.0.0.0`**。故 S4 成功后应尽快执行 S5。

### S6 已拍板：C2 镜像仓库化（Owner 2026-09-18）

| 选项 | 做法 | 取舍 |
|---|---|---|
| C1 拉指定 ref | 本仓按 `PRODUCT_REF` 拉 `looma-zervi`，只同步 `backend/`、`data/`、前端产物 | 过渡可用，仍依赖对方仓与相对路径 |
| **C2 镜像仓库化（已选）** | CI 构建镜像推 registry，compose 只留 `image:`；栈目录自包含，可迁出 `/opt/looma-zervi` | 改动面最大，一劳永逸；**须放弃 `backend/` bind mount** |
| C3 过渡排除 | 对方 rsync 排除 `docker/` | 与"废弃旧通道"冲突 |

C2 有一个**必须提前知道**的代价（§八·2 有实证）：现状是"镜像只装依赖 + 代码 `bind mount`"，
且 `looma-zervi-backend` 镜像自 **2026-09-03** 起未重建过。C2 之后代码进镜像，
**改一行后端代码 = 重建镜像 + 推 + 拉**，不再能"同步文件 + 重启"。
换来的是硬版本锚点（镜像 digest），取代现在那个脆弱的 `backend/git_commit.txt`（§八·3）。

## 八、真机运行环境实证与可行性（S1 详证 · 2026-09-18 只读）

### 8.1 平台与运行时

| 项 | 实测值 | 含义 |
|---|---|---|
| 主机 | Vultr **VHP** · Ubuntu 22.04.5 LTS · kernel 5.15.0-185 · hostname `genz-ltd` · region **SG(SGP)** | — |
| Docker | **29.6.1** · storage `overlayfs` · cgroup **v2** · root `/var/lib/docker` | **容器化早已成立** ✅ |
| Compose | **v5.3.1 插件**；**无**独立 `docker-compose` | 只能用 `docker compose`（连字符版会 not found） |
| 编排归属 | project=`looma-zervi` · cfg=`/opt/looma-zervi/docker/docker-compose.yml` · wd=`/opt/looma-zervi/docker` | 本仓此前的全部假设成立 |
| 资源 | `/` 94G（用 24G，**余 67G**）· 内存 3.9G（可用 3.0G） | 拉镜像充裕；**在真机构建偏紧，CI 构建更合适** |
| 磁盘占用 | 镜像 1.93G · **build cache 5.06G（可回收 4.02G）** | build cache = "曾在真机构建"的痕迹 |
| 出口连通 | `ghcr.io/v2/` → **401** · `registry-1.docker.io/v2/` → **401**（均为正常鉴权挑战） | **镜像仓库化的网络前提成立** ✅ |

### 8.2 镜像只装依赖，代码靠 bind mount

`Dockerfile.backend` 注释原话「应用代码由 compose volume 挂载，镜像只装依赖」。实测印证：
容器 `Created=2026-09-17T13:27Z`，而镜像 `looma-zervi-backend` **Created=2026-09-03T16:30Z**
——**镜像两周未重建**。

| 类型 | 源 | 目标 | rw |
|---|---|---|---|
| bind | `/opt/looma-zervi/backend` | `/app` | ✅ |
| bind | `/opt/looma-zervi/data/poetry_full` | `/app/poetry_data` | ❌ |
| bind | `/opt/looma-zervi/data/chroma_models` | `/root/.cache/chroma/onnx_models` | ✅ |
| volume | `looma-zervi_backend-data` | `/app/data` | ✅ |
| volume | `looma-zervi_chroma-data` | `/app/chroma_data` | ✅ |

**推论**：① **P0 无需重建镜像**，端口只在 compose 里，`up -d` 即生效；
② **C2 不是小改**，它必须删掉 `backend/` 这条 bind mount、把代码 `COPY` 进镜像。

### 8.3 安全组能力（Q2 的正面回答）

- Vultr 的 **Firewall Group 属数据中心层**，机器内部（含 metadata `169.254.169.254`）**读不到**，
  只能 **Vultr Console 人工配置**，或用 **Vultr API 自动化**。
- 本机**没有** `VULTR_API_KEY` / `vultr-cli` / `terraform`
  → **要自动化控制安全组，须先提供 Vultr API token**；否则只能人工 Console 操作。
- **"安全组现在有没有生效"不需要 API 就能判定**——§七 那组端口实测本身就是对照实验：
  同一次探测、同一个 ufw，宿主进程的 **443 被拦下**，Docker 的 **5200/6379/8000 穿透**
  → ① 主机层 ufw 对 Docker 端口无效；② **当前没有任何云防火墙在遮挡**。

### 8.4 ⚠️ 必须纠正的验证逻辑：云防火墙会「削弱」验收力

你的顾虑是"否则你无法验证成功与否"。这里有个反直觉但关键的点：

| 判据 | 无云防火墙（现状） | 挂了"只放 22/80"的云防火墙之后 |
|---|---|---|
| 公网探 5200/6379/8000 打不通 | **强判据**：没有别的东西遮挡 ⇒ 打不通就是容器真的收内网了 | **假阳性**：容器绑 `0.0.0.0` 还是 `127.0.0.1` 都打不通 → 判据失效 |
| `docker port` 断言 | 判"绑对了没有" | 判"绑对了没有"（**此时唯一有效**） |

分工固定、不可互相替代：**`docker port` = 正确性判据；云防火墙 = 容错层。**

**落地次序建议**：
1. **先在"无云防火墙"状态下做 S4**——此刻公网探针最强，一次就能证明 P0 真的生效；
2. S4 通过**之后**再挂 Vultr Firewall Group（只放 22/80）当防呆层：将来若有人把端口改回 `0.0.0.0`，
   `docker port` 断言会失败（正确性），防火墙保证不泄露（容错），两层都在岗；
3. **不加**"部署时临时开放安全组"的窗口——容器层收内网本身就是终态；要临时访问走 SSH 隧道（你已选）。

### 8.5 版本锚点现状（脆弱，C2 必须换掉）

- `backend/git_commit.txt` = **`a52638e5017de7eb18171ab6af0769aadeb53038`**（root，09-17 13:27）——旧流水线写入，**目前唯一锚点**。
- `/opt/looma-zervi/.git` 存在但是**零 commit 的空仓**：`branch main` 却报
  *"does not have any commits yet"*，全部文件 `??` untracked（`.git` 由 root 于 09-18 04:28 建）。
  → **git 不可用于版本对账或回滚**；C2 落地后以**镜像 digest** 取代该锚点。

### 8.6 C2 仍未定的子项

| # | 子项 | 已知约束 |
|---|---|---|
| 1 | registry 选型 | `ghcr.io` 已验证可达（401 鉴权挑战）；也可选 Vultr Container Registry / 自建 |
| 2 | 构建位置 | GitHub runner 构建（推荐，真机内存仅 3.9G）vs 真机构建（需 `--build-arg PIP_INDEX_URL=https://pypi.org/simple`） |
| 3 | 镜像 tag 策略 | digest 锁定（可复现）vs tag 漂移（好读）；建议**双轨**：不可变 tag + 部署时记 digest |
| 4 | 前端静态产物 | `/var/www/genz-web`、`/var/www/saas/dist` 是由 CI 投递的宿主文件，**不在容器内** → 是否一并纳入"栈自包含" |
| 5 | 迁移方式 | 保留 `/opt/looma-zervi` 布局（最小风险）vs 迁到独立目录（真正自包含） |

### 顺带实证：`CATALOG.md` §五 待决 D1（Cloudflare 回源模式）

nginx 与部署脚本是按 **Cloudflare Full + 自签 origin 证书**准备的
（`/etc/nginx/ssl/fullchain.pem`；`deploy-overseas.yml` 注释明写 "Origin TLS for Cloudflare Full mode"）。
但**公网实测 443 为 filtered，`ufw` 仅放行 22/80**，而站点仍 200
→ 实际回源走的是 **80（Flexible）**。
**含义：切 Full 之前必须先 `ufw allow 443`，否则一切就全站 502。**

另注：`5200/6379/8000` 公网 OPEN 是 `docker-proxy` 绕过 `ufw` 的结果——
收内网只能靠 compose 端口绑定，指望 ufw 无效（这正是 P0 的意义）。
