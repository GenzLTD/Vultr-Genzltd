"""
MBTI Text Analyzer — Analyze text to infer MBTI personality type.

Migrated from old mbti_analyzer.py, adapted for Flask.
"""
from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger("looma.mbti")

MIN_TEXT_LENGTH = 20

MBTI_DIMENSIONS = {
    "E/I": {"extraversion": ["外向", "社交", "团队", "活跃", "热情", "开朗", "沟通", "表达"],
            "introversion": ["内向", "独处", "思考", "安静", "沉稳", "专注", "深思", "独立"]},
    "S/N": {"sensing": ["实际", "经验", "细节", "具体", "传统", "务实", "步骤", "观察"],
            "intuition": ["想象", "创新", "可能", "模式", "愿景", "直觉", "灵感", "大局"]},
    "T/F": {"thinking": ["逻辑", "分析", "客观", "理性", "效率", "判断", "数据", "因果"],
            "feeling": ["情感", "共情", "价值", "和谐", "关怀", "体贴", "感受", "关系"]},
    "J/P": {"judging": ["计划", "组织", "目标", "结构", "秩序", "准时", "规划", "控制"],
            "perceiving": ["灵活", "适应", "探索", "开放", "随性", "变化", "尝试", "自发"]},
}

MBTI_DESCRIPTIONS = {
    "ISTJ": "检查员 — 安静严肃，通过全面性和可靠性来获得成功",
    "ISFJ": "保护者 — 安静友好，有责任心和尽职尽责",
    "INFJ": "提倡者 — 寻求思想、关系和物质等之间的意义和联系",
    "INTJ": "建筑师 — 在实现自己的想法和达成目标时有着独创性的驱动力",
    "ISTP": "鉴赏家 — 灵活耐心，通常是一个安静的观察者",
    "ISFP": "探险家 — 安静友好，敏感和善良",
    "INFP": "调停者 — 理想主义，对于重要的事情有着忠诚的信念",
    "INTP": "逻辑学家 — 寻求对他们感兴趣的事物逻辑性的解释",
    "ESTP": "企业家 — 灵活忍耐，通常采取 pragmatic approach 来取得结果",
    "ESFP": "表演者 — 外向友好，接受生活的人和事物",
    "ENFP": "竞选者 — 热情富有想象力，认为生活充满可能性",
    "ENTP": "辩论家 — 聪明有能力，喜欢挑战和争辩",
    "ESTJ": "总经理 — 实际现实，事实导向，果断快速",
    "ESFJ": "执政官 — 热心尽责，有合作精神",
    "ENFJ": "主人公 — 温情有同情心，积极响应别人的需要",
    "ENTJ": "指挥官 — 率直果断，有天生的领导力",
}


class MBTITextAnalyzer:
    """Analyze text to infer MBTI type using keyword scoring + optional LLM refinement."""

    def analyze_text(self, text: str) -> dict:
        """Analyze text and return MBTI analysis result."""
        scores = self._keyword_scores(text)

        # Determine each dimension
        type_code = ""
        dimension_results = {}
        for dim, prefs in MBTI_DIMENSIONS.items():
            pos_letter = dim.split("/")[0]  # E, S, T, J
            neg_letter = dim.split("/")[1]  # I, N, F, P

            pos_score = scores.get(f"{pos_letter.lower()}_score", 0)
            neg_score = scores.get(f"{neg_letter.lower()}_score", 0)

            if pos_score >= neg_score:
                chosen = pos_letter
            else:
                chosen = neg_letter
            type_code += chosen

            dimension_results[dim] = {
                "chosen": chosen,
                "pos_score": pos_score,
                "neg_score": neg_score,
            }

        # Try LLM refinement if available
        try:
            from src.agents.central_brain import _call_llm
            prompt = (
                f"根据以下自述文本分析用户的MBTI性格类型。只输出4字母MBTI类型（如INTJ）和一个简短描述。\n\n"
                f"用户自述：{text[:500]}\n\n"
                '请输出 JSON：{"type": "XXXX", "description": "..."}'
            )
            response = _call_llm(prompt)
            if response:
                resp = response.strip()
                if "```" in resp:
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp)
                    if m:
                        resp = m.group(1).strip()
                try:
                    data = json.loads(resp)
                    llm_type = data.get("type", "")
                    if llm_type and len(llm_type) == 4 and llm_type.isupper():
                        type_code = llm_type
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass  # LLM unavailable, keep keyword result

        description = MBTI_DESCRIPTIONS.get(type_code, "未知类型")
        return {
            "mbti_type": type_code,
            "description": description,
            "dimensions": dimension_results,
            "confidence": sum(
                abs(d["pos_score"] - d["neg_score"]) for d in dimension_results.values()
            ) / 4,
        }

    def _keyword_scores(self, text: str) -> dict:
        """Score each MBTI dimension based on keyword frequency."""
        text_lower = text.lower()
        scores = {}
        for dim, prefs in MBTI_DIMENSIONS.items():
            pos_letter = dim.split("/")[0].lower()
            neg_letter = dim.split("/")[1].lower()
            pos_kw = prefs.get("extraversion" if pos_letter == "e" else
                               "sensing" if pos_letter == "s" else
                               "thinking" if pos_letter == "t" else "judging", [])
            neg_kw = prefs.get("introversion" if neg_letter == "i" else
                               "intuition" if neg_letter == "n" else
                               "feeling" if neg_letter == "f" else "perceiving", [])
            scores[f"{pos_letter}_score"] = sum(1 for kw in pos_kw if kw in text_lower)
            scores[f"{neg_letter}_score"] = sum(1 for kw in neg_kw if kw in text_lower)
        return scores
