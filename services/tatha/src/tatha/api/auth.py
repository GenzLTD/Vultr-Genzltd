"""
V1 认证：从请求头取 token，调量子认证校验（或 stub），将 user_id、tier 注入请求上下文。

与 docs/量子认证接口约定_V1.md 一致。

安全约定（fail-closed）：
- 配置了 QUANTUM_AUTH_URL → 远程校验失败（非 200 / 超时 / 缺 user_id / 异常）
  必须返回 None（→ 401），**绝不回落 stub**。
- 未配置 QUANTUM_AUTH_URL → 才走开发 stub（任意 token 视为 free 档），并打 warning。

旧实现是「远程失败也回落 stub」，属于 fail-open：认证服务一抖动，任意伪造 token
即可通过鉴权并拿到 stub-xxx 身份。禁止回到该行为。
"""
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

from fastapi import Header, HTTPException

logger = logging.getLogger("tatha.auth")

# 认证调用超时：抖动窗口越短越好（配合 fail-closed）
AUTH_TIMEOUT_SEC = 3

Tier = Literal["free", "basic", "pro"]


@dataclass
class AuthContext:
    """请求上下文中的用户身份与档位，供业务与配额使用。"""
    user_id: str
    tier: Tier


def get_bearer_token(authorization: str | None = Header(None, alias="Authorization")) -> str | None:
    """从请求头取出 Bearer token；无头或格式不对返回 None。"""
    if not authorization or not isinstance(authorization, str):
        return None
    auth = authorization.strip()
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    return token if token else None


_STUB_WARNED = False


def _verify_token_stub(token: str) -> AuthContext:
    """Stub：任意非空 token 视为 free 档，user_id 由 token 派生。

    仅在未配置 QUANTUM_AUTH_URL 时调用；首次调用打 warning，
    避免运维误以为「有认证」——这与 fail-open 是同一类静默降级。
    """
    global _STUB_WARNED
    if not _STUB_WARNED:
        logger.warning(
            "QUANTUM_AUTH_URL 未配置：鉴权走开发 stub，任意非空 token 视为 free 档（禁止用于生产）"
        )
        _STUB_WARNED = True
    safe = re.sub(r"[^a-zA-Z0-9\-]", "", token[:32]) or "anon"
    return AuthContext(user_id=f"stub-{safe}", tier="free")


def _verify_token_remote(token: str) -> AuthContext | None:
    """调用量子认证服务校验 token；失败或非 200 返回 None。"""
    url = os.environ.get("QUANTUM_AUTH_URL", "").strip()
    if not url:
        return None
    try:
        import urllib.request
        import json
        # 文档称 GET/POST 均可，实现按可配置方法发起，默认 GET（不改变现有行为）
        method = os.environ.get("QUANTUM_AUTH_METHOD", "GET").strip().upper() or "GET"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=AUTH_TIMEOUT_SEC) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode())
            user_id = data.get("user_id")
            tier_raw = (data.get("tier") or "free").lower()
            tier: Tier = "free" if tier_raw not in ("basic", "pro") else tier_raw
            if not user_id:
                return None
            return AuthContext(user_id=str(user_id), tier=tier)
    except Exception:
        return None


def verify_token(token: str) -> AuthContext | None:
    """校验 token。

    fail-closed：一旦配置了 QUANTUM_AUTH_URL，远程校验失败（非 200 / 超时 /
    缺 user_id / 异常）一律返回 None（由 get_auth 转 401），**绝不回落 stub**。
    只有「未配置」才走开发 stub——保留本地/联调便利，但不给生产留后门。
    """
    if os.environ.get("QUANTUM_AUTH_URL", "").strip():
        ctx = _verify_token_remote(token)
        if ctx is None:
            logger.warning("量子认证校验失败，拒绝请求（fail-closed，不回落 stub）")
        return ctx
    return _verify_token_stub(token)


def get_auth(authorization: str | None = Header(None, alias="Authorization")) -> AuthContext:
    """
    依赖项：从请求头取 token，校验后返回 AuthContext；无 token 或校验失败抛出 401。
    用于需要鉴权的路由：/v1/ask、/v1/jobs/match、/v1/documents/convert、/v1/rag/query。
    """
    token = get_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing or invalid authorization")
    ctx = verify_token(token)
    if ctx is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return ctx
