"""memory.recall 的入口处理（POST /v1/ask · context.port_hint=memory）。

这一刀只接 recall（契约 ``min_role: observer``、``scope: memory.read``）：
    * 入口仍是单入口 ``POST /v1/ask``，不新增 ``/memory/*`` 路由
    * 不提供 remember（需要 ``participant``，本次不授予），``put`` / ``supersede`` 不挂入口
    * 身份只认请求头 ``X-Actor-Sub``（原始 claims.sub），不读 body、不读 ``X-User-Id``

为什么显式 ``port_hint`` 而不是靠自然语言意图：用户输入一句话时由 LLM 猜「这是不是想回忆」
会把身份端口和记忆端口的边界交给概率模型；第一刀用调用方声明的端口，行为可预测。
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .gfcc_store import (
    DEFAULT_LIMIT,
    LIBRARIES,
    InvalidLibrary,
    StoreUnavailable,
    query,
)

PORT = "memory"


def _opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_limit(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def handle_recall(request: Any, actor_sub: str | None) -> dict[str, Any]:
    """执行 memory.recall，返回 ``/v1/ask`` 的 ``result`` 字段。

    ``actor_sub`` 缺失 → 401（契约：``missing_sub: 401``，不得降级为匿名读取）。
    """
    actor = (actor_sub or "").strip()
    if not actor:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "missing_actor_sub",
                "message": "memory 端口需要 X-Actor-Sub 头（原始 claims.sub），缺失即拒绝（不降级为匿名读取）",
            },
        )

    context = getattr(request, "context", None) or {}
    library = _opt_text(context.get("library"))
    circle_id = _opt_text(context.get("circle_id"))
    limit = _as_limit(context.get("limit"))
    include_superseded = bool(context.get("include_superseded"))

    if library is not None and library not in LIBRARIES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_library",
                "message": f"library={library} 不在七库枚举内",
                "library_enum": list(LIBRARIES),
            },
        )

    try:
        records = query(
            actor_sub=actor,
            library=library,
            circle_id=circle_id,
            limit=limit,
            include_superseded=include_superseded,
        )
    except InvalidLibrary as e:
        raise HTTPException(status_code=422, detail={"code": "invalid_library", "message": str(e)})
    except StoreUnavailable as e:
        # 库不可用是「能力暂时不可用」，不是「没有记忆」。这两者混在一起会让调用方
        # 把故障当空结果，所以 status=error 且 records=[] 明确区分。
        return {
            "status": "error",
            "message": "gfcc 记忆库不可用",
            "error": str(e),
            "library": library,
            "circle_id": circle_id,
            "count": 0,
            "records": [],
        }

    if not records:
        # 空结果按契约是成功：先写这条记忆的人才会有记录，读空不算失败。
        return {
            "status": "ok",
            "message": "没有匹配的记忆",
            "library": library,
            "circle_id": circle_id,
            "count": 0,
            "records": [],
        }

    return {
        "status": "ok",
        "message": f"回忆到 {len(records)} 条记忆",
        "library": library,
        "circle_id": circle_id,
        "count": len(records),
        "records": records,
    }
