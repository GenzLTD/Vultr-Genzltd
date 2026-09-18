# 上游提案：`deploy-overseas.yml` 的 `.env` 改为「仅首次种入」

> 目标仓：`GenzLTD/looma-zervi`　文件：`.github/workflows/deploy-overseas.yml`
> 性质：**提案，未提交**。本仓不改产品仓代码。

## 问题

bootstrap 步骤里有一个 `set_kv` 函数，且在 `.env` 已存在时**每次发版都执行一遍**：

```bash
set_kv STRIPE_SECRET_KEY  "${{ secrets.ENV_STRIPE_SECRET_KEY }}"
set_kv STRIPE_WEBHOOK_SECRET "${{ secrets.ENV_STRIPE_WEBHOOK_SECRET }}"
# … 共约 20 个键
```

`set_kv` 只在**值为空**时 `return 0`。因此只要仓级 secret 非空，
**每次 tag 发版都会把 secret 里的值写回机器 `.env`**。

后果（2026-09-17 实际发生过）：Stripe Dashboard 的 Live 签名密钥与机器 `.env` 不一致，
订单卡在 pending、用户不升档；而"改机器不改 secret"，会在下次发版被静默回滚。

## 提案（照 szbolent-cn 的成功实践）

把 Stripe 等**运行时真值**从"每轮重写"改为"**仅缺失时补齐**"：

```diff
-          set_kv STRIPE_SECRET_KEY "${{ secrets.ENV_STRIPE_SECRET_KEY }}"
-          set_kv STRIPE_WEBHOOK_SECRET "${{ secrets.ENV_STRIPE_WEBHOOK_SECRET }}"
+          # 仅当键缺失时补齐；已存在则不动（防发版回滚线上密钥）
+          seed_kv STRIPE_SECRET_KEY "${{ secrets.ENV_STRIPE_SECRET_KEY }}"
+          seed_kv STRIPE_WEBHOOK_SECRET "${{ secrets.ENV_STRIPE_WEBHOOK_SECRET }}"
```

并新增函数：

```bash
seed_kv() {
  local key="$1" val="$2"
  [ -n "${val}" ] || return 0
  grep -q "^${key}=" "${ENV_FILE}" && return 0    # 已存在 → 永不覆盖
  echo "${key}=${val}" >> "${ENV_FILE}"
}
```

## 范围建议

- **改为 `seed_kv`**（运行时真值，机器是权威）：`STRIPE_SECRET_KEY`、`STRIPE_WEBHOOK_SECRET`、
  `JWT_SECRET`、`QCC_AUTH_TOKEN`、`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、
  `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`。
- **保持 `set_kv`**（每轮收敛的配置，无秘密）：`FLASK_PORT`、`CHROMA_*`、`CORS_ORIGINS`、
  `DEPLOY_REGION`、`RATE_LIMIT_STORAGE_URI`、`STRIPE_SUCCESS_URL`、`STRIPE_CANCEL_URL` 等。

## 验收

- 连续两次 tag 发版后，机器 `.env` 的 `sha256` 前缀**逐字节不变**（除非主动轮换）。
- `grep -c '^STRIPE_WEBHOOK_SECRET=' .env` 始终 1，且值未被 CI 改写。
