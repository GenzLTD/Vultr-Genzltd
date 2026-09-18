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

## 二、防火墙（ufw）

| 端口 | 状态 |
|---|---|
| `22/tcp` | ALLOW Anywhere |
| `80/tcp` | ALLOW Anywhere |
| 其余 | 默认 DROP |

### ⚠️ 关键事实：ufw 挡不住 Docker 发布的端口

`DOCKER-USER` 链为空（`iptables -S DOCKER-USER` 仅 `-N`），而 Docker 发布端口走
`nat/PREROUTING → DOCKER` 链 DNAT，**不经过 INPUT**，因此 ufw 的 `-P INPUT DROP` 对其无效。

**实测（2026-09-18，从公网）**：

| 端口 | 结果 |
|---|---|
| 22 / 80 | 通（预期） |
| **5200** | **通**（绕过 nginx 的限流与审计） |
| **6379** | **通**（Redis 无认证 → 可读写/清空限流存储） |
| **8000** | **通**（ChromaDB 裸露） |
| 443 | timeout（nginx 是宿主进程，受 ufw 管辖，未放行） |

→ 故 szbolent-cn 的「**安全组 + 容器绑定双保险**」在 Vultr 上**第二层缺失**，
本仓 P0 即补此层（`compose/docker-compose.yml` 端口收内网）。

## 三、已知跨机依赖

| 依赖 | 现状 | 解耦方向 |
|---|---|---|
| 静态站 `/var/www/genz-web`、`/var/www/saas/dist` | 由 `looma-zervi` CI 投递 | 维持（属产品侧） |
| `szbolent.cn` 门户 `/v1/` → 本机 | 对端反代到本机 API | 对端登记，见 szbolent-cn `CATALOG.md` §三 |
| 企查查 MCP `1.14.202.161:8998` | 本机后端出网调用 | 外部服务，非本机部署 |

## 四、待决事项（需 Owner 定，不在 P0 内擅自改）

| # | 事项 | 现状矛盾 | 选项 |
|---|---|---|---|
| D1 | **Cloudflare 回源模式** | `nginx.conf:24` 注释写「Flexible → port 80」，`scripts/deploy-overseas.sh` 写「self-signed cert + Full mode」——**同一套部署自相矛盾** | A) Full + Origin 证书 + 放行 443（安全，需 CF 侧操作）；B) 明确 Flexible + 删除 443 块与 HSTS（最小改动，但 CF↔origin 明文） |
| D2 | 443 上 4 个 HTTPS server 块 + HSTS | 公网不可达 → **死配置**；一旦有人放行 443，客户端会撞自签证书 | 随 D1 一并处置 |
| D3 | 镜像未仓库化 | compose 依赖产品树相对路径 → 无法"一机一仓"自包含 | P2：CI 构建镜像推 registry，compose 只留 `image:` |
| D4 | 发版重写 `.env` | `looma-zervi` 的 `deploy-overseas.yml` 用 `set_kv` 每轮覆盖约 20 键（含 `STRIPE_WEBHOOK_SECRET`）→ 下次 tag 发版会把旧值写回 | 见 `proposals/looma-zervi-set_kv-seed-only.md`（上游补丁） |

## 五、归属与治理

- 本仓只管「**本机的部署契约与变更集**」，不含产品代码。
- 变更纪律：`baseline/` 冻结现网 → 改 `compose/`、`nginx/` → `scripts/dryrun.sh` 全绿 → 授权后应用 → `scripts/healthcheck.sh` 门禁。
- 资源↔主体↔服务的完整对账以 docs 仓《资源-主体-服务对账表》为准。
