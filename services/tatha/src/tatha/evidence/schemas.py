"""skill-proof.v1 契约 + ingest 信封的 Pydantic 模型。

契约真源：Guibu ``contracts/skill-proof.v1.json``（Tatha 仓内 ``contracts/skill-proof.v1.json``
为其副本，同步机制见 ``docs/skill_evidence_ingest.md``）。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "skill-proof.v1"
SIGNAL_TYPE_SKILL_PROOF = "skill_proof"


class EvidenceItem(BaseModel):
    """对齐契约 evidence[]：一条技能的学习材料出处。"""

    skill: str
    source: str
    file_path: str | None = None
    start_sec: float | None = None
    end_sec: float | None = None
    excerpt: str
    similarity: float | None = None
    learned_at: str | None = None


class ProofItem(BaseModel):
    """可验证声明：looma_timeline / yedall_attestation / audit_package。"""

    type: str
    value: str


class SkillProofPayload(BaseModel):
    """对齐 contracts/skill-proof.v1.json 的载荷（信封 payload 字段）。"""

    schema_version: Literal["skill-proof.v1"]
    user_id: str = Field(min_length=1, description="sha256(email) 64 位 hex")
    skill_tags: list[str] = Field(min_length=1)
    level: Literal["beginner", "intermediate", "advanced"] | None = None
    evidence: list[EvidenceItem] = Field(min_length=1)
    total_micro_lessons: int = Field(default=1, ge=1)
    proofs: list[ProofItem] = Field(default_factory=list)
    generated_at: str
    expires_at: str | None = None


class SignalEnvelope(BaseModel):
    """ingest 请求信封：signal_type + user_id_hash + nonce + payload。

    幂等键 = (signal_type, user_id_hash, nonce)。
    """

    signal_type: str
    user_id_hash: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    payload: SkillProofPayload
