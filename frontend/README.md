# 海外 tspace（本仓发版真源）

`@looma/saas` 打出来的静态站，CI `saas-build` 上传 artifact，`deploy` 第 5 步 rsync 到 `/var/www/saas/dist`。不再手搓 dist 上传。

| | |
|---|---|
| 钉 | [`SOURCE.json`](SOURCE.json)（从 looma-zervi `fef232e` 收进，2026-09-18） |
| 构建 | `bash scripts/build-saas.sh` 或 `cd frontend && pnpm --filter @looma/saas build` |
| 环境 | `VITE_API_BASE=""`（同源 `/v1`）、`VITE_DEPLOY_REGION=SG` |
| 现网路径 | nginx `tspace.genz.ltd` → `/var/www/saas/dist` |
| 不收 | PlanetX、genz-web（Vercel）、小程序 |

产品功能仍先在 `looma-zervi` 合入，再覆盖本目录并改 `SOURCE.json`，然后打新 `stack-v*`。不要两仓各改一坨前端。
