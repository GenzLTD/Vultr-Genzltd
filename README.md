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
| 手动 `workflow_dispatch`，`dry_run=false` | 干跑通过 → 投递 → 重建容器 → 健康门禁（受 `production` 环境审批保护） |
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

**环境**：Settings → Environments 建 `production`，建议配 **Required reviewers**——
这样 `dry_run=false` 也必须人工批一次才能落到真机。

**不需要配**：`DEPLOY_PATH` 固定为 `/opt/looma-zervi`（写在 workflow 的 `env` 里，非敏感）；
`.env` 的真值不需要进 Secrets——目标机 `.env` 已存在，`seed-env.sh` 会直接跳过，永不覆盖。

### 首次启用建议

先只跑 `dry_run=true` 一次，确认干跑五步全绿；再建环境 + 配审批；最后才用 `dry_run=false`。
