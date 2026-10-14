# 人格小工具（Tatha MBTI）上法兰克福预发机：技术方案（方案 A）

> **目标机**：Vultr 法兰克福预发机（本仓为公开仓，机器地址以 `<STAGING_HOST>` 占位，不入库）
> **性质**：方案待批准。先落预发，**不进生产**（生产仍走 `stack-v*` tag）
> **硬约束**：**不新增任何域名**，只走 IP 直连；**不新增任何监听端口**
> **前置（v2 修订）**：ufw 入站只放行 `22/tcp`，**必须先 `ufw allow 80/tcp`**，否则 IP 直连必然超时（实测见 §2 事实 1）
> **上游能力**：`GenzLTD/Tatha` 的 `POST /v1/mbti/analyze`（PR #7，16 型 + 三态 + 独立配额）

---

## 1. 这次要做什么、不做什么

**做**：让 `http://<STAGING_HOST>/` 能直接打开人格小工具（订阅页 → 登录 → 演示页 → 测评），端到端跑通。

**不做**：

- 不配域名（合规底线）
- 不新增对外**监听**端口（不新增 nginx server / docker 发布；但**要放行已有的 80/tcp**，见 §2 事实 1 与 §7 步骤 0）
- 不动 `api.genz.ltd` / `tspace.genz.ltd` 的现有 Host 分流
- 不进生产，不发 `stack-v*`
- 不改算法（真源在 `planetx-tatha`，漂移问题见 `GenzLTD/planetx-tatha#5`）

---

## 2. 现状：四条决定方案的事实（v2 修订，2026-10-15 实测）

| # | 事实 | 出处 |
|---|---|---|
| 1 | **ufw 入站只放行 `22/tcp`**（active，default deny incoming）。外部访问 80/443 **全部超时**；只有服务器本机 `curl 127.0.0.1/` 才得到 404 ⇒ **IP 直连目前没有任何入口，必须先放行 80** | 预发机 `ufw status` 实测；本机 `curl --noproxy '*' http://45.76.84.90/` 12s 0 字节 |
| 2 | **Tatha 不在海外栈**：compose 只有 `looma-backend`(5200) + chromadb + redis，全仓 grep 不到 `tatha` / `mbti` | `compose/docker-compose.yml` |
| 3 | **Docker 端口穿透宿主 ufw**。**预发机现状：`block-docker-ports.service` = inactive，`DOCKER-USER` 链为空**（与生产机不同）⇒ 新服务**必须**绑 `127.0.0.1`，绝不能 `0.0.0.0` | 预发机 `systemctl is-active` / `iptables -S DOCKER-USER` 实测 |
| 4 | **443 没有 `default_server`**（`listen 443 ssl http2` 两处都未标）⇒ `https://<IP>/` 会命中第一张证书 **`api.genz.ltd`**。本方案**只走 80，不承诺 https 入口** | `nginx.conf:137` / `:220` 实测 |

第 1 条说明"IP 直连"目前**没有任何入口**，必须放行 80；第 3 条说明新服务**只能绑宿主回环**；第 4 条说明别指望 `https://<IP>/`。

---

## 3. 方案 A：把 default server 反代给 Tatha

### 3.1 拓扑

```
浏览器 → http://<STAGING_HOST>/
              │
         nginx :80  default_server（原 404）
              │  proxy_pass
              ▼
        127.0.0.1:5210  ← 宿主仅回环
              │
        容器 tatha-mbti :8010
```

`api.genz.ltd` / `tspace.genz.ltd` 各自有 `server_name` 块，**不受影响**；只有不带已知 Host 的 IP 直连会落到 default server。

### 3.2 为什么是 default server 而不是新端口

- **不新增监听端口**（复用已存在的 80，代价只是一条 `ufw allow 80/tcp` 放行规则）
- 零新增域名 → 不动合规边界
- `http://<STAGING_HOST>/` 即可访问，不用记端口

代价：现在"未知 Host 一律 404"的防护被替换成"未知 Host 进 Tatha"。**预发机可接受**；若要收紧，见 §9 风险缓解。

### 3.3 nginx 改动

