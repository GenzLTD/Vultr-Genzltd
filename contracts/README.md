# 契约层（GFCC pin）

本目录是 **L0 契约在本仓的钉**，不是围坐内核、也不是 Discord 产品。

写作真源仍是 `GenzLTD/gfcc`。本仓只保存一份可发版、可回滚的快照：某个 `stack-vX.Y.Z` 当时认哪一版 Ask / 五端口 / 信号。没有这份钉，自动化打 tag 只能对「文件长什么样」负责，对「协议是什么」无法负责。

| 族 | 当前钉 | 入口 |
|---|---|---|
| Ask + 五端口 + roles + registry | **1.2.0** | `POST /v1/ask` |
| 信号信封 + `signals/*` | **1.0.0** | `POST /v1/signal-ingest` |

钉点见 [`gfcc/SOURCE.json`](gfcc/SOURCE.json)（commit `435c80b8…`，2026-09-18）。

## 本仓认什么 / 不认什么

- **认**：JSON 字段、枚举、`$ref`、五端口默认适配器是 `stub`、围坐不是聊天室、AI 不是表决成员。
- **不认**：把 `gfcc` 内核进程、天翼 `:5211` 现网、或 Discord 功能表拷进本仓当实现。海外适配先把契约和 Host 片段收进版本，再在后续 tag 里接适配器。
- **不写进现行** `nginx/nginx.conf`：`circle.genz.ltd` 片段在 `nginx/sites/`，解开 include 必须是一次独立的 `stack-v*`，不能手改现网。

## 刷新钉

1. 在 `gfcc` 仓取出新 commit（先过那边的契约 Semver）。
2. 覆盖 `contracts/gfcc/*.json` 与 `signals/`。
3. 改 `SOURCE.json` 的 `commit` / `families.*.version`。
4. `bash scripts/assert-contracts.sh` 与 `bash scripts/dryrun.sh --static` 全绿。
5. `bash scripts/release-tag.sh X.Y.Z` 打 **新** `stack-v*`。旧 tag 不可变。

禁止为迁就某个后端实现倒改这份 JSON。要改协议，回 `gfcc` 升版本，再钉过来。
