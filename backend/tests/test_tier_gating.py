"""Tests for tier gating, job posts, and contact sales."""
import json

import pytest


def _register(client, email):
    resp = client.post("/v1/auth/register", json={
        "email": email,
        "password": "secret123",
        "name": "Test",
    })
    assert resp.status_code == 201
    return resp.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _upgrade(client, token, tier):
    resp = client.post(
        "/v1/payment/upgrade",
        json={"tier": tier},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    return resp.get_json().get("access_token") or token


def test_free_user_blocked_from_candidates(client):
    token = _register(client, "free@test.com")
    client.post("/v1/enterprise/create", headers=_auth(token), json={"name": "测试企业"})

    resp = client.get("/v1/enterprise/candidates", headers=_auth(token))
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_supporter_can_access_candidates(client):
    token = _register(client, "sup@test.com")
    token = _upgrade(client, token, "supporter")
    client.post("/v1/enterprise/create", headers=_auth(token), json={"name": "测试企业"})

    resp = client.get("/v1/enterprise/candidates", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["limit"] == 20
    assert data["candidates"] == []


def test_job_post_limits_by_tier(client):
    supporter_token = _register(client, "jp-sup@test.com")
    supporter_token = _upgrade(client, supporter_token, "supporter")

    for i in range(3):
        resp = client.post(
            "/v1/job-posts",
            headers=_auth(supporter_token),
            json={"title": f"职位{i + 1}", "company": "测试公司"},
        )
        assert resp.status_code == 201

    resp = client.post(
        "/v1/job-posts",
        headers=_auth(supporter_token),
        json={"title": "超额职位", "company": "测试公司"},
    )
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "quota_exceeded"

    list_resp = client.get("/v1/job-posts", headers=_auth(supporter_token))
    assert list_resp.status_code == 200
    assert list_resp.get_json()["count"] == 3
    assert list_resp.get_json()["limit"] == 3


def test_free_user_blocked_from_job_posts(client):
    token = _register(client, "free-jp@test.com")
    resp = client.post(
        "/v1/job-posts",
        headers=_auth(token),
        json={"title": "测试职位"},
    )
    assert resp.status_code == 403


def test_contact_sales_creates_inquiry(client):
    resp = client.post("/v1/enterprise/contact-sales", json={
        "company_name": "未来科技",
        "contact_name": "张经理",
        "contact_email": "zhang@future.com",
        "contact_phone": "13800138000",
        "scale": "50-200人",
        "message": "需要私有化部署",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["ok"] is True
    assert data["id"]


def test_contact_sales_requires_fields(client):
    resp = client.post("/v1/enterprise/contact-sales", json={
        "company_name": "未来科技",
    })
    assert resp.status_code == 400


def test_job_post_matches_returns_candidates(client):
    seeker_token = _register(client, "seeker-jp@test.com")
    hr_token = _register(client, "hr-jp@test.com")
    hr_token = _upgrade(client, hr_token, "supporter")

    personality = {"name": "探索者", "traits": ["创新", "领导力"]}
    client.post(
        "/v1/game/profile-sync",
        headers=_auth(seeker_token),
        json={
            "personality_type": "探索者",
            "personality_detail": json.dumps(personality, ensure_ascii=False),
        },
    )
    code = client.post(
        "/v1/referral/create",
        headers=_auth(seeker_token),
        json={"purpose": "profile_share"},
    ).get_json()["code"]

    client.post("/v1/enterprise/create", headers=_auth(hr_token), json={"name": "HR公司"})
    client.post(
        "/v1/enterprise/candidates/import-share",
        headers=_auth(hr_token),
        json={"share_code": code},
    )

    post_resp = client.post(
        "/v1/job-posts",
        headers=_auth(hr_token),
        json={
            "title": "产品经理",
            "description": "需要创新领导力的产品经理",
            "requirements": ["创新", "领导力"],
        },
    )
    assert post_resp.status_code == 201
    post_id = post_resp.get_json()["id"]

    match_resp = client.get(
        f"/v1/job-posts/{post_id}/matches",
        headers=_auth(hr_token),
    )
    assert match_resp.status_code == 200
    matches = match_resp.get_json()["matches"]
    assert len(matches) == 1
    assert matches[0]["match_score"] > 0
