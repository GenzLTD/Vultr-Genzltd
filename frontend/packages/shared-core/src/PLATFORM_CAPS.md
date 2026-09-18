# 平台能力矩阵 (Platform Capabilities Matrix)

## 概述
本文档记录了Looma-Zervi多端应用的平台能力差异和契约一致性状态。

## 当前状态（2026-07-06）

### Ask API契约一致性

| 端 | 客户端实现 | 期望 | 后端实现 | 状态 | 影响 |
|----|-----------|------|----------|------|------|
| **小程序** | `createChatApi().ask()` | JSON一次返回 | `jsonify(...)` | ✅ 一致 | 无问题 |
| **SaaS (B端)** | `useChatNonStreaming` → `createChatApi().ask()` | JSON一次返回 | `jsonify(...)` | ✅ 一致 | P0 已修复（2026-07-06） |
| **shared-core Web** | `createChatApi().askStream()` | SSE流式 | 未实现stream路由 | ⏸️ 规划中 | P2；内测使用非流式 ask |

### 解决方案

#### 短期方案（P0 - 内测前）✅ 已完成
1. **统一为非流式JSON**
   - SaaS 已改用 `useChatNonStreaming` + `createChatApi().ask()`
   - 与小程序一致

2. **实现真SSE**（工作量大）
   - 后端实现 `/v1/ask/stream` 端点
   - 更新shared-core的 `askStream()` 实现
   - 需要改造现有缓存逻辑

#### 中期方案（P1 - 内测并行）
1. **移植LLM分支的缓存机制**
   - `llm_cache.py`（LRU + TTL）
   - provider fallback策略
   - 熔断机制

2. **API契约对齐**
   - 更新 `docs/api.yaml` v1.1.0
   - 明确stream/非stream接口

#### 长期方案（P2 - 内测后）
1. **真SSE实现**
2. **异步队列**（Redis/Celery）
3. **Rust contracts复用**

## 平台特定能力

### Web平台（PlanetX + SaaS）
```typescript
// 能力矩阵
const PLATFORM_CAPS_WEB = {
  // API支持
  api: {
    ask: true,          // ✅ JSON非流式
    askStream: false,   // ❌ SSE流式（后端未实现）
    auth: true,         // ✅ JWT认证
    quota: true,        // ✅ 配额管理
    consent: true,      // ✅ 用户授权
  },
  // UI特性
  ui: {
    realtime: true,     // ✅ WebSocket/SSE
    fileUpload: true,   // ✅ 文件上传
    richText: true,     // ✅ 富文本编辑
  },
  // 存储
  storage: {
    localStorage: true,  // ✅ 本地存储
    indexedDB: true,    // ✅ 索引数据库
  }
};
```

### 小程序平台
```typescript
const PLATFORM_CAPS_MINI = {
  // API支持
  api: {
    ask: true,          // ✅ JSON非流式
    askStream: false,   // ❌ 不支持SSE
    auth: true,         // ✅ 微信登录
    quota: true,        // ✅ 配额管理
    consent: true,      // ✅ 用户授权
  },
  // UI特性
  ui: {
    realtime: false,    // ❌ 不支持WebSocket
    fileUpload: true,   // ✅ 文件上传（有限制）
    richText: false,    // ❌ 富文本有限
  },
  // 存储
  storage: {
    wxStorage: true,    // ✅ 微信存储
    cloudStorage: true, // ✅ 云存储
  }
};
```

## 性能指标（SLO目标）

| 指标 | 目标值 | 当前状态 | 备注 |
|------|--------|----------|------|
| Ask p95 (nocache, VU≤5) | < 8s | 待测试 | DeepSeek ~3s avg (LLM分支) |
| Ask p95 (cache hit) | < 500ms | 待测试 | 120s TTL缓存 |
| 错误率 | < 5% | 待测试 | 不含预期429 |
| 并发用户数 | ≥ 10 | 待测试 | gunicorn多worker |

## 部署建议

### 开发环境
```bash
# Flask开发服务器（单进程）
cd backend && ./dev.sh
```

### 内测环境
```bash
# gunicorn多进程（建议≥4 workers）
cd backend && ./start_gunicorn.sh

# 监控
ps aux | grep gunicorn
curl http://localhost:5200/health
```

### 生产环境
```bash
# systemd服务 + 监控
sudo systemctl start looma-backend

# 反向代理 (Nginx)
# 负载均衡 + SSL + 限流
```

## 迁移路径

### 从假SSE迁移到非流式JSON
1. SaaS: `useChat` → `useChatNonStreaming`
2. 更新Chat组件导入
3. 验证功能完整性

### 从非流式迁移到真SSE
1. 后端: 实现 `/v1/ask/stream` 端点
2. shared-core: 完善 `askStream()` 实现
3. SaaS: 切换回流式（可选）
4. 性能测试

## 测试验证

### 契约一致性测试
```bash
# 1. 验证各端API调用
./scripts/test-platform-caps.sh

# 2. 并发测试
python3 scripts/concurrency_test.py --concurrency 10 --requests 100

# 3. k6压测
k6 run scripts/k6_ask_test_nocache.js --vus 5 --duration 30s
```

### 功能回归测试
```bash
# 1. 小程序Ask流程
npm run dev:mini

# 2. SaaS Ask流程（非流式）
npm run dev:saas

# 3. PlanetX Ask流程
npm run dev:planetx
```

## 版本记录

### v1.0.0（当前）
- ✅ 小程序：JSON非流式
- ⚠️ SaaS：假SSE → 改为非流式（P0）
- ❌ shared-core Web：askStream未实现

### v1.1.0（内测目标）
- ✅ 所有平台：JSON非流式统一
- ✅ 性能：gunicorn多worker
- ✅ 缓存：LLM层缓存移植

### v1.2.0（内测后）
- ✅ 真SSE流式支持
- ✅ 异步队列
- ✅ 高级熔断机制

## 责任人

| 组件 | 负责人 | 状态 |
|------|--------|------|
| SaaS useChat迁移 | Jason | ✅ P0完成 |
| gunicorn配置 | Jason | ✅ P0完成 |
| k6压测脚本 | Jason | ✅ P0完成 |
| LLM缓存移植 | 待分配 | P1 |
| API契约对齐 | 待分配 | P1 |
| 真SSE实现 | 待分配 | P2 |