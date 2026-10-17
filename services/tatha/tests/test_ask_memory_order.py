"""/v1/ask 的 memory 分支顺序契约：身份校验先于配额扣减。

回归背景：consume() 曾在 handle_recall 抛 401 missing_actor_sub 之前执行，
缺 X-Actor-Sub 的探测请求也会扣掉 free 档当日唯一的 ask 配额（1 次/日）。
契约：身份校验失败（401）不得消耗配额；合法 recall 正常扣减。
"""
import uuid

import pytest
from fastapi.testclient import TestClient

import tatha.memory.recall as recall_mod
from tatha.api import quota as quota_mod
from tatha.api.app import app
from tatha.api.auth import AuthContext, get_auth

client = TestClient(app)

_ASK_BODY = {
    "message": "recall",
    "context": {"port_hint": "memory", "library": "issue"},
}


def _auth_as(tier: str = "free") -> str:
    """覆盖鉴权。每次用独立 user_id：配额是进程内按 user_id+日 计数的，测试间必须隔离。"""
    uid = f"test-ask-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_auth] = lambda: AuthContext(user_id=uid, tier=tier)
    return uid


def _remaining_ask(uid: str, tier: str = "free") -> int:
    return quota_mod.get_remaining(uid, tier, quota_mod.RESOURCE_ASK)


@pytest.fixture(autouse=True)
def _clean_override():
    yield
    app.dependency_overrides.pop(get_auth, None)


def test_missing_actor_header_401_without_consuming_quota():
    """缺 X-Actor-Sub → 401 missing_actor_sub，且当日 ask 配额分文未扣。"""
    uid = _auth_as()
    before = _remaining_ask(uid)
    assert before == 1  # free 档 ask 上限

    r = client.post("/v1/ask", json=_ASK_BODY)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "missing_actor_sub"
    assert _remaining_ask(uid) == before, "401 拒绝不应消耗配额"

    # 同一 user_id 补上头之后，当日额度仍完整可用
    assert _remaining_ask(uid) == 1


def test_blank_actor_header_also_rejected_without_consuming_quota():
    """X-Actor-Sub 为空白串等价于缺失，同样 401 且不扣配额。"""
    uid = _auth_as()
    r = client.post("/v1/ask", headers={"X-Actor-Sub": "   "}, json=_ASK_BODY)
    assert r.status_code == 401
    assert _remaining_ask(uid) == 1


def test_valid_recall_consumes_quota_once(monkeypatch):
    """带头合法 recall → 200，扣 1 次；free 档第二发 429。"""
    uid = _auth_as()
    monkeypatch.setattr(
        recall_mod,
        "handle_recall",
        lambda req, actor: {"status": "ok", "actor": actor, "count": 0, "records": []},
    )

    r = client.post("/v1/ask", headers={"X-Actor-Sub": "sub-abc"}, json=_ASK_BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["port"] == "memory"
    assert data["result"]["status"] == "ok"
    assert data["result"]["actor"] == "sub-abc"  # 原始 sub 透传，不做哈希
    assert _remaining_ask(uid) == 0

    r2 = client.post("/v1/ask", headers={"X-Actor-Sub": "sub-abc"}, json=_ASK_BODY)
    assert r2.status_code == 429
    assert r2.json()["detail"]["code"] == "quota_exceeded"


def test_non_memory_path_unaffected_by_actor_header(monkeypatch):
    """port_hint 非 memory 时不做 actor 校验（老意图路径行为不变，只确认不被 401 拦）。"""
    _auth_as()
    import tatha.api.app as app_mod

    monkeypatch.setattr(app_mod, "handle_ask", lambda req: {"intent": "demo", "result": {}})
    # 不带头：老路径不做 actor 校验；此处若 401 即回归
    r = client.post("/v1/ask", json={"message": "你好", "context": {}})
    assert r.status_code == 200
    assert r.json()["intent"] == "demo"
