"""POST /v1/mbti/analyze 接口契约测试：三态、独立配额、鉴权。

核心契约两条：
1. 只有 status=ok 时才给花语与职业建议，partial / insufficient 不给结论；
2. 计量走独立资源 mbti，不再吃掉 /v1/ask 的免费额度（免费档 ask 仅 1 次/日）。
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from tatha.api.app import app
from tatha.api.auth import AuthContext, get_auth

client = TestClient(app)

# 四轴齐全：独立+思考(I) / 细节+具体+步骤(S) / 逻辑+分析(T) / 计划(J)
OK_TEXT = "我喜欢独立思考，做事注重细节和具体步骤，分析问题时看重逻辑，习惯先做好计划再执行。"
# 有信号但 E/I 持平（独立 vs 团队），且 S/N、J/P 无信号
PARTIAL_TEXT = "我做事看重逻辑，喜欢独立思考，也喜欢团队协作。"
# 无关键词信号，长度足够
NO_SIGNAL_TEXT = "今天天气不错，我吃了一碗面条，然后看了一会儿电视，窗外有鸟在叫。"


def _auth_as(tier: str = "free", user_id: str | None = None) -> str:
    """覆盖鉴权。每次用独立 user_id：配额是进程内按 user_id+日 计数的，测试间必须隔离。"""
    uid = user_id or f"test-mbti-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_auth] = lambda: AuthContext(user_id=uid, tier=tier)
    return uid


@pytest.fixture(autouse=True)
def _clean_override():
    yield
    app.dependency_overrides.pop(get_auth, None)


def test_ok_gives_flower_and_career():
    """四轴齐全：给花语 + 职业建议，类型是完整四字母。"""
    _auth_as("free")
    r = client.post("/v1/mbti/analyze", json={"text": OK_TEXT})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert len(data["mbti_type"]) == 4 and "X" not in data["mbti_type"]
    assert data["flower_personality"] not in (None, "", "待分析")
    assert data["career_match"] is not None
    assert data["career_match"]["suitable_careers"]
    assert data["insufficient_reason"] is None


def test_partial_gives_no_career():
    """部分轴缺信号：不给职业建议，列出缺信号的轴，并给补充描述的引导。"""
    _auth_as("free")
    r = client.post("/v1/mbti/analyze", json={"text": PARTIAL_TEXT})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "partial"
    assert data["career_match"] is None
    assert data["undetermined_axes"]
    assert data["hint"]


def test_insufficient_gives_no_conclusion():
    """无信号：不猜类型（旧行为恒返回 INFP+薰衣草），明确 XXXX + 待分析。"""
    _auth_as("free")
    r = client.post("/v1/mbti/analyze", json={"text": NO_SIGNAL_TEXT})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "insufficient"
    assert data["mbti_type"] == "XXXX"
    assert data["flower_personality"] == "待分析"
    assert data["career_match"] is None
    assert data["insufficient_reason"]


def test_free_tier_three_calls_then_429():
    """免费档 3 次/日：第 4 次返回 429 且带 quota_exceeded。"""
    _auth_as("free")
    for _ in range(3):
        assert client.post("/v1/mbti/analyze", json={"text": OK_TEXT}).status_code == 200
    r = client.post("/v1/mbti/analyze", json={"text": OK_TEXT})
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "quota_exceeded"


def test_mbti_quota_is_independent_of_ask():
    """人格测评用尽后，ask 的额度一分未动——这是与 /v1/ask 分开计量的意义。"""
    from tatha.api.quota import RESOURCE_ASK, RESOURCE_MBTI, get_remaining

    uid = _auth_as("free")
    for _ in range(3):
        assert client.post("/v1/mbti/analyze", json={"text": OK_TEXT}).status_code == 200
    assert get_remaining(uid, "free", RESOURCE_MBTI) == 0
    assert get_remaining(uid, "free", RESOURCE_ASK) == 1


def test_requires_auth():
    """无 token 401：小工具同样走鉴权，不能匿名白嫖。"""
    app.dependency_overrides.pop(get_auth, None)
    r = client.post("/v1/mbti/analyze", json={"text": OK_TEXT})
    assert r.status_code == 401


def test_pricing_exposes_mbti_daily_quota():
    """订阅页要能展示人格测评额度：字段由 QUOTA_LIMITS 派生，不另写一份以免漂移。"""
    from tatha.api.quota import QUOTA_LIMITS, RESOURCE_MBTI

    r = client.get("/v1/region?country=CN")
    assert r.status_code == 200
    quota_shown = r.json()["pricing"]["mbti_daily_quota"]
    assert quota_shown == {
        tier: limits.get(RESOURCE_MBTI, 0) for tier, limits in QUOTA_LIMITS.items()
    }
    assert quota_shown["free"] == 3
