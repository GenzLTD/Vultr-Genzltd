"""memory 端口的 gfcc 存储读取层（只读）。

契约真源：GenzLTD/gfcc@3dcb084 ``contracts/memory.v1.json``（1.3.0）
    * ``store_slot.link = actor_sub``
    * ``optional_adapters`` 含 ``gfcc``：「pgvector 库 gfcc。与 cortex-mcp 只通过 actor_sub 关联。」
    * ``recall`` = ``scope: memory.read`` / ``min_role: observer``

本模块只做 **recall 的读取面**（``store.query``）：
    * 不实现 ``put`` / ``supersede``（这一刀不授予 remember，写入口不挂）
    * 不装 vector 扩展、不做向量检索：按 ``actor_sub``（+ 可选 ``library`` / ``circle_id``）
      精确查询、按 ``observed_at`` 倒序返回

隔离红线（来自契约「get/query 无 circle_id 时必须 actor_sub，防跨人读」）：
    * ``actor_sub`` 一律必填，绝不省略
    * 只有在显式给 ``circle_id`` 时才把同围坐的记录纳入（``actor_sub = ? OR circle_id = ?``）

``actor_sub`` 语义（2026-10-18 已定）：**原始 claims.sub**，由网关放入 ``X-Actor-Sub`` 头。
它与 ``X-User-Id = sha256(sub)``（配额与既有 Tatha 身份用）是两个并存的键，**不互相替换**。
"""

from __future__ import annotations

import os
from typing import Any

# 七库：与契约 library_enum 完全一致；注意 methodology_value（不是 method）
LIBRARIES: tuple[str, ...] = (
    "issue",
    "action",
    "event",
    "methodology_value",
    "person",
    "org",
    "resource",
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
STATEMENT_TIMEOUT_MS = 3000
CONNECT_TIMEOUT_SEC = 3

_SELECT_COLUMNS = (
    "id::text AS id, library, record_type, circle_id, body, refs, "
    "observed_at, observed_by, ai_source, superseded_at, actor_sub, created_at"
)


class StoreUnavailable(RuntimeError):
    """gfcc 库不可达或未配置（DSN 为空 / 连接失败 / 超时）。"""


class InvalidLibrary(ValueError):
    """library 不在七库枚举内。"""


def dsn() -> str:
    """gfcc 库连接串；未配置返回空串（此时 memory 端口不可用，但进程照常启动）。"""
    return (os.getenv("GFCC_DB_DSN") or "").strip()


def is_configured() -> bool:
    return bool(dsn())


def _clamp_limit(limit: Any) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _iso(value: Any) -> str | None:
    """timestamptz → ISO8601 字符串；None 原样返回。"""
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)


def query(
    actor_sub: str,
    library: str | None = None,
    circle_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    """按 ``actor_sub`` 读取记忆记录。

    Args:
        actor_sub: 原始 claims.sub，必填非空。
        library: 七库之一；None 表示不按库过滤。
        circle_id: 围坐标识；给定后同围坐的记录也纳入（与本人记录去重后一起返回）。
        limit: 返回条数，1..100，默认 20。
        include_superseded: 是否返回已被 supersede 的旧记录（默认不返回）。

    Returns:
        list[dict]，按 ``observed_at`` 倒序；无命中返回 ``[]``（空结果不是错误）。

    Raises:
        ValueError: ``actor_sub`` 为空。
        InvalidLibrary: ``library`` 不在七库枚举内。
        StoreUnavailable: DSN 未配置或库不可达。
    """
    actor = (actor_sub or "").strip()
    if not actor:
        raise ValueError("actor_sub 不能为空")

    lib = (library or "").strip() or None
    if lib is not None and lib not in LIBRARIES:
        raise InvalidLibrary(f"library={lib} 不在七库枚举内（{', '.join(LIBRARIES)}）")

    circle = (circle_id or "").strip() or None
    limit_n = _clamp_limit(limit)

    conninfo = dsn()
    if not conninfo:
        raise StoreUnavailable("GFCC_DB_DSN 未配置：memory 端口不可用")

    # 参数一律显式 ::type 转换：%(library)s / %(circle_id)s 可能是 NULL，
    # 不标类型时 PG 会报 "could not determine data type of parameter"。
    sql = f"""
        SELECT {_SELECT_COLUMNS}
          FROM public.memory_record
         WHERE (%(library)s::text IS NULL OR library = %(library)s::text)
           AND (%(include_superseded)s::boolean OR superseded_at IS NULL)
           AND (actor_sub = %(actor_sub)s::text
                OR (%(circle_id)s::text IS NOT NULL AND circle_id = %(circle_id)s::text))
         ORDER BY observed_at DESC
         LIMIT %(limit)s
    """
    params = {
        "library": lib,
        "include_superseded": bool(include_superseded),
        "actor_sub": actor,
        "circle_id": circle,
        "limit": limit_n,
    }

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:  # pragma: no cover - 镜像缺依赖时给出可读原因
        raise StoreUnavailable(f"psycopg 未安装：{e}") from e

    try:
        with psycopg.connect(
            conninfo,
            connect_timeout=CONNECT_TIMEOUT_SEC,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
            row_factory=dict_row,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except StoreUnavailable:
        raise
    except Exception as e:  # 连接/查询失败统一归一，调用方据此返回 error 而非 500 堆栈
        raise StoreUnavailable(f"gfcc 库查询失败：{e}") from e

    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["refs"] = list(item.get("refs") or [])
        for key in ("observed_at", "superseded_at", "created_at"):
            item[key] = _iso(item.get(key))
        out.append(item)
    return out
