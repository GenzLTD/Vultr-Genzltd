"""技能证据摄入（skill-proof）与简历增强的契约测试。

覆盖：
- EvidenceStore 幂等 + 聚合
- HMAC 签名/验签
- resume_enhancer 注入 / 无证据原样
- POST /v1/skills/ingest 端点（dev 免签 / HMAC 强制 / 幂等 / 校验失败）
"""
import json

import pytest
from fastapi.testclient import TestClient

from tatha.api.app import app
from tatha.evidence import EvidenceStore, enhance_resume, sign_body, verify_signature
from tatha.evidence import store as store_mod

USER_ID = "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b"
SECRET = "test-shared-secret"


def make_payload(user_id: str = USER_ID) -> dict:
    return {
        "schema_version": "skill-proof.v1",
        "user_id": user_id,
        "skill_tags": ["Python", "列表推导式"],
        "level": "beginner",
        "evidence": [
            {
                "skill": "列表推导式",
                "source": "python数据分析实战.md",
                "file_path": None,
                "start_sec": None,
                "end_sec": None,
                "excerpt": "列表推导式可以将循环与条件合并，语法为 [expr for x in iterable if cond]",
                "similarity": 0.82,
                "learned_at": "2026-08-12T10:00:00+08:00",
            }
        ],
        "total_micro_lessons": 3,
        "proofs": [],
        "generated_at": "2026-08-12T12:00:00+08:00",
        "expires_at": None,
    }


def make_envelope(user_id_hash: str = USER_ID, nonce: str = "nonce-1") -> dict:
    return {
        "signal_type": "skill_proof",
        "user_id_hash": user_id_hash,
        "nonce": nonce,
        "payload": make_payload(user_id_hash),
    }


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    """隔离 skills_evidence 到临时库 + 重置单例；默认无 SIGNAL_BRIDGE_SECRET（dev 免签）。"""
    monkeypatch.setenv("TATHA_EVIDENCE_DB", str(tmp_path / "skills.db"))
    monkeypatch.delenv("SIGNAL_BRIDGE_SECRET", raising=False)
    store_mod._store = None
    yield
    store_mod._store = None


# ---------- 存储幂等与聚合 ----------


def test_store_idempotent_insert(tmp_path):
    store = EvidenceStore(tmp_path / "ev.db")
    payload = make_payload()
    row1, created1 = store.insert("skill_proof", USER_ID, "nonce-1", payload)
    row2, created2 = store.insert("skill_proof", USER_ID, "nonce-1", payload)
    assert created1 is True
    assert created2 is False
    assert row1["id"] == row2["id"]
    assert store.count_for_user(USER_ID) == 1
    store.close()


def test_store_get_verified_skills_aggregates(tmp_path):
    store = EvidenceStore(tmp_path / "ev.db")
    store.insert("skill_proof", USER_ID, "nonce-1", make_payload())
    skills = store.get_verified_skills(USER_ID)
    assert len(skills) == 1
    assert skills[0]["skill"] == "列表推导式"
    assert len(skills[0]["evidence"]) == 1
    assert store.distinct_skill_tags(USER_ID) == ["Python", "列表推导式"]
    store.close()


# ---------- HMAC ----------


def test_hmac_roundtrip():
    body = b'{"a":1}'
    sig = sign_body(SECRET, body)
    assert verify_signature(SECRET, body, sig) is True
    assert verify_signature(SECRET, body, "deadbeef") is False
    assert verify_signature(SECRET, body, None) is False
    assert verify_signature("wrong-secret", body, sig) is False


# ---------- resume_enhancer ----------


def test_enhance_resume_injects_verified_block():
    skills = [{"skill": "Python", "evidence": [{"source": "s.md", "excerpt": "示例摘录"}]}]
    enhanced, out = enhance_resume("简历正文", skills)
    assert "已验证技能" in enhanced
    assert "Python" in enhanced
    assert "s.md" in enhanced
    assert out == skills


def test_enhance_resume_noop_when_no_evidence():
    enhanced, out = enhance_resume("简历正文", [])
    assert enhanced == "简历正文"
    assert out == []


# ---------- ingest 端点 ----------


def test_ingest_dev_mode_and_idempotent(isolated_store):
    client = TestClient(app)
    env = make_envelope()

    r1 = client.post("/v1/skills/ingest", json=env)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "stored"
    assert d1["verified"] is False  # 未配 secret → dev 免签
    assert d1["evidence_count"] == 1
    assert d1["skill_tags"] == ["Python", "列表推导式"]

    r2 = client.post("/v1/skills/ingest", json=env)  # 同 nonce 幂等
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "duplicate"
    assert d2["evidence_id"] == d1["evidence_id"]
    assert d2["evidence_count"] == 1


def test_ingest_user_id_mismatch(isolated_store):
    client = TestClient(app)
    env = make_envelope()
    env["user_id_hash"] = "another-hash"  # 仅改信封，不改 payload.user_id
    r = client.post("/v1/skills/ingest", json=env)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "user_id_mismatch"


def test_ingest_unsupported_signal(isolated_store):
    client = TestClient(app)
    env = make_envelope()
    env["signal_type"] = "unknown_signal"
    r = client.post("/v1/skills/ingest", json=env)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "unsupported_signal"


def test_ingest_invalid_payload(isolated_store):
    client = TestClient(app)
    env = make_envelope()
    env["payload"].pop("evidence")  # 契约 required 缺失
    r = client.post("/v1/skills/ingest", json=env)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_envelope"


def test_ingest_hmac_enforced(isolated_store, monkeypatch):
    monkeypatch.setenv("SIGNAL_BRIDGE_SECRET", SECRET)
    client = TestClient(app)
    env = make_envelope()
    raw = json.dumps(env, ensure_ascii=False).encode()

    # 无签名 → 401
    r0 = client.post(
        "/v1/skills/ingest",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert r0.status_code == 401

    # 错误签名 → 401
    r1 = client.post(
        "/v1/skills/ingest",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": "bad"},
    )
    assert r1.status_code == 401

    # 正确签名 → 200 且 verified=True
    sig = sign_body(SECRET, raw)
    r2 = client.post(
        "/v1/skills/ingest",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert r2.status_code == 200
    assert r2.json()["verified"] is True
