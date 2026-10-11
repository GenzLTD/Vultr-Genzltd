"""数据主体权利入口测试：``GET /v1/account/export``、``DELETE /v1/account``。

Run: pytest tests/test_account_data_rights.py -v

锁死四件事：

1. 导出只给「我的」——越权取数不可接受；
2. 导出剔除凭据列（password_hash 等），密码摘要不属于可携带数据；
3. 导出范围与删除范围同源（都走 ``_collect_owned_ids``），包括沿外键遍历
   覆盖不到的无外键表（query_logs / product_events）—— 漏了就是"看起来
   导出全了、其实少一块"；
4. 注销必须显式确认；存在真实支付流水的账号被资金护栏挡回 409，
   且**数据一行都不能少**。
"""
from __future__ import annotations

import json

# ── helpers ──────────────────────────────────────────────────────────────


def _register(client, email, password="secret123"):
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "name": "DSAR"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _uid(client, email):
    with client.application._db.get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    assert row is not None, f"user {email} not found"
    return row[0]


def _seed(db, uid, tag="a"):
    """写入一条覆盖三类样本的足迹：普通子表 / 孙表 / 无外键表，外加审计轨迹。"""
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO consents (id, user_id, scope) VALUES (?, ?, ?)",
            (f"consent-{tag}", uid, "ask_rag"),
        )
        conn.execute(
            "INSERT INTO match_reports (id, user_id) VALUES (?, ?)",
            (f"mr-{tag}", uid),
        )
        # 孙表：只经由 match_reports 关联，没有指向 users 的外键
        conn.execute(
            "INSERT INTO match_report_items (id, report_id, job_title, company_name)"
            " VALUES (?, ?, ?, ?)",
            (f"mri-{tag}", f"mr-{tag}", "后端工程师", "某公司"),
        )
        # 无外键表 —— 沿外键遍历永远找不到
        conn.execute(
            "INSERT INTO query_logs (query_text, provider, user_id, created_at)"
            " VALUES (?, ?, ?, ?)",
            ("测试查询", "deepseek", uid, "2026-09-16 00:00:00"),
        )
        conn.execute(
            "INSERT INTO product_events (event_name, user_id, success) VALUES (?, ?, ?)",
            (f"evt-{tag}", uid, 1),
        )
        conn.execute(
            "INSERT INTO audit_logs (id, actor, action, resource_type) VALUES (?, ?, ?, ?)",
            (f"al-{tag}", uid, "register", "user"),
        )


# ── 导出 ─────────────────────────────────────────────────────────────────


class TestAccountExport:
    def test_requires_auth(self, client):
        assert client.get("/v1/account/export").status_code == 401

    def test_exports_only_my_rows(self, client):
        t1 = _register(client, "export-a@test.local")
        _register(client, "export-b@test.local")
        db = client.application._db
        _seed(db, _uid(client, "export-a@test.local"), "me")
        _seed(db, _uid(client, "export-b@test.local"), "other")

        r = client.get("/v1/account/export", headers=_auth(t1))
        assert r.status_code == 200, r.get_data(as_text=True)
        blob = json.dumps(r.get_json(), ensure_ascii=False)

        for mine in ("consent-me", "mr-me", "mri-me", "evt-me"):
            assert mine in blob, f"missing own row {mine}"
        for theirs in ("consent-other", "mr-other", "mri-other", "evt-other"):
            assert theirs not in blob, f"leaked other user's row {theirs}"

    def test_redacts_credential_columns(self, client):
        token = _register(client, "export-c@test.local")
        r = client.get("/v1/account/export", headers=_auth(token))
        rows = r.get_json()["tables"]["users"]
        assert rows, "own users row must be present"
        row = rows[0]
        assert "password_hash" not in row
        # 可携带的个人数据本身要留着
        assert row.get("email") == "export-c@test.local"

    def test_covers_non_fk_tables(self, client):
        token = _register(client, "export-d@test.local")
        uid = _uid(client, "export-d@test.local")
        _seed(client.application._db, uid, "nfk")

        tables = client.get("/v1/account/export", headers=_auth(token)).get_json()["tables"]
        # 无外键表不参与外键遍历，必须显式补扫，否则导出会缺一块
        assert any(row["user_id"] == uid for row in tables.get("query_logs", []))
        assert any(row["user_id"] == uid for row in tables.get("product_events", []))

    def test_covers_grandchild_table(self, client):
        token = _register(client, "export-e@test.local")
        uid = _uid(client, "export-e@test.local")
        _seed(client.application._db, uid, "gc")

        tables = client.get("/v1/account/export", headers=_auth(token)).get_json()["tables"]
        assert [row["id"] for row in tables.get("match_report_items", [])] == ["mri-gc"]

    def test_audit_logs_excluded_by_default_included_on_request(self, client):
        token = _register(client, "export-f@test.local")
        uid = _uid(client, "export-f@test.local")
        _seed(client.application._db, uid, "aud")

        default = client.get("/v1/account/export", headers=_auth(token)).get_json()
        assert "audit_logs" not in default["tables"]

        with_audit = client.get(
            "/v1/account/export?include_audit=1", headers=_auth(token)
        ).get_json()
        ids = [r["id"] for r in with_audit["tables"].get("audit_logs", [])]
        assert "al-aud" in ids

    def test_export_writes_audit_trail(self, client):
        token = _register(client, "export-g@test.local")
        uid = _uid(client, "export-g@test.local")
        assert client.get("/v1/account/export", headers=_auth(token)).status_code == 200

        with client.application._db.get_conn() as conn:
            actions = [
                r[0]
                for r in conn.execute(
                    "SELECT action FROM audit_logs WHERE actor = ?", (uid,)
                ).fetchall()
            ]
        assert "account_export" in actions

    def test_counts_reported(self, client):
        token = _register(client, "export-h@test.local")
        uid = _uid(client, "export-h@test.local")
        _seed(client.application._db, uid, "cnt")

        payload = client.get("/v1/account/export", headers=_auth(token)).get_json()
        assert payload["counts"]["match_report_items"] == 1
        assert payload["truncated"] == []


