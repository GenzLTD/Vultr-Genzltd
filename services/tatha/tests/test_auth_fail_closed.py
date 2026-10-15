"""auth.verify_token 的 fail-closed 回归测试。

背景（安全项）：旧实现是

    ctx = _verify_token_remote(token)
    if ctx is not None:
        return ctx
    return _verify_token_stub(token)      # ← 远程失败也回落 stub

即 fail-open：只要量子认证服务抖动（非 200 / 超时 / 缺 user_id / 异常），
任意伪造 token 都能通过鉴权并拿到 `stub-xxx` 身份 + free 档。

修复后：已配置 QUANTUM_AUTH_URL → 失败必须返回 None（→ 401），
只有「未配置」才走开发 stub。

本文件锁定这两条边界，防止改回 fail-open。
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tatha.api.auth import verify_token


class _QuantumStubHandler(BaseHTTPRequestHandler):
    """本地量子认证桩：状态码与响应体由测试改写。"""

    status = 200
    payload = {"user_id": "u-remote", "tier": "pro"}

    def do_GET(self):  # noqa: N802 - http.server 约定
        self._reply()

    def do_POST(self):  # noqa: N802 - http.server 约定
        self._reply()

    def _reply(self):
        body = json.dumps(type(self).payload).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静音，避免污染测试输出
        pass


@pytest.fixture
def quantum(monkeypatch):
    """起一个本地量子认证桩，并把 QUANTUM_AUTH_URL 指向它。"""
    server = HTTPServer(("127.0.0.1", 0), _QuantumStubHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("QUANTUM_AUTH_URL", f"http://127.0.0.1:{port}/verify")
    monkeypatch.setattr(_QuantumStubHandler, "status", 200)
    monkeypatch.setattr(_QuantumStubHandler, "payload", {"user_id": "u-remote", "tier": "pro"})
    yield server
    server.shutdown()
    server.server_close()


def test_unconfigured_uses_dev_stub(monkeypatch):
    """未配置 QUANTUM_AUTH_URL → 走开发 stub（保留本地/联调便利）。"""
    monkeypatch.delenv("QUANTUM_AUTH_URL", raising=False)
    ctx = verify_token("demo-token-123")
    assert ctx is not None
    assert ctx.user_id.startswith("stub-")
    assert ctx.tier == "free"


def test_configured_remote_ok_returns_real_identity(quantum):
    """已配置且认证服务 200 → 返回真身份，不经过 stub。"""
    ctx = verify_token("a-real-token")
    assert ctx is not None
    assert ctx.user_id == "u-remote"
    assert ctx.tier == "pro"


def test_configured_remote_unreachable_is_fail_closed(monkeypatch):
    """已配置但认证服务不可达 → None（401），绝不回落 stub。"""
    monkeypatch.setenv("QUANTUM_AUTH_URL", "http://127.0.0.1:1/verify")  # 必然拒绝连接
    assert verify_token("forged-token") is None


def test_configured_non_200_is_fail_closed(quantum, monkeypatch):
    """已配置但认证服务非 200 → None，绝不回落 stub。"""
    monkeypatch.setattr(_QuantumStubHandler, "status", 401)
    assert verify_token("forged-token") is None


def test_configured_missing_user_id_is_fail_closed(quantum, monkeypatch):
    """已配置但响应缺 user_id → None，绝不回落 stub。"""
    monkeypatch.setattr(_QuantumStubHandler, "payload", {"tier": "pro"})
    assert verify_token("forged-token") is None


def test_configured_timeout_is_fail_closed(monkeypatch):
    """已配置但认证服务超时 → None，绝不回落 stub。"""
    server = HTTPServer(("127.0.0.1", 0), _QuantumStubHandler)
    port = server.server_address[1]
    blocker = threading.Event()

    class _SlowHandler(_QuantumStubHandler):
        def _reply(self):
            blocker.wait(10)  # 不返回，制造超时

    server.RequestHandlerClass = _SlowHandler
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("QUANTUM_AUTH_URL", f"http://127.0.0.1:{port}/verify")
    try:
        assert verify_token("forged-token") is None
    finally:
        blocker.set()
        server.shutdown()
        server.server_close()
