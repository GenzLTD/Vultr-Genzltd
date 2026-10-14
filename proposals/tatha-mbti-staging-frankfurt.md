# 人格小工具（Tatha MBTI）上法兰克福预发机：技术方案（方案 A）

> **目标机**：Vultr 法兰克福预发机（本仓为公开仓，机器地址以 `<STAGING_HOST>` 占位，不入库）
> **性质**：方案待批准。先落预发，**不进生产**（生产仍走 `stack-v*` tag）
> **硬约束**：**不新增任何域名**，只走 IP 直连
> **上游能力**：`GenzLTD/Tatha` 的 `POST /v1/mbti/analyze`（PR #7，16 型 + 三态 + 独立配额）

---

## 1. 这次要做什么、不做什么

**做**：让 `http://<STAGING_HOST>/` 能直接打开人格小工具（订阅页 → 登录 → 演示页 → 测评），端到端跑通。

**不做**：

- 不配域名（合规底线）
- 不新增对外端口（不新增 ufw 规则）
- 不动 `api.genz.ltd` / `tspace.genz.ltd` 的现有 Host 分流
- 不进生产，不发 `stack-v*`
- 不改算法（真源在 `planetx-tatha`，漂移问题见 `GenzLTD/planetx-tatha#5`）

---

## 2. 现状：三条决定方案的事实

| # | 事实 | 出处 |
|---|---|---|
| 1 | 预发机对外只开 80 / 443，且按 `server_name` 分流。**IP 直连命中 `default_server` → `404 Unknown host`** | `nginx/nginx.conf` 第 115–121 行 |
| 2 | **Tatha 不在海外栈**：compose 只有 `looma-backend`(5200) + chromadb + redis，全仓 grep 不到 `tatha` / `mbti` | `compose/docker-compose.yml` |
| 3 | **Docker 端口穿透宿主 ufw**（实测 443 被拦，`5200/6379/8000` 却被 Docker 放行）；现网靠 `block-docker-ports.service` + `DOCKER-USER` 补防 | `LIVE-FORENSICS-2026-09-18.md` |

第 1 条说明"IP 直连"目前**没有任何入口**，必须开；第 3 条说明新服务**只能绑宿主回环**，不能 `0.0.0.0`。

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

- 零新增对外端口 → 零 ufw 改动
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

    # Tatha 没有 / 路由（只有 /index.html /demo.html /auth.html），根路径转一下
    location = / {
        return 302 /index.html;
    }

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

> 根路径 302 是**必须**的：`src/tatha/api/app.py` 只有 `/index.html`、`/demo.html`、`/auth.html`，没有 `/`，直接访问根会 404。

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
    "git_commit": "<待填：PR #7 合并后的 main，或分支 2ed8453>",
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

---

## 5. 合规

| 项 | 处理 |
|---|---|
| 域名 | **一个都不加**。这是本方案的前提，不是可选项 |
| LLM 出境 | `GO-LIVE-CHECKLIST.md` 已把 `deepseek` 从海外候选剔除（GDPR Art.44+ / PIPL 出境）。预发机上 `TATHA_DEFAULT_MODEL` 走 `openai` |
| 人格端点实际上不调 LLM | `/v1/mbti/analyze` 直接调 `MBTITextAnalyzer`（关键词计数），`/v1/ask` 的 mbti 分支同样；只有意图解析会碰 LLM，而 `TATHA_USE_LLM_INTENT=false` 默认关着。**所以预发验证阶段 `OPENAI_API_KEY` 可以完全留空**，零数据出境 |
| 数据落地 | 用户自述文本在法兰克福处理，不出 EU |

---

## 6. 变更清单（文件级）

| 文件 | 动作 |
|---|---|
| `services/tatha/**` | 新增（Tatha 起步拷贝树） |
| `services/tatha/SOURCE.json` | 新增 |
| `services/tatha/.env` | 新增（真值不入库；`.env.example` 补键） |
| `docker/Dockerfile.tatha` | 新增 |
| `compose/docker-compose.yml` | 加 `tatha` 服务 |
| `nginx/nginx.conf` | default server 改为反代 Tatha（§3.3） |
| `.env.example` | 补 `TATHA_DEFAULT_MODEL` / `OPENAI_API_KEY` |
| `docs/` | 记一笔预发入口说明 |

---

## 7. 上机步骤与验收

```bash
# 0) 起服务（预发机）
docker compose -f compose/docker-compose.yml up -d --build tatha
sudo nginx -t && sudo systemctl reload nginx

# 1) 健康检查
curl -s http://<STAGING_HOST>/health

# 2) 根路径重定向
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://<STAGING_HOST>/
# 期望：302 /index.html

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
# http://<STAGING_HOST>/ → 302 → /index.html → 注册 → /demo.html
```

**本机先过一遍**：`bash scripts/dryrun.sh`

---

## 8. 回滚

```bash
git revert <本方案提交>          # 只回 compose / nginx / services
docker compose -f compose/docker-compose.yml up -d --remove-orphans
sudo nginx -t && sudo systemctl reload nginx
```

`looma-backend` 不在改动范围内，域名服务全程不受影响。

---

## 9. 风险与待办

| 项 | 处理 |
|---|---|
| default server 防护被替换 | 预发可接受。若要收紧：加 `allow/deny` 限定来源 IP，或改回 404 + 独立端口（方案 B） |
| **Tatha 仓 Dockerfile 硬编码 DeepSeek 密钥且已入库** | **密钥应视为已泄露，建议轮换**；向上游 `GenzLTD/Tatha` 提 PR 移除并加 `.dockerignore`。本仓 `Dockerfile.tatha` 不继承该 ENV |
| `.chroma-cache` 缺失 | 本仓 Dockerfile 不 COPY 该目录；如人格测评确需，另行挂载模型缓存 |
| Tatha PR #7 未合并 | 起步拷贝要么等 #7 合入 main，要么直接取分支 `feat/mbti-analyze-endpoint-20261014`（`2ed8453`），需在 `SOURCE.json` 写明 |
| 算法三副本漂移 | 不在本方案范围，见 `GenzLTD/planetx-tatha#5` |
| ssh 凭据 | 本地 9 把私钥 + 6 个用户名全部被拒，需授权后才能上机执行 §7 |
