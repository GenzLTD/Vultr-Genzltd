# nginx Host 片段

现行生产配置仍是整文件 [`../nginx.conf`](../nginx.conf)（api + tspace，无裸域）。

| 文件 | 状态 | 何时进真机 |
|---|---|---|
| `circle.genz.ltd.conf` | 仓内期望片段 | 未来某次 `stack-v*` 解开 `nginx.conf` 里的 include，且 kernel `:5211` 已在本机 |

片段进仓是为了让 **tag 能版本化 Host 契约**，不是把天翼现网或 Discord 产品搬过来。
