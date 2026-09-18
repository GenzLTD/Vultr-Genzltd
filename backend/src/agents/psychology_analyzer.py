"""
Psychology Analyzer — Conversation emotion analysis for Navigator mode.
Migrated from old psychology_analyzer.py, adapted for Flask.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger("looma.psychology")


@dataclass
class Emotions:
    primary_emotion: str = "neutral"
    intensity: float = 0.3
    valence: float = 0.5  # positive/negative (0-1)


@dataclass
class Guidance:
    approach: str = "supportive"  # supportive | challenging | reflective
    depth_level: int = 1  # 1-3


@dataclass
class PsychologyResult:
    emotions: Emotions
    guidance: Guidance


def analyze_conversation(
    user_message: str,
    session_history: list[dict] | None = None,
    active_domain: str = "",
    visited_domains: list[str] | None = None,
    use_external_api: bool = False,
) -> PsychologyResult:
    """Analyze user conversation to extract emotional state and guidance approach.

    Uses simple keyword-based analysis. External API (Sentino) can be added later.
    """
    text = user_message.lower()

    # Emotion detection (keyword-based)
    emotion_keywords = {
        "anxious": ["焦虑", "担心", "害怕", "紧张", "不安", "压力"],
        "sad": ["难过", "失落", "沮丧", "悲伤", "低落", "痛苦"],
        "angry": ["愤怒", "生气", "不满", "抱怨", "烦躁", "恼火"],
        "hopeful": ["期待", "希望", "憧憬", "向往", "信心", "积极"],
        "confused": ["困惑", "迷茫", "不确定", "不知道", "犹豫"],
        "curious": ["好奇", "想知道", "了解", "探索", "试试"],
        "grateful": ["感谢", "开心", "满意", "欣慰", "收获"],
        "neutral": [],
    }

    primary = "neutral"
    max_count = 0
    for emotion, keywords in emotion_keywords.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > max_count:
            primary = emotion
            max_count = count

    # Intensity based on keyword density and length
    intensity = min(1.0, max_count / max(len(text) / 10, 1))

    # Valence: positive emotions → higher valence
    positive = {"hopeful", "curious", "grateful"}
    negative = {"anxious", "sad", "angry", "confused"}
    valence = 0.5
    if primary in positive:
        valence = 0.7 + intensity * 0.2
    elif primary in negative:
        valence = 0.2 - intensity * 0.2

    # Guidance approach based on domain and emotional state
    approach = "supportive"
    if active_domain in ("self", "identity"):
        approach = "reflective"
    elif active_domain == "job" and primary in positive:
        approach = "challenging"

    depth = 1
    if visited_domains and len(visited_domains) >= 2:
        depth = 2
    if primary in ("anxious", "sad") and intensity > 0.5:
        depth = 3

    return PsychologyResult(
        emotions=Emotions(primary_emotion=primary, intensity=intensity, valence=valence),
        guidance=Guidance(approach=approach, depth_level=depth),
    )


def build_psychology_hint(result: PsychologyResult) -> str:
    """Build a psychology hint string for Navigator prompt injection."""
    approach_map = {
        "supportive": "用户需要支持与肯定。回应时多用鼓励语言，避免过度追问。",
        "reflective": "用户正在反思。用提问引导思考，不直接给答案。",
        "challenging": "用户状态积极。可以适度挑战其舒适区，引导深度探索。",
    }
    hint = approach_map.get(result.guidance.approach, "")
    if result.emotions.intensity > 0.5:
        hint += f" 注意：用户情绪强度较高（{result.emotions.primary_emotion}），回应需温和。"
    return hint
