# 技能证据摄入（skill-proof）与简历增强

Guibu 微课产出「技能掌握证据」，经 `POST /v1/skills/ingest` 落入 Tatha 的 `skills_evidence` 表；
`POST /v1/jobs/match` 传入 `user_id_hash` 时，匹配前按证据增强简历（打 `verified` + 证据引用）。

## 契约单一来源

`payload` 遵循 **Guibu 真源契约**：

- 真源：`guibu/contracts/skill-proof.v1.json`
- 副本：本仓 `contracts/skill-proof.v1.json`（claw 工具端同样引用此 schema）

三仓防漂移约定：

1. 字段变更**先改 Guibu 真源**，再同步本仓副本与 claw。
2. Tatha 侧的 Pydantic 模型 `tatha.evidence.schemas.SkillProofPayload` 与契约字段一一对齐，
   摄入端点以该模型做运行时校验。
3. 若契约 `required` 或字段类型变化，务必同步更新 `SkillProofPayload`，并补一条用例到
   `tests/test_evidence.py`。

## 摄入端点

```
POST /v1/skills/ingest
```

### 信封（JSON body）

```json
{
  "signal_type": "skill_proof",
  "user_id_hash": "<sha256(email.lower().trim()) 64 位 hex>",
  "nonce": "<客户端生成的唯一值，如 uuid4 hex>",
  "payload": { "...skill-proof.v1 完整对象..." }
}
```

### HMAC 验签

- 请求头：`X-Signature`
- 算法：`HMAC-SHA256(SIGNAL_BRIDGE_SECRET, raw_body)`，hex 小写输出
- `SIGNAL_BRIDGE_SECRET` 为 Guibu ↔ Tatha 共享密钥：
  - **已配置** → 强制验签，失败返回 `401 {code: invalid_signature}`
  - **未配置** → dev 免签模式，`verified=false`（仅本地冒烟）

### 幂等

唯一键 `(signal_type, user_id_hash, nonce)`，见 `skills_evidence` 表 UNIQUE 约束：

- 首次摄入 → `200 {status: "stored", evidence_id, evidence_count, skill_tags, verified}`
- 重复摄入 → `200 {status: "duplicate", ...}`（返回已有 `evidence_id`）

### 校验失败

| 场景 | 状态码 | code |
| --- | --- | --- |
| 验签失败 | 401 | invalid_signature |
| 信封/payload 不符合契约 | 422 | invalid_envelope |
| signal_type 非 skill_proof | 422 | unsupported_signal |
| user_id_hash ≠ payload.user_id | 422 | user_id_mismatch |

## 简历增强（resume_enhancer）

`POST /v1/jobs/match` 的 `user_id_hash` 字段传入时：

1. 按 `user_id_hash` 聚合 `skills_evidence` 全部证据，按 `skill` 去重成 `verified_skills`。
2. 生成「已验证技能 + 证据引用」文本块注入简历末尾（标注非自述、带 source/excerpt 溯源）。
3. LLM 打分因此能区分「自述技能」与「有证据支撑的技能」。

增强失败（无证据 / 存储异常）**不阻断匹配**，原样用原始简历打分。

响应新增 `verified_skills` 字段（仅当传了 `user_id_hash` 时返回），供验收对照：

```
同一简历：无证明 vs 有证明 → JobMatchScore 不降 + 技能命中率（skills_overlap）上升
```

## 验收脚本（可复跑证据）

`scripts/eval_skill_proof.py` 黑盒对照真实 `:8010` 端点，验证上面的「无证明 vs 有证明」口径：

```bash
cd Tatha
SIGNAL_BRIDGE_SECRET=change-me-shared-secret \
  uv run python scripts/eval_skill_proof.py
```

- 流程：同简历 + 同 `user_id_hash`，先跑 A（无证据 match）→ ingest 一条 skill-proof → 再跑 B（有证据 match），对比指标。
- `SIGNAL_BRIDGE_SECRET`：与 Guibu 共享密钥一致则走 HMAC 验签；缺省走 dev 免签模式。
- 退出码：`0`=PASS（桥接注入成功 + 蒸馏体现到分数），`1`=FAIL（区分「桥接」证据未注入 vs「蒸馏」分数未体现），`2`=SKIP（LLM 不可用）。
- 前置：需 Tatha `:8010` 在线 + 真实 LLM Key；缺 LLM 时明确 SKIP，不判 PASS/FAIL，避免假绿。
- 可选 `--user-email` 固定复现同一 hash；默认每次运行换随机 hash + 随机 token（stub free 档每日 3 次 match，A+B 共 2 次）。

## 存储

`skills_evidence`（SQLite，标准库 sqlite3，无新依赖）：

| 字段 | 说明 |
| --- | --- |
| id | 自增主键 |
| signal_type | 信号类型（Phase 1 = skill_proof） |
| user_id_hash | 跨平台关联键 |
| nonce | 幂等键 |
| payload | 完整 skill-proof.v1 JSON |
| skill_tags | JSON 数组（去重查询冗余列） |
| evidence_count | evidence 条数 |
| generated_at / created_at | 时间戳 |

默认路径 `.data/skills_evidence.db`（`.data/` 已 gitignore），可用 `TATHA_EVIDENCE_DB` 覆盖。