```nginx
upstream tatha_backend {
    server 127.0.0.1:5210;
}

server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://tatha_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

> **v2 更正**：~~根路径 302 是必须的~~ —— **不成立**。`Tatha` main（`c665677`，#7 合并后）自 `5ca2268`（2026-10-09）起就有 `GET /`（`src/tatha/api/app.py:88`，叠在 `@app.get("/index.html")` 上），直接返回 `index.html`。nginx 侧不做任何根路径特殊处理，验收期望改为 **200 + `index.html` 内容**。
>
> 另核：`nginx -T` 生效态里 `default_server` 仅此一处（`nginx.conf:115`）；`/etc/nginx/sites-enabled/default` 虽也写了 `listen 80 default_server`，但 `nginx.conf` 没有 `include sites-enabled/*`，**该文件从未加载**，改这里不会与任何现有 Host 冲突。

---

## 4. 代码怎么进本仓

照 `backend/SOURCE.json` 的先例——`backend/` 本身就是从 `looma-zervi/backend`（commit `fef232e`，2026-09-18）**起步拷贝**进来的，`may_diverge: true`。所以 Tatha 也走同一条路，不引入 submodule：

```
services/tatha/          ← Tatha 起步拷贝树
services/tatha/SOURCE.json   ← 记 fork_origin: GenzLTD/Tatha + commit + 日期
docker/Dockerfile.tatha  ← 海外版镜像（本仓维护）
```

`SOURCE.json` 内容：

```json
{
  "role": "overseas-runtime",
  "not": "algorithm source",
  "algorithm": "GenzLTD/planetx-tatha -> src/tatha/agents/mbti_analyzer.py",
  "may_diverge": false,
  "fork_origin": {
    "tree": "GenzLTD/Tatha",
    "git_commit": "c665677bdcedc52633e70a637ac9fda8d8512fdd",
    "git_commit_note": "Tatha#7 已于 2026-10-14 合并（merge commit c665677，main HEAD）。钉合并提交本身，不钉分支 2ed8453；更早的 main（1971447）没有 POST /v1/mbti/analyze 与 mbti_daily_quota，不得作为起步树",
    "copied_at": "2026-10-14",
    "note": "16 型人格测评小工具。算法真源在 planetx-tatha，本树只作海外运行时；分析器改动回上游，不在此处分叉。"
  }
}
```

### 4.1 不复用 Tatha 自带的 Dockerfile

`GenzLTD/Tatha` 顶层有 `Dockerfile`，但**不能直接用于海外预发**，三个问题：

| 问题 | 具体 |
|---|---|
| 硬编码密钥 | `ENV DEEPSEEK_API_KEY=sk-73fd842e…`（明文，且已随 commit `3e868fc` 入库） |
| 构建必失败 | `COPY .chroma-cache /root/.cache/chroma`，而仓内**无此目录** |
| 镜像源/体积 | `pip install` 走默认源；无 `.dockerignore`，`COPY . /opt/tatha` 会把 `.venv`/`.git`/`tests` 全打进去 |

因此本仓另写 `docker/Dockerfile.tatha`，风格对齐 `docker/Dockerfile.backend`（`USE_CN_MIRROR` / `PIP_INDEX_URL` 可选、装 `requirements.txt`、不写任何密钥）。

> **密钥已入库这件事要单独处理**：见 §8 待办。

### 4.2 compose 服务

```yaml
  tatha:
    build:
      context: ../services/tatha
      dockerfile: ../docker/Dockerfile.tatha
    container_name: tatha-mbti
    restart: unless-stopped
    ports:
      # 收内网：仅宿主回环。公网不能直连绕过 nginx（Docker 穿透 ufw，见 §2 事实 3）
      - "127.0.0.1:5210:8010"
    environment:
      - TATHA_USE_LLM_INTENT=false          # 意图解析走规则，不调 LLM
      - TATHA_DEFAULT_MODEL=${TATHA_DEFAULT_MODEL:-openai/gpt-4o-mini}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}  # 留空即不调 LLM，人格端点不受影响
    env_file:
      - ../services/tatha/.env
    networks:
      - looma-net
```

容器内端口 **8010**（Tatha 默认），宿主 **5210**（与国内语义一致），宿主侧只绑回环。

**v2 补两条硬规则**：

1. `docker/Dockerfile.tatha` 里必须**写死** `ENV TATHA_USE_LLM_INTENT=false`（不只靠 compose 的 environment —— 双保险，防任何裸跑回落 `true` 调 LLM）。
2. compose 操作**只能在 `/opt/looma-zervi/docker`（现网 compose 项目目录）下对单个服务 `up`**：`docker compose -f docker-compose.yml up -d --build tatha`。**禁止**在 git 检出目录对整份 `compose/docker-compose.yml` 执行 `up` —— 该文件带 `container_name: looma-backend`，会与在跑容器撞名（现网 compose 文件与仓内 `origin/main:compose/docker-compose.yml` sha256 全等：`b5ea0b9429b6892a`）。

---

## 5. 合规

| 项 | 处理 |
|---|---|
| 域名 | **一个都不加**。这是本方案的前提，不是可选项 |
| LLM 出境 | `GO-LIVE-CHECKLIST.md` 已把 `deepseek` 从海外候选剔除（GDPR Art.44+ / PIPL 出境）。预发机上 `TATHA_DEFAULT_MODEL` 走 `openai` |
| 人格端点实际上不调 LLM | `/v1/mbti/analyze` 直接调 `MBTITextAnalyzer`（关键词计数），`/v1/ask` 的 mbti 分支同样；只有意图解析会碰 LLM。**注意：`TATHA_USE_LLM_INTENT` 代码默认是 `true`**（`src/tatha/core/config.py:28`：`os.getenv("TATHA_USE_LLM_INTENT","true")`），"不调 LLM"**必须靠显式注入 `false`**——上游 `Dockerfile:12` 与本方案 compose §4.2 各有一处，缺一不可。**所以预发验证阶段 `OPENAI_API_KEY` 可以完全留空**，零数据出境；但任何绕过这两处的裸跑都会回落 `true` 并调 LLM |
| 数据落地 | 用户自述文本在法兰克福处理，不出 EU |

---

## 6. 变更清单（文件级）

| 文件 | 动作 |
|---|---|
| `services/tatha/**` | 新增（Tatha 起步拷贝树，**钉 main `c665677`**，见 §4） |
| `services/tatha/SOURCE.json` | 新增 |
| `services/tatha/.env` | 新增（真值不入库；`.env.example` 补键） |
| `docker/Dockerfile.tatha` | 新增（**写死 `ENV TATHA_USE_LLM_INTENT=false`**，见 §4.2） |
| `compose/docker-compose.yml` | 加 `tatha` 服务（**实施时只在 `/opt/looma-zervi/docker` 下 `up` 单个服务**，见 §4.2 / §7） |
| `nginx/nginx.conf` | default server 改为反代 Tatha（§3.3）。改动目标正确性已核：`origin/main` 与机器 `/etc` / `current/` / `releases/staging-r2/` 四份 sha256 全等（`2b098ab3ec3ad18f`），部署步骤 6 会把 `current/` 覆盖到 `/etc` |
| **预发机 ufw（一次性，非文件变更）** | `ufw allow 80/tcp` —— **不改此条，§7 全部验收必然超时** |
| `.env.example` | 补 `TATHA_DEFAULT_MODEL` / `OPENAI_API_KEY` |
| `docs/` | 记一笔预发入口说明 |

---

## 7. 上机步骤与验收

```bash
# 0) 前置（缺了这步，本节全部 curl 必然超时）
sudo ufw allow 80/tcp && sudo ufw status | head -5

# 0.5) 起服务（预发机，注意工作目录必须是现网 compose 项目目录；只 up 单个服务）
cd /opt/looma-zervi/docker
docker compose -f docker-compose.yml up -d --build tatha
sudo nginx -t && sudo systemctl reload nginx

# 1) 健康检查
curl -s http://<STAGING_HOST>/health

# 2) 根路径（v2 修订：Tatha 已有 GET /，期望 200 + index.html，不是 302）
curl -s -o /dev/null -w "%{http_code}\n" http://<STAGING_HOST>/
# 期望：200，且 body 含 index.html 内容

# 3) 定价含人格额度
curl -s "http://<STAGING_HOST>/v1/region?country=CN" | grep mbti_daily_quota
# 期望：free 3 / basic 30 / pro 9999

# 4) 注册取 token
TOKEN=$(curl -s -X POST http://<STAGING_HOST>/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@preprod.local","password":"smoke123456"}' \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

# 5) 三态：ok
curl -s -X POST http://<STAGING_HOST>/v1/mbti/analyze \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"我喜欢独立思考，做事注重细节和具体步骤，分析问题时看重逻辑，习惯先做好计划再执行。"}'
# 期望：status=ok，有 mbti_type / flower_personality / career_match

# 6) 三态：insufficient
curl -s -X POST http://<STAGING_HOST>/v1/mbti/analyze \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"你好"}'
# 期望：status=insufficient，mbti_type=XXXX，career_match=null

# 7) 配额：free 第 4 次
# 期望：429，且 ask 额度未被动用（独立计量）

# 8) 浏览器
# http://<STAGING_HOST>/ → 200 index.html（Tatha 自带根路由）→ 注册 → /demo.html
# 注意：https://<STAGING_HOST>/ 不在本方案范围 —— 443 无 default_server，会落到 api.genz.ltd 的证书
```

**实施前置（v2 → v2.1）**：~~`Tatha#7` 必须已合并~~ —— **已完成**：#7 于 2026-10-14 合并，main HEAD = `c665677`（已实测 `app.py:240` 含 `POST /v1/mbti/analyze`）。`SOURCE.json.git_commit` 钉 `c665677`（见 §4）。

**本机先过一遍**：`bash scripts/dryrun.sh`

---

## 8. 回滚

```bash
git revert <本方案提交>          # 只回 compose / nginx / services
# 只摘除 tatha 服务（不要对整份 compose up —— container_name 撞名，见 §4.2）
cd /opt/looma-zervi/docker
docker compose -f docker-compose.yml stop tatha && docker compose -f docker-compose.yml rm -f tatha
# nginx 回滚：用部署步骤 6 留下的备份，nginx -t 过了再 reload
ls -t /etc/nginx/nginx.conf.bak-* | head -1
sudo cp "$(ls -t /etc/nginx/nginx.conf.bak-* | head -1)" /etc/nginx/nginx.conf.new \
  && sudo nginx -t -c /etc/nginx/nginx.conf.new \
  && sudo mv /etc/nginx/nginx.conf.new /etc/nginx/nginx.conf \
  && sudo systemctl reload nginx
# 可选：撤回入口放行
sudo ufw delete allow 80/tcp
```

`looma-backend` 不在改动范围内，域名服务全程不受影响。

---

## 9. 风险与待办

| 项 | 处理 |
|---|---|
| default server 防护被替换 | 预发可接受。若要收紧：加 `allow/deny` 限定来源 IP，或改回 404 + 独立端口（方案 B） |
| **Tatha 仓 Dockerfile 硬编码 DeepSeek 密钥且已入库** | **密钥应视为已泄露，建议轮换**；向上游 `GenzLTD/Tatha` 提 PR 移除并加 `.dockerignore`。本仓 `Dockerfile.tatha` 不继承该 ENV |
| `.chroma-cache` 缺失 | 本仓 Dockerfile 不 COPY 该目录；如人格测评确需，另行挂载模型缓存 |
| ~~Tatha PR #7 未合并~~（v2.1 已解除） | **#7 已合并**（2026-10-14，merge commit `c665677`，main HEAD）。`SOURCE.json.git_commit` 钉 `c665677`，**不钉**分支 `2ed8453` |
| 算法三副本漂移 | 不在本方案范围，见 `GenzLTD/planetx-tatha#5` |
| ssh 凭据 | **v2 更正**：~~需授权后才能上机~~ —— 实测**通道存在**：Windows 机用专用预发钥（注释 `win-cursor-vultr-staging`）可登录，Dell 机用 `looma_staging_fra` 同样可登录；**被拒的只是 Mac 侧的 9 把私钥 × 6 用户名** ⇒ Mac 如需操作该机，先补配 authorized_keys |
| 443 入口 | 443 无 `default_server`，`https://<IP>/` 会命中 `api.genz.ltd` 的证书 ⇒ 本方案只承诺 **http://80**；如需 https 另行方案（配证书 + default_server），不与本方案混 |
| ufw 放行 80 的暴露面 | 未知 Host 由 404 变为进 Tatha（§3.2 已述）；`api/tspace` 两个 Host 路由本就设计为公网可达，放行 80 不改变其暴露面 |