# ── 注销 ─────────────────────────────────────────────────────────────────


class TestAccountDelete:
    def test_requires_auth(self, client):
        assert client.delete("/v1/account").status_code == 401

    def test_requires_explicit_confirmation(self, client):
        token = _register(client, "del-a@test.local")
        uid = _uid(client, "del-a@test.local")

        r = client.delete("/v1/account", headers=_auth(token))
        assert r.status_code == 400
        assert r.get_json()["error"] == "confirmation_required"

        with client.application._db.get_conn() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM users WHERE id = ?", (uid,)
            ).fetchone()[0] == 1

    def test_wrong_confirmation_rejected(self, client):
        token = _register(client, "del-b@test.local")
        r = client.delete("/v1/account", headers=_auth(token), json={"confirm": "yes"})
        assert r.status_code == 400
        assert r.get_json()["error"] == "confirmation_required"

    def test_delete_removes_everything_and_invalidates_token(self, client):
        token = _register(client, "del-c@test.local")
        uid = _uid(client, "del-c@test.local")
        db = client.application._db
        _seed(db, uid, "del")

        r = client.delete("/v1/account", headers=_auth(token), json={"confirm": "DELETE"})
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["deleted"] is True

        with db.get_conn() as conn:
            for table, col in (
                ("users", "id"),
                ("consents", "user_id"),
                ("match_reports", "user_id"),
                ("query_logs", "user_id"),
                ("product_events", "user_id"),
            ):
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (uid,)
                ).fetchone()[0]
                assert n == 0, f"{table} still holds {n} row(s) for {uid}"
            # 审计轨迹保留，且留下"自助注销"这条
            actions = [
                x[0]
                for x in conn.execute(
                    "SELECT action FROM audit_logs WHERE actor = ?", (uid,)
                ).fetchall()
            ]
        assert "account_delete" in actions

        # 原 JWT 立即失效：require_auth 每次都回库查人，用户行没了自然 401
        assert client.get("/v1/auth/profile", headers=_auth(token)).status_code == 401

    def test_paid_orders_block_self_delete(self, client):
        token = _register(client, "del-d@test.local")
        uid = _uid(client, "del-d@test.local")
        db = client.application._db
        _seed(db, uid, "paid")
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO orders (id, user_id, out_trade_no, plan_id, tier,"
                " amount, currency, status, paid_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("o-1", uid, "TESTPAID001", "pro-monthly", "pro", 19.0, "CNY",
                 "paid", "2026-09-16 00:00:00"),
            )

        r = client.delete("/v1/account", headers=_auth(token), json={"confirm": "DELETE"})
        assert r.status_code == 409
        assert r.get_json()["error"] == "paid_orders_exist"
        assert r.get_json()["orders"] == ["TESTPAID001"]

        # 护栏必须"要么不动、要么全动"：被挡回时一行都不能少
        with db.get_conn() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM users WHERE id = ?", (uid,)
            ).fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM consents WHERE user_id = ?", (uid,)
            ).fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM query_logs WHERE user_id = ?", (uid,)
            ).fetchone()[0] == 1

    def test_export_and_delete_see_same_rows(self, client):
        """导出范围与删除范围必须同源：导出里出现过的表，删除都要处理到。"""
        token = _register(client, "del-e@test.local")
        uid = _uid(client, "del-e@test.local")
        _seed(client.application._db, uid, "same")

        exported = client.get("/v1/account/export", headers=_auth(token)).get_json()["tables"]
        exported_tables = {
            t for t, rows in exported.items() if t not in ("users", "audit_logs") and rows
        }
        assert exported_tables, "seed produced no exportable rows"

        deleted = client.delete(
            "/v1/account", headers=_auth(token), json={"confirm": "DELETE"}
        ).get_json()["tables"]
        missing = exported_tables - set(deleted)
        assert not missing, f"exported but not deleted: {sorted(missing)}"
