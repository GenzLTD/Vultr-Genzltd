#!/usr/bin/env python3
"""
Standalone JWT verification for MCP Sidecar.
No Flask dependencies — reads secrets directly from environment.
"""
from __future__ import annotations

import logging
import os

import jwt as pyjwt

logger = logging.getLogger("looma.mcp.auth")


class MCPAuthError(Exception):
    """Raised when MCP token verification fails."""


class MCPForbiddenError(MCPAuthError):
    """Raised when user tier is insufficient."""


def _get_jwt_config() -> dict[str, str]:
    """Read JWT config from env (mirrors backend/src/config.py defaults)."""
    return {
        "secret": os.getenv(
            "JWT_SECRET",
            "looma-zervi-default-jwt-secret-change-in-production-2026",
        ),
        "algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
    }


def verify_bearer_token(token: str) -> dict:
    """
    Verify a looma JWT bearer token.

    Returns the decoded payload dict containing at least {"sub": user_id, "tier": str}.

    Raises:
        MCPAuthError: invalid or missing token
    """
    if not token or not token.strip():
        raise MCPAuthError("Missing authentication token")

    cfg = _get_jwt_config()
    try:
        payload = pyjwt.decode(
            token.strip(),
            cfg["secret"],
            algorithms=[cfg["algorithm"]],
            issuer="looma",
        )
    except pyjwt.ExpiredSignatureError:
        raise MCPAuthError("Token has expired")
    except pyjwt.InvalidTokenError as e:
        raise MCPAuthError(f"Invalid token: {e}")

    if "sub" not in payload:
        raise MCPAuthError("Token missing 'sub' field")

    return payload


def verify_bearer_token_inline(
    token: str,
    user_id: str | None = None,
    require_db_user: bool = False,
) -> dict:
    """
    Convenience wrapper: verify token, optionally check user_id consistency.

    Parameters
    ----------
    token : str
        Looma JWT bearer token.
    user_id : str | None
        If provided, cross-check against token 'sub'.
    require_db_user : bool
        If True, also verify the user exists in the DB (aligns with require_auth).

    Returns the decoded payload.

    Raises:
        MCPAuthError: verification failed
        MCPForbiddenError: user not found in DB
    """
    payload = verify_bearer_token(token)

    # If caller provides a user_id, validate it matches the token
    if user_id and payload["sub"] != user_id:
        raise MCPAuthError(
            f"Token subject ({payload['sub']}) does not match user_id ({user_id})"
        )

    # Optional DB user existence check (aligns with require_auth)
    if require_db_user:
        uid = payload["sub"]
        try:
            if not _user_exists_in_db(uid):
                raise MCPForbiddenError(
                    f"User '{uid}' not found in database — please register first"
                )
        except MCPForbiddenError:
            raise
        except Exception as e:
            logger.warning(f"DB user check skipped (DB unavailable): {e}")

    return payload


def _user_exists_in_db(user_id: str) -> bool:
    """Check if a user exists in the looma database.
    
    Uses sqlite3 directly (no Flask app context needed for MCP sidecar).
    """
    import sqlite3
    import os

    db_path = os.getenv(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(__file__), "..", "data", "looma.db"),
    )
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        logger.warning(f"_user_exists_in_db failed: {e}")
        raise
