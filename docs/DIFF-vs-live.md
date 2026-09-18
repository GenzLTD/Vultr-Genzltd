# P0 变更集：端口收内网

> 变更对象：`139.180.184.25` 的 `/opt/looma-zervi/docker/docker-compose.yml`
> 基线指纹：`8aace57b5c757e70a5298add5534ef6f`（现网实测，见 `baseline/MANIFEST.md`）
> 状态：**本地干跑通过后仍未应用**；应用需显式授权。

## 一、改了什么（仅三处）

| 服务 | 现网 | 变更后 | 理由 |
|---|---|---|---|
| `backend` | `"5200:5200"`（= 0.0.0.0） | `"127.0.0.1:5200:5200"` | 宿主 nginx 的 `upstream looma_backend` 指向 **`127.0.0.1:5200`**，收内网不影响链路；公网不再能直连绕过限流/审计 |
| `chromadb` | `"8000:8000"` | **删除 ports** | 仅由 backend 经 `looma-net` 以 `chromadb:8000` 访问（`CHROMA_HOST=chromadb`、`CHROMA_MODE=remote`） |
| `redis` | `"6379:6379"` | **删除 ports** | 仅由 backend 经 `looma-net` 以 `redis:6379` 访问（`RATE_LIMIT_STORAGE_URI=redis://redis:6379/1`）；且 redis 无 `requirepass` |

其余逐字节不变。`nginx/nginx.conf` 与基线**完全一致**（本变更集不含 nginx）。

## 二、为什么安全（动前已核）

1. **nginx 链路不变**：`upstream looma_backend { server 127.0.0.1:5200; }` —— 宿主回环仍在。
2. **宿主侧无消费者**：实测 `crontab -l` 为空、无自定义 systemd timer、
   `ss -tnp` 无到 6379/8000 的连接；源码内引用 6379/8000 的只有
   `deploy-overseas.sh`（写的是服务名 `redis:6379`）与 `start-full-mvp.sh`（本机 dev 脚本，不在机器上跑）。
3. **数据安全**：`docker compose up -d` 会重建容器，但 `redis-data` / `chroma-data` / `backend-data`
   为具名卷，bind mount 亦不受影响。

## 三、影响与代价

- **有短暂中断**：`backend` 单容器重建，预计 5–15 秒不可用（无滚动能力）。
- **对外行为变化（预期为正）**：`5200/6379/8000` 从"公网可达"变为"仅回环"。
  任何依赖公网直连这三端口的**外部**脚本会失败——已排查本机与两仓，无此依赖。
- **不变**：`80` 对外、`/health` 可达、Stripe webhook 路径不受影响（走 `80` → nginx → backend）。

## 四、应用步骤（授权后执行）

```bash
# 0) 备份（回滚物）
ssh vultr-overseas 'cp /opt/looma-zervi/docker/docker-compose.yml \
  /opt/looma-zervi/docker/docker-compose.yml.bak-20260918-ports'

# 1) 投递变更后的 compose
scp compose/docker-compose.yml vultr-overseas:/opt/looma-zervi/docker/docker-compose.yml

# 2) 重建（仅端口变化，数据卷不动）
ssh vultr-overseas 'cd /opt/looma-zervi/docker && docker compose up -d'

# 3) 健康门禁
scp scripts/healthcheck.sh vultr-overseas:/opt/looma-zervi/scripts/
ssh vultr-overseas 'bash /opt/looma-zervi/scripts/healthcheck.sh'

# 4) 外部复测（关键：公网必须打不到）
for p in 5200 6379 8000; do
  printf '%s ' "$p"; nc -vz -w 4 139.180.184.25 $p 2>&1 | tail -1
done   # 期望：三个全部失败/超时
ssh vultr-overseas 'docker ps --format "{{.Names}}|{{.Ports}}"'
# 期望：looma-backend 仅 127.0.0.1:5200；redis/chromadb 无宿主端口
```

## 五、回滚（任一步失败）

```bash
ssh vultr-overseas 'cd /opt/looma-zervi/docker && \
  cp docker-compose.yml.bak-20260918-ports docker-compose.yml && \
  docker compose up -d && docker ps --format "{{.Names}}|{{.Ports}}"'
```

回滚后 `5200/6379/8000` 恢复公网可达——即"回到有风险的旧状态"，仅用于止血。

## 六、验收标准

- [ ] `scripts/healthcheck.sh` 退出码 0（含"端口收内网"断言）
- [ ] 公网 `nc` 到 5200/6379/8000 **全部失败**
- [ ] `https://api.genz.ltd/health` 返回 200 且 sha 与变更前一致（未发版，代码未动）
- [ ] `docker ps` 中 `looma-backend` 显示 `127.0.0.1:5200->5200/tcp`
- [ ] 20 分钟内无 5xx 增长（观察 nginx error log / backend 日志）
