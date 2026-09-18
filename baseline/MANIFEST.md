# 现网冻结基线（MANIFEST）

> 采集时间：**2026-09-18 晨**（**摘块手操之前**）
> 这是回滚对照，**不是** clone 后要对齐的期望态。
> 期望态在仓库根的 `compose/` 与 `nginx/`：端口收内网 + 裸域已摘。
> 生产机路径 `/opt/looma-zervi` 不要在笔记本上复刻。

## 文件与指纹

| 本仓快照 | 机器上的位置 | md5 | 说明 |
|---|---|---|---|
| `docker-compose.yml` | `/opt/looma-zervi/docker/docker-compose.yml` | `8aace57b5c757e70a5298add5534ef6f` | 容器实际启动来源（`docker inspect` 标签实证） |
| `nginx.conf` | `/etc/nginx/nginx.conf` 与 `/opt/looma-zervi/docker/nginx.conf` | `0f505e33f8fb047f4185689b89e4c256` | 两处**同一份**（CI `cp` 覆盖所得） |

## 同源性核验（为什么基线可信）

| 对比 | 结果 |
|---|---|
| 仓（`looma-zervi` main）`docker/docker-compose.yml` | `8aace57b…` = 机器 ✅ |
| 仓（`looma-zervi` main）`docker/nginx.conf` | `0f505e33…` = 机器 ✅ |

→ **仓 = 机器，逐字节一致**。故基线可从仓内文件派生，且可在本地精确复现现网解析结果。

## 已知基线缺陷（变更集针对它们）

1. `backend` / `chromadb` / `redis` 三处端口均为 `0.0.0.0` 语义发布，公网实测可达（见 `CATALOG.md` §二）。
2. nginx 配了 443 + HSTS，但 ufw 未放行 443 → 公网 timeout，属死配置（待决 D1/D2）。
3. 机器上的 `.env` 无备份；且上游 `deploy-overseas.yml` 的 `set_kv` 会在下次 tag 发版时重写约 20 个键。

## 用途

- **变更审计**：`scripts/dryrun.sh` 用它证明"只改了该改的"。
- **回滚物**：与 `docs/DIFF-vs-live.md` §五 的备份文件同为回滚依据。
