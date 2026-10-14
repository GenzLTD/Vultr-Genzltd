"""skills_evidence 表：SQLite 存储 + 幂等 + 按 user_id_hash 聚合查询。

- 表位置：``<项目根>/.data/skills_evidence.db``（``.data/`` 已 gitignore，证据不入库）
- 幂等：唯一约束 ``(signal_type, user_id_hash, nonce)``，重复摄入返回已有记录
- 查询：按 ``user_id_hash`` 聚合所有证据，供 resume_enhancer 打 verified + evidence 引用
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_type TEXT NOT NULL,
    user_id_hash TEXT NOT NULL,
    nonce TEXT NOT NULL,
    payload TEXT NOT NULL,
    skill_tags TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    generated_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(signal_type, user_id_hash, nonce)
);
CREATE INDEX IF NOT EXISTS idx_skills_evidence_user ON skills_evidence(user_id_hash);
"""

_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceStore:
    """skills_evidence 的极简存储层（标准库 sqlite3，无新依赖）。"""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # ---- 写入（幂等） ----
    def insert(
        self,
        signal_type: str,
        user_id_hash: str,
        nonce: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """插入一条证据，返回 ``(row_dict, created)``。

        重复 ``(signal_type, user_id_hash, nonce)`` 时返回已有记录且 ``created=False``。
        """
        payload_json = json.dumps(payload, ensure_ascii=False)
        tags = payload.get("skill_tags") or []
        tags_json = json.dumps(tags, ensure_ascii=False)
        evidence_count = len(payload.get("evidence") or [])
        generated_at = payload.get("generated_at")
        created_at = now_iso()
        with _lock, self._conn:
            try:
                cur = self._conn.execute(
                    "INSERT INTO skills_evidence "
                    "(signal_type, user_id_hash, nonce, payload, skill_tags, "
                    " evidence_count, generated_at, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        signal_type,
                        user_id_hash,
                        nonce,
                        payload_json,
                        tags_json,
                        evidence_count,
                        generated_at,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError:
                row = self._conn.execute(
                    "SELECT * FROM skills_evidence "
                    "WHERE signal_type=? AND user_id_hash=? AND nonce=?",
                    (signal_type, user_id_hash, nonce),
                ).fetchone()
                return dict(row), False
        row = self._conn.execute(
            "SELECT * FROM skills_evidence WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return dict(row), True

    # ---- 查询 ----
    def count_for_user(self, user_id_hash: str) -> int:
        """某用户累计摄入的 skill-proof 记录数。"""
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM skills_evidence WHERE user_id_hash=?",
            (user_id_hash,),
        ).fetchone()
        return int(row["n"])

    def distinct_skill_tags(self, user_id_hash: str) -> list[str]:
        """某用户累计去重的 skill_tags（保持首次出现顺序）。"""
        rows = self._conn.execute(
            "SELECT skill_tags FROM skills_evidence WHERE user_id_hash=? ORDER BY id ASC",
            (user_id_hash,),
        ).fetchall()
        seen: set[str] = set()
        out: list[str] = []
        for r in rows:
            for t in json.loads(r["skill_tags"] or "[]"):
                if t and t not in seen:
                    seen.add(t)
                    out.append(t)
        return out

    def get_verified_skills(self, user_id_hash: str) -> list[dict[str, Any]]:
        """聚合某用户所有已验证技能 + 证据引用（按 skill 去重）。"""
        rows = self._conn.execute(
            "SELECT payload FROM skills_evidence WHERE user_id_hash=? ORDER BY id ASC",
            (user_id_hash,),
        ).fetchall()
        by_skill: dict[str, dict[str, Any]] = {}
        for r in rows:
            payload = json.loads(r["payload"])
            for ev in payload.get("evidence") or []:
                skill = (ev.get("skill") or "").strip()
                if not skill:
                    continue
                entry = by_skill.setdefault(skill, {"skill": skill, "evidence": []})
                entry["evidence"].append(
                    {
                        "source": ev.get("source"),
                        "excerpt": ev.get("excerpt"),
                        "learned_at": ev.get("learned_at"),
                        "file_path": ev.get("file_path"),
                        "start_sec": ev.get("start_sec"),
                        "end_sec": ev.get("end_sec"),
                        "similarity": ev.get("similarity"),
                    }
                )
        return [by_skill[s] for s in by_skill]


_store: EvidenceStore | None = None


def get_store(db_path: str | Path | None = None) -> EvidenceStore:
    """进程级单例；测试可传临时路径构造独立实例。"""
    global _store
    if db_path is not None:
        return EvidenceStore(db_path)
    if _store is None:
        from tatha.core.config import get_evidence_db_path

        _store = EvidenceStore(get_evidence_db_path())
    return _store
