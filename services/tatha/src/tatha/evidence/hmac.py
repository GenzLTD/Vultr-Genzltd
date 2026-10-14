"""Guibu ↔ Tatha 信号桥 HMAC-SHA256 签名 / 验签。

约定：
- 签名头：``X-Signature``
- 签名串：对**原始请求体字节**做 ``HMAC-SHA256(SIGNAL_BRIDGE_SECRET, raw_body)``，hex 输出
- 验签用 ``hmac.compare_digest`` 恒定时间比对，防时序侧信道
"""
from __future__ import annotations

import hashlib
import hmac


def sign_body(secret: str, body: bytes) -> str:
    """对 raw body 计算 HMAC-SHA256 hex 摘要。"""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """恒定时间比对 X-Signature；signature 为空或不一致返回 False。"""
    if not signature:
        return False
    expected = sign_body(secret, body)
    return hmac.compare_digest(expected, signature.strip())
