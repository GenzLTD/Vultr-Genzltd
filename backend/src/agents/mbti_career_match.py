"""
MBTI Career Match — Map MBTI types to recommended career paths.
Migrated from old mbti_career_match.py.
"""
from __future__ import annotations

MBTI_CAREER_MAP = {
    "ISTJ": {"industries": ["会计", "审计", "法律", "工程管理"], "roles": ["审计师", "会计", "程序员", "工程师", "管理员"],
             "strengths": ["严谨细致", "可靠稳定", "组织能力强"], "growth_areas": ["灵活应变", "创新思维"]},
    "ISFJ": {"industries": ["医疗", "教育", "社会工作", "行政"], "roles": ["护士", "教师", "行政助理", "心理咨询师"],
             "strengths": ["耐心体贴", "忠诚可靠", "观察敏锐"], "growth_areas": ["自我表达", "果断决策"]},
    "INFJ": {"industries": ["心理咨询", "教育", "写作", "非营利组织"], "roles": ["心理咨询师", "作家", "教师", "人力资源专家"],
             "strengths": ["洞察力强", "理想主义", "善于倾听"], "growth_areas": ["理性分析", "边界设定"]},
    "INTJ": {"industries": ["科技", "金融", "战略咨询", "学术研究"], "roles": ["架构师", "战略分析师", "科学家", "投资经理"],
             "strengths": ["战略思维", "独立创新", "系统性分析"], "growth_areas": ["团队协作", "情感表达"]},
    "ISTP": {"industries": ["工程", "技术", "运动", "执法"], "roles": ["工程师", "技术专家", "消防员", "飞行员"],
             "strengths": ["动手能力强", "灵活务实", "问题解决"], "growth_areas": ["长期规划", "情感沟通"]},
    "ISFP": {"industries": ["艺术", "设计", "医疗", "教育"], "roles": ["艺术家", "设计师", "护士", "教师"],
             "strengths": ["审美敏感", "温和友善", "适应性强"], "growth_areas": ["目标规划", "果断行动"]},
    "INFP": {"industries": ["写作", "心理咨询", "艺术", "教育"], "roles": ["作家", "心理咨询师", "艺术家", "UX设计师"],
             "strengths": ["创意丰富", "理想驱动", "深度共情"], "growth_areas": ["执行力", "现实适应"]},
    "INTP": {"industries": ["科技", "学术", "数据分析", "法律"], "roles": ["程序员", "数据科学家", "哲学家", "分析师"],
             "strengths": ["逻辑分析", "创新思维", "独立探索"], "growth_areas": ["社交沟通", "项目完成"]},
    "ESTP": {"industries": ["销售", "创业", "体育", "执法"], "roles": ["销售经理", "创业者", "运动员", "警察"],
             "strengths": ["行动力强", "适应环境", "人际敏锐"], "growth_areas": ["长期规划", "细节把控"]},
    "ESFP": {"industries": ["娱乐", "销售", "医疗", "教育"], "roles": ["演员", "销售", "护士", "活动策划"],
             "strengths": ["热情活力", "人际魅力", "即兴应变"], "growth_areas": ["系统规划", "专注深度"]},
    "ENFP": {"industries": ["创意", "咨询", "教育", "媒体"], "roles": ["创意总监", "咨询顾问", "教师", "记者"],
             "strengths": ["创意驱动", "人际激励", "灵活适应"], "growth_areas": ["专注执行", "细节管理"]},
    "ENTP": {"industries": ["创业", "咨询", "科技", "法律"], "roles": ["创业者", "咨询顾问", "产品经理", "律师"],
             "strengths": ["创新突破", "辩论说服", "战略直觉"], "growth_areas": ["执行落地", "耐心坚持"]},
    "ESTJ": {"industries": ["管理", "金融", "法律", "军事"], "roles": ["管理者", "银行家", "法官", "军官"],
             "strengths": ["组织高效", "目标明确", "执行果断"], "growth_areas": ["灵活应变", "情感关怀"]},
    "ESFJ": {"industries": ["医疗", "教育", "社会工作", "行政"], "roles": ["护士", "教师", "人事经理", "社工"],
             "strengths": ["团队协作", "关怀体贴", "组织有序"], "growth_areas": ["独立判断", "适应变化"]},
    "ENFJ": {"industries": ["教育", "咨询", "人力资源", "公益"], "roles": ["教师", "咨询师", "HR经理", "公益领袖"],
             "strengths": ["激励他人", "远见卓识", "关系协调"], "growth_areas": ["客观分析", "自我关怀"]},
    "ENTJ": {"industries": ["管理", "金融", "创业", "法律"], "roles": ["CEO", "投资银行家", "律师", "战略顾问"],
             "strengths": ["领导决断", "战略规划", "效率驱动"], "growth_areas": ["倾听耐心", "情感表达"]},
}


def get_career_match(mbti_type: str) -> dict:
    """Get career recommendations for a given MBTI type."""
    match = MBTI_CAREER_MAP.get(mbti_type, {})
    if not match:
        return {"industries": ["综合"], "roles": ["待分析"], "strengths": ["待评估"], "growth_areas": ["待探索"]}
    return match
