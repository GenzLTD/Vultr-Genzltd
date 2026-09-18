# 契约层（GFCC）

境内一套、海外一套，对齐的是这份协议，不是同一棵代码树。**唯一协议真源就是这里**（写作汇合处 `GenzLTD/gfcc`）。本目录是海外运行时当前认的 Ask / 五端口 / 信号：**可变**（Semver），但一次 `stack-v*` 必须能指到当时生效的那一版。没有它，回滚只能还原文件，不知道协议是哪一版。

`GenzLTD/gfcc` 是协议讨论的汇合处。海外要改字段/枚举/入口，可以先在本仓改 JSON 再回写 gfcc，或先在 gfcc 升版本再拉过来。禁止为迁就某一个后端实现偷偷改语义却不升版本。

| 族 | 当前钉 | 入口 |
|---|---|---|
| Ask + 五端口 + roles + registry | **1.2.0** | `POST /v1/ask` |
| 信号信封 + `signals/*` | **1.0.0** | `POST /v1/signal-ingest` |

钉点见 [`gfcc/SOURCE.json`](gfcc/SOURCE.json)（commit `435c80b8…`，2026-09-18）。

## 本仓认什么 / 不认什么

- **认**：JSON 字段、枚举、`$ref`、五端口默认适配器是 `stub`、围坐不是聊天室、AI 不是表决成员。
- **不认**：把天翼现网、Discord 功能表、或国内微信登录拷进本仓当「必须一致的实现」。海外按管辖接适配器。
- **不写进现行** `nginx/nginx.conf`：`circle.genz.ltd` 片段在 `nginx/sites/`，解开 include 走一次独立 `stack-v*`（环境允许时就可以，不必等境内施工单）。

## 刷新协议版本

1. 改 JSON（本仓或 gfcc，最终两边同号）。
2. 改 `SOURCE.json` 的 `commit` / `families.*.version`。
3. `bash scripts/assert-contracts.sh` 与 `bash scripts/dryrun.sh --static` 全绿。
4. 打 **新** `stack-v*`。旧 tag 不可变。
