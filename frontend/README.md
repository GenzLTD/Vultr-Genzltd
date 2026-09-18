# 海外 tspace（本仓发版真源）

`@looma/saas` 打出来的静态站，CI `saas-build` 上传 artifact，`deploy` 第 5 步 rsync 到 `/var/www/saas/dist`。不再手搓 dist 上传。

| | |
|---|---|
| 起步拷贝 | [`SOURCE.json`](SOURCE.json)（从 looma-zervi `fef232e` 收进，2026-09-18） |
| 构建 | `bash scripts/build-saas.sh` 或 `cd frontend && pnpm --filter @looma/saas build` |
| 环境 | `VITE_API_BASE=""`（同源 `/v1`）、`VITE_DEPLOY_REGION=SG` |
| 现网路径 | nginx `tspace.genz.ltd` → `/var/www/saas/dist` |
| 本仓不收 | PlanetX 小程序壳、genz-web（Vercel 营销站） |

海外 tspace 以本目录为真源，按管辖改（Stripe、海外会话、同源 `/v1`）。不必等 `looma-zervi` 先合再覆盖。国内站若要同一交互，按 GFCC / 产品需要自己适配。起步拷贝只记录分叉从哪来，不是以后每次发版的闸门。
