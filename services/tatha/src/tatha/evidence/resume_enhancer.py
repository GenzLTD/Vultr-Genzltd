"""简历增强：匹配前按 user_id_hash 查证据，往简历打 verified + evidence 引用。

验收口径：同一简历「无证明 vs 有证明」，JobMatchScore 不降 + 技能命中率（skills_overlap）上升。
做法：把已验证技能与证据引用作为**追加文本块**注入简历，供 LLM 打分时感知「这是有溯源支撑的技能」，
而非简单堆关键词。注入失败不阻断匹配（enhance 异常被 pipeline 吞掉）。
"""
from __future__ import annotations

from typing import Any

_HEADER = "## 已验证技能（Guibu 微课学习证据，非自述）"


def build_evidence_block(verified_skills: list[dict[str, Any]]) -> str:
    """把 verified_skills 结构化为注入简历末尾的 Markdown 文本块。"""
    if not verified_skills:
        return ""
    lines: list[str] = ["", _HEADER]
    for vs in verified_skills:
        skill = vs.get("skill") or ""
        evs = vs.get("evidence") or []
        refs: list[str] = []
        for ev in evs[:3]:
            src = ev.get("source") or "未知来源"
            excerpt = (ev.get("excerpt") or "").strip()
            refs.append(f"{src}「{excerpt[:60]}」" if excerpt else src)
        ref_text = "；".join(refs) if refs else "—"
        lines.append(f"- {skill} — 证据 {len(evs)} 条：{ref_text}")
    return "\n".join(lines)


def enhance_resume(
    resume_text: str,
    verified_skills: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """把证据块注入 resume_text 末尾，返回 ``(增强后简历, verified_skills)``。无证据时原样返回。"""
    block = build_evidence_block(verified_skills)
    if not block:
        return resume_text, []
    enhanced = (resume_text or "").rstrip() + "\n" + block + "\n"
    return enhanced, verified_skills
