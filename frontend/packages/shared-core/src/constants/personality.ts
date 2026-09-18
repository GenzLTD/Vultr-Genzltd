import type { PersonalityType } from "../types/planetx-game";

/** 双特质组合 → 人格类型（单真源 · S0-3） */
export const PERSONALITY_MAP: Record<string, PersonalityType> = {
  creative_social: {
    name: "星云艺术家",
    emoji: "🎨",
    tagline: "创造力 + 感染力 = 你的超能力",
    desc: "你天生会讲故事。在团队里你是灵感的源头，你的想法总能点燃别人的热情。适合创意、内容、品牌向的工作。",
    traits: ["创造力爆表", "社交引力", "直觉驱动"],
  },
  creative_thinker: {
    name: "黑洞程序员",
    emoji: "💻",
    tagline: "思维深度穿透事件视界",
    desc: "你对世界的理解超越表面。安静、深邃、逻辑严密。适合技术、研发、数据分析向的工作。",
    traits: ["深度思考", "逻辑严谨", "独立作战"],
  },
  social_action: {
    name: "超新星领航员",
    emoji: "⭐",
    tagline: "你的能量可以点亮整个星系",
    desc: "你是人群中的太阳。行动力+社交力让你成为天然的Leader。适合管理、销售、创业向的工作。",
    traits: ["天然领袖", "行动力MAX", "感染力强"],
  },
  social_supporter: {
    name: "双星星系守护者",
    emoji: "🌓",
    tagline: "你的存在就是别人的安全感",
    desc: "你是团队的粘合剂。善解人意、温暖可靠。适合HR、客服、教育、心理咨询向的工作。",
    traits: ["共情力强", "可靠后盾", "温暖磁场"],
  },
  growth_balance: {
    name: "脉冲星修行者",
    emoji: "✨",
    tagline: "持续进化，但从不透支自己",
    desc: "你追求成长但不盲从。节奏感是你最强的武器。适合需要持续深耕的专业领域。",
    traits: ["长期主义", "自我节奏", "持续进化"],
  },
  wanderer_balance: {
    name: "暗物质漫游者",
    emoji: "🌌",
    tagline: "你的自由就是你的引力",
    desc: "你不急着定义自己。在探索中你会找到属于自己的独特轨道。适合自由职业、跨界领域。",
    traits: ["自由灵魂", "跨界思维", "不被定义"],
  },
};

export const PERSONALITY_FALLBACK_MAP: Record<string, PersonalityType> = {
  creative: PERSONALITY_MAP["creative_social"],
  social: PERSONALITY_MAP["social_action"],
  thinker: PERSONALITY_MAP["creative_thinker"],
  action: PERSONALITY_MAP["social_action"],
  growth: PERSONALITY_MAP["growth_balance"],
  wanderer: PERSONALITY_MAP["wanderer_balance"],
};
