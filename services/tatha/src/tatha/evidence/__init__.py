"""Guibu → Tatha 技能证据摄入与简历增强。

- ``store``：skills_evidence 表（SQLite 幂等）
- ``hmac``：X-Signature 验签
- ``resume_enhancer``：匹配前查证据 → 简历打 verified + evidence 引用
"""
from .hmac import sign_body, verify_signature
from .resume_enhancer import build_evidence_block, enhance_resume
from .schemas import (
    SCHEMA_VERSION,
    SIGNAL_TYPE_SKILL_PROOF,
    EvidenceItem,
    ProofItem,
    SignalEnvelope,
    SkillProofPayload,
)
from .store import EvidenceStore, get_store

__all__ = [
    "SCHEMA_VERSION",
    "SIGNAL_TYPE_SKILL_PROOF",
    "EvidenceItem",
    "ProofItem",
    "SignalEnvelope",
    "SkillProofPayload",
    "sign_body",
    "verify_signature",
    "build_evidence_block",
    "enhance_resume",
    "EvidenceStore",
    "get_store",
]
