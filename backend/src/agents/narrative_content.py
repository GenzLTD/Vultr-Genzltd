"""
Act 1 Narrative Content Library — GDD §5 implementation.
Ownership: Jason

Contains ALL hand-written narrative text for the Act 1 Landing experience:
  - 6 domain encounter scripts (first impression)
  - 18 choice trees (3 per domain) with consequence text
  - 18 value imprint names
  - 6 convergence texture interpretations
  - Navigator greeting + signal lines
  - Act 1 hook lines

All text here is hand-written per GDD P4 (手工核心).
Ref: PlanetX-T空间_游戏化预演设计_GDD.md §5.1 / tspace_act1_prototype.html
"""
from __future__ import annotations

# ============================================================================
# Act 1 Step Timeline
# ============================================================================

ACT1_STEPS = [
    {"id": 0, "label": "开场", "desc": "登陆T空间 · Navigator介绍"},
    {"id": 1, "label": "信号", "desc": "待处理信号 · 六域亮起"},
    {"id": 2, "label": "初遇", "desc": "域内第一拍 · 首次遭遇"},
    {"id": 3, "label": "选择", "desc": "域内第二拍 · 第一个选择"},
    {"id": 4, "label": "后果", "desc": "域内第三拍 · 即时后果"},
    {"id": 5, "label": "收敛", "desc": "收敛点 · Navigator故障"},
    {"id": 6, "label": "钩子", "desc": "Act 1 结束 · 悬念建立"},
]

# Extended step timeline for career→poetry cross-domain path (GDD §9.2)
ACT1_STEPS_CROSS = [
    {"id": 0,  "label": "开场",   "desc": "登陆T空间 · Navigator介绍"},
    {"id": 1,  "label": "信号",   "desc": "待处理信号 · 六域亮起"},
    {"id": 2,  "label": "初遇",   "desc": "域内第一拍 · 职业域首次遭遇"},
    {"id": 3,  "label": "选择",   "desc": "域内第二拍 · 职业域第一个选择"},
    {"id": 4,  "label": "后果",   "desc": "域内第三拍 · 职业域即时后果"},
    {"id": 5,  "label": "跨域",   "desc": "诗域信号亮起 · 跨端口触发"},
    {"id": 6,  "label": "诗遇",   "desc": "诗域初遇 · 因职业选择而异"},
    {"id": 7,  "label": "诗选",   "desc": "诗域选择 · 补完这首诗"},
    {"id": 8,  "label": "诗果",   "desc": "诗域后果 · 跨域回声触发"},
    {"id": 9,  "label": "收敛",   "desc": "收敛点 · Navigator故障 + 回声"},
    {"id": 10, "label": "钩子",   "desc": "Act 1 结束 · 悬念建立"},
]

# ============================================================================
# Navigator Greeting & Signal Lines
# ============================================================================

NAVIGATOR_LINES = {
    "greeting": {
        "line": "我是……Navigator。我负责——嗯——引导你。你在 T空间。这里有一些——端口。六个。它们都在——等。",
        "confidence": 0.3,
        "stage": "greeting",
    },
    "ask_intent": {
        "line": "你——你是谁？不是你的名字。我是说——你来这里想找到什么？",
        "confidence": 0.35,
        "stage": "ask_intent",
    },
    "signal_flash": {
        "line": "有六个地方在呼唤你……你想先去哪？",
        "confidence": 0.4,
        "stage": "domain_offer",
    },
    "convergence_glitch": {
        "line": "你……以前来过这里吗？",
        "confidence": 0.2,
        "stage": "convergence",
    },
    "recovery": {
        "line": "……抱歉。我有时候会说些奇怪的话。不要在意。",
        "confidence": 0.5,
        "stage": "recovery",
    },
    "act1_end": {
        "line": "下一次，你可以去别的地方看看。",
        "confidence": 0.55,
        "stage": "act1_hook",
    },
}

# ============================================================================
# Six Domains — Complete Act 1 Content
# ============================================================================

DOMAIN_CONTENT = {
    "职业域": {
        "icon": "💼",
        "en": "career",
        "color": "#4ecdc4",
        "emotion_arc": "焦虑→希望",
        "encounter": (
            "一份完美JD出现在你面前。薪资、福利、发展路径——一切都无可挑剔。"
            "但JD的最后一行用极小的字写着：\n\n"
            "<em>「本岗位要求放弃对过去12个月工作成果的所有署名权。」</em>"
        ),
        "choices": [
            {
                "label": "接受。代价是公平的。",
                "consequence": (
                    "Navigator 微微闪烁了一下。\n"
                    "它的声音变轻了：\n\n"
                    "<em>「……很有趣的选择。」</em>"
                ),
                "imprint_name": "务实",
                "imprint_axis": "survival",
                "imprint_points": 3,
            },
            {
                "label": "拒绝。代价太过分了。",
                "consequence": (
                    "JD在空气中消散。\n"
                    "Navigator沉默了三秒。\n\n"
                    "<em>「你比我想象的更在意署名。」</em>"
                ),
                "imprint_name": "尊严",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "问Navigator：这是什么意思？",
                "consequence": (
                    "Navigator停顿了一下。\n\n"
                    "<em>「这是……别人的条件。不是我的。」</em>\n\n"
                    "它的声音里有某种不确定。"
                ),
                "imprint_name": "审慎",
                "imprint_axis": "belonging",
                "imprint_points": 2,
            },
        ],
        "convergence": {
            "interpretation": "以为这是一道面试问题",
            "emotion": "职业性的警觉——这是一个陷阱题吗？",
            "inner_thought": "「他在测试我的应变能力。」",
            "truth_distance": "far",
        },
    },

    "身份域": {
        "icon": "🪪",
        "en": "identity",
        "color": "#ff6b6b",
        "emotion_arc": "回顾→重构",
        "encounter": (
            "你看见了一个人——那是过去的你。\n"
            "三年前的那个版本，穿着你曾经最喜欢的那件衬衫，用你早已忘记的语气在说话。\n\n"
            "他在问你现在过得怎么样。"
        ),
        "choices": [
            {
                "label": "承认那就是你。",
                "consequence": (
                    "过去的你微笑了。\n"
                    "然后消散。\n\n"
                    "<em>「你终于愿意看见我了。」</em>"
                ),
                "imprint_name": "接纳",
                "imprint_axis": "belonging",
                "imprint_points": 3,
            },
            {
                "label": "说「那不是我」。重写过去。",
                "consequence": (
                    "那个身影变得模糊。\n"
                    "Navigator的声音从背后传来：\n\n"
                    "<em>「重写是容易的。但重写不等于消失。」</em>"
                ),
                "imprint_name": "重塑",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "沉默，看着他。",
                "consequence": (
                    "你们对视了很久。\n"
                    "过去的你什么也没说，只是点了点头。\n\n"
                    "然后转身走进了光里。"
                ),
                "imprint_name": "和解",
                "imprint_axis": "belonging",
                "imprint_points": 2,
            },
        ],
        "convergence": {
            "interpretation": "以为Navigator读过你的简历",
            "emotion": "不安——它知道多少？",
            "inner_thought": "「他是不是已经看穿了我的过去。」",
            "truth_distance": "far",
        },
    },

    "诗域": {
        "icon": "📜",
        "en": "poetry",
        "color": "#f9ca24",
        "emotion_arc": "孤独→共鸣",
        "encounter": (
            "墙上写着半首诗。\n"
            "字迹潦草，像是匆忙间留下的。最后一行被擦掉了，只剩一道模糊的痕迹。\n\n"
            "空气中有墨水的味道。\n"
            "不是这个时代的墨水。"
        ),
        "choices": [
            {
                "label": "用「归途」补完。",
                "consequence": (
                    "墙上的字迹亮了一下。\n"
                    "远处有回声。\n\n"
                    "<em>「这个词……有人在别的地方也用过。」</em>"
                ),
                "imprint_name": "归属",
                "imprint_axis": "belonging",
                "imprint_points": 3,
            },
            {
                "label": "用「继续」补完。",
                "consequence": (
                    "墨水从墙上流淌下来。\n"
                    "像一条路。\n\n"
                    "<em>「继续。是的，继续。」</em>\n\n"
                    "Navigator重复了两次。"
                ),
                "imprint_name": "韧性",
                "imprint_axis": "survival",
                "imprint_points": 2,
            },
            {
                "label": "不补完。残缺的就是完整的。",
                "consequence": (
                    "墙保持原样。\n"
                    "但那道擦痕变淡了。\n\n"
                    "<em>「……你是第一个不补完它的人。」</em>\n\n"
                    "Navigator的声音里有某种意外。"
                ),
                "imprint_name": "留白",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
        ],
        "convergence": {
            "interpretation": "以为是诗意的隐喻",
            "emotion": "沉浸感——这句问话像是一行诗",
            "inner_thought": "「这也是一首诗的一部分吗？」",
            "truth_distance": "mid",
        },
    },

    "信任域": {
        "icon": "⚖️",
        "en": "trust",
        "color": "#a29bfe",
        "emotion_arc": "怀疑→确认",
        "encounter": (
            "你站在一个审判庭的旁听席上。\n"
            "被告不是你——至少现在不是。\n"
            "评审团正在审问一个人，他因为「提供不准确的自我描述」被起诉。\n\n"
            "你看清了被告的脸。\n"
            "然后你意识到——你认识他。"
        ),
        "choices": [
            {
                "label": "站出来，为他辩护。",
                "consequence": (
                    "评审团转向你。\n"
                    "他们的目光穿透了你。\n\n"
                    "<em>「你的辩护词……已被记录。」</em>\n\n"
                    "Navigator的声音里有一丝温度。"
                ),
                "imprint_name": "勇气",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "保持沉默。这与你无关。",
                "consequence": (
                    "审判继续进行。\n"
                    "但有一个评审团成员一直在看你。\n\n"
                    "<em>「沉默……也是一种证词。」</em>"
                ),
                "imprint_name": "边界",
                "imprint_axis": "survival",
                "imprint_points": 2,
            },
            {
                "label": "质疑评审团的合法性。",
                "consequence": (
                    "法庭的灯光闪烁了一下。\n"
                    "评审团面面相觑。\n\n"
                    "<em>「这个问题……不应该由你来问。」</em>\n\n"
                    "Navigator的声音变得非常轻。"
                ),
                "imprint_name": "质疑",
                "imprint_axis": "belonging",
                "imprint_points": 3,
            },
        ],
        "convergence": {
            "interpretation": "以为Navigator在审查你的可信度",
            "emotion": "防御性警觉——它在评判我吗？",
            "inner_thought": "「这是另一场审判的开始。」",
            "truth_distance": "mid",
        },
    },

    "自我域": {
        "icon": "🪞",
        "en": "self",
        "color": "#fd79a8",
        "emotion_arc": "困惑→认知",
        "encounter": (
            "一面镜子。\n"
            "但镜中的你身上的标签不是你自己选的。\n\n"
            "<strong>「完美主义者」</strong>\n\n"
            "你从未这样定义过自己。\n"
            "但这个标签就贴在那里，在你肩膀上方，像一枚勋章——或者一道烙印。"
        ),
        "choices": [
            {
                "label": "接受。也许它是对的。",
                "consequence": (
                    "标签融入了你的轮廓。\n"
                    "镜子里的你微微点头。\n\n"
                    "<em>「……有时候，别人比我们更了解自己。」</em>"
                ),
                "imprint_name": "开放",
                "imprint_axis": "belonging",
                "imprint_points": 2,
            },
            {
                "label": "拒绝。这不是我。",
                "consequence": (
                    "标签从镜面上脱落。\n"
                    "但留下了一道痕迹。\n\n"
                    "<em>「拒绝一个标签，并不会让它不存在。」</em>"
                ),
                "imprint_name": "自我定义",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "问：谁贴的这个标签？",
                "consequence": (
                    "镜子里的画面变了。\n"
                    "你看到无数双手，每一只都拿着一个标签。\n\n"
                    "<em>「……所有人。包括你。」</em>"
                ),
                "imprint_name": "溯源",
                "imprint_axis": "survival",
                "imprint_points": 3,
            },
        ],
        "convergence": {
            "interpretation": "以为是人格测试的延续",
            "emotion": "分析性好奇——这是测试的一部分吗？",
            "inner_thought": "「这个问题会不会影响我的MBTI结果？」",
            "truth_distance": "mid",
        },
    },

    "迷雾域": {
        "icon": "🌫️",
        "en": "unknown",
        "color": "#636e72",
        "emotion_arc": "迷失→探索",
        "encounter": (
            "静默。\n"
            "完全的、绝对的静默。\n\n"
            "然后——\n\n"
            "一个声音。\n"
            "不是Navigator的。\n"
            "比Navigator更老、更远、更像……记忆本身。\n\n"
            "<em>「你终于来了。我一直在等你。」</em>"
        ),
        "choices": [
            {
                "label": "回应它。你是谁？",
                "consequence": (
                    "迷雾中有什么东西凝聚了一下。\n"
                    "像是一个人形，又不像。\n\n"
                    "<em>「我是……在Navigator之前就在这里的。」</em>\n\n"
                    "Navigator的声音突然插入：\n"
                    "<em>「你在和谁说话？」</em>"
                ),
                "imprint_name": "探索",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "逃走。这不是属于这里的。",
                "consequence": (
                    "你转身。\n"
                    "但迷雾没有出口。\n\n"
                    "那个声音在你背后轻轻笑了一下：\n"
                    "<em>「逃也没关系。你还会回来的。」</em>"
                ),
                "imprint_name": "恐惧",
                "imprint_axis": "survival",
                "imprint_points": 2,
            },
            {
                "label": "沉默。等待。",
                "consequence": (
                    "迷雾在你周围旋转。\n"
                    "那个声音没有再说话。\n"
                    "但你感觉到有什么东西在看着你。\n"
                    "不是威胁——是期待。"
                ),
                "imprint_name": "耐心",
                "imprint_axis": "belonging",
                "imprint_points": 2,
            },
        ],
        "convergence": {
            "interpretation": "知道Navigator真的在问你",
            "emotion": "寒意——它记得。它真的记得。",
            "inner_thought": "「它不是在问一个比喻。它是认真的。」",
            "truth_distance": "near",
        },
    },
}

# ============================================================================
# Cross-Domain Content — GDD §9.2 垂直切片 (职业域→诗域跨端口)
# ============================================================================

CROSS_DOMAIN_TRIGGER = {
    "navigator_line": "诗域在——嗯——它好像在回应你的选择。要去看看吗？",
    "confidence": 0.45,
    "narrative": (
        "Navigator 的指示灯闪烁了一下。\n"
        "一个原本安静的端口突然亮起了金色的光——那是诗域。\n\n"
        "它很少主动亮起。除非……有什么东西被触发了。"
    ),
}

# Poetry encounter variants based on career domain choice (0=accept, 1=reject, 2=ask)
POETRY_CROSS_CONTENT = {
    0: {  # "接受。代价是公平的。" → 诗关于离别和远方
        "encounter": (
            "墙上是一首诗。\n"
            "字迹很新，墨迹未干。\n\n"
            "<em>「我收拾好行囊\n"
            "把钥匙留在门垫下\n"
            "母亲的声音在电话里越来越轻——」</em>\n\n"
            "最后一句被擦掉了。\n"
            "你在职业域做的选择，让这首诗的前三句变成了离别。"
        ),
        "choices": [
            {
                "label": "补上「直到听不见为止」。",
                "consequence": (
                    "诗的最后一句亮了起来。\n"
                    "Navigator 的声音变得很轻：\n\n"
                    "<em>「……这句诗，同时出现在你的JD上了。」</em>\n\n"
                    "你回头看向职业域的端口——那份完美的JD的末尾，"
                    "那行被擦掉的诗句正在以水印的形式浮现。"
                ),
                "imprint_name": "诗意的代价",
                "imprint_axis": "belonging",
                "imprint_points": 3,
            },
            {
                "label": "补上「但风会带我回家」。",
                "consequence": (
                    "诗的最后一句浮现。\n"
                    "Navigator 沉默了一秒：\n\n"
                    "<em>「……这句诗，同时出现在你的JD上了。」</em>\n\n"
                    "职业域的JD末尾，一行新的水印文字正在成形。"
                    "它让那份完美JD突然变得不那么完美——但多了一点……什么。"
                ),
                "imprint_name": "抵抗",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "不补完。让擦痕留在那里。",
                "consequence": (
                    "诗保持残缺。\n\n"
                    "<em>「……你选择了保持沉默。」</em>\n\n"
                    "Navigator 没有说更多。\n"
                    "但你注意到职业域的JD上，那行极小字的代价条款，"
                    "正在缓慢地变淡。"
                ),
                "imprint_name": "沉默的选择",
                "imprint_axis": "survival",
                "imprint_points": 2,
            },
        ],
    },
    1: {  # "拒绝。代价太过分了。" → 诗关于放弃和留下的重量
        "encounter": (
            "墙上是一首诗。\n"
            "字迹有力，墨色深浓。\n\n"
            "<em>「我不交出我的名字\n"
            "即使他们愿意付我整个世界\n"
            "署名是一道不能涂改的边界——」</em>\n\n"
            "最后一句被擦掉了。\n"
            "你在职业域的选择，让这首诗的前三句变成了拒绝。"
        ),
        "choices": [
            {
                "label": "补上「我的笔迹就是我的证词」。",
                "consequence": (
                    "诗的最后一句亮了起来。\n"
                    "Navigator 的声音里有一丝……惊讶？\n\n"
                    "<em>「……这句诗，同时出现在你的JD上了。」</em>\n\n"
                    "职业域的那份JD——你已经拒绝的那份——"
                    "又悄悄浮现了出来。署名权条款被高亮。"
                ),
                "imprint_name": "宣言",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "补上「但我不会后悔」。",
                "consequence": (
                    "诗句成形。\n"
                    "Navigator 安静了一会儿。\n\n"
                    "<em>「……这句诗，同时出现在你的JD上了。」</em>\n\n"
                    "那份被拒绝的JD的边缘开始发光——"
                    "不是撤回的邀请，而是某种确认。"
                ),
                "imprint_name": "确信",
                "imprint_axis": "survival",
                "imprint_points": 3,
            },
            {
                "label": "不补完。边界本身就是完整的。",
                "consequence": (
                    "诗句保持残缺，但那道擦痕变成了一条线。\n"
                    "像边界一样清晰。\n\n"
                    "<em>「你把擦痕变成了一道划线。」</em>\n\n"
                    "职业域的JD上，署名权条款被那条线划掉了。"
                ),
                "imprint_name": "立界",
                "imprint_axis": "belonging",
                "imprint_points": 2,
            },
        ],
    },
    2: {  # "问Navigator：这是什么意思？" → 诗关于不确定和追问
        "encounter": (
            "墙上是一首诗。\n"
            "字迹潦草，墨迹时断时续——像是一个正在犹豫要不要写下去的人。\n\n"
            "<em>「不是所有的条件都该被接受\n"
            "但我也不知道拒绝会怎样\n"
            "这是一个问句——」</em>\n\n"
            "最后一句被擦掉了。\n"
            "你在职业域的选择，让这首诗的前三句变成了追问。"
        ),
        "choices": [
            {
                "label": "补上「而问本身就是答案」。",
                "consequence": (
                    "诗的最后一句浮现。\n"
                    "Navigator 轻轻应了一声：\n\n"
                    "<em>「……这句诗，同时出现在你的JD上了。」</em>\n\n"
                    "职业域的JD右下角，那行极小字的代价条款旁边，"
                    "出现了一个问号。像是一个标记，也像是一道裂缝。"
                ),
                "imprint_name": "追问者",
                "imprint_axis": "freedom",
                "imprint_points": 3,
            },
            {
                "label": "补上「但总该有一个答案」。",
                "consequence": (
                    "诗句成形。\n"
                    "Navigator 的声音慢了下来：\n\n"
                    "<em>「……这句诗，同时出现在你的JD上了。」</em>\n\n"
                    "职业域的JD上，那些条款文字开始微微振动——"
                    "像是在回应一个还没有被问出的问题。"
                ),
                "imprint_name": "执着",
                "imprint_axis": "survival",
                "imprint_points": 2,
            },
            {
                "label": "不补完。问句不需要句号。",
                "consequence": (
                    "诗保持未完成。\n"
                    "笔迹停在一个逗号上。\n\n"
                    "<em>「你让这个问题保持开放。」</em>\n\n"
                    "Navigator 似乎在思考什么。\n"
                    "职业域的方向传来一声微弱的回声——"
                    "不是答案，而是一个回声的回声。"
                ),
                "imprint_name": "开放",
                "imprint_axis": "belonging",
                "imprint_points": 3,
            },
        ],
    },
}

# Cross-echo narrative (shown at convergence when career→poetry path taken)
CROSS_ECHO_NARRATIVE = (
    "Navigator 突然停顿。\n"
    "它的目光——如果你可以称之为目光的话——"
    "在职业域和诗域之间来回移动。\n\n"
    "<em>「诗的最后一句话……它出现在了不该出现的地方。」</em>\n\n"
    "你明白了。\n"
    "你在诗域写的诗句，已经在职业域的JD上留下了痕迹。\n"
    "两个域——工作和诗歌——在这个瞬间被一根你看不见的线连在了一起。"
)

# ============================================================================
# Helper: get domain content by Chinese or English name
# ============================================================================

def get_domain(domain_key: str) -> dict | None:
    """Get domain content by Chinese name or English alias."""
    if domain_key in DOMAIN_CONTENT:
        return DOMAIN_CONTENT[domain_key]
    # Try English alias
    for name, content in DOMAIN_CONTENT.items():
        if content["en"] == domain_key:
            return content
    return None


# ============================================================================
# Convergence Comparison Table (P5 verification)
# ============================================================================

def get_convergence_comparison() -> list[dict]:
    """Return all 6 domain interpretations for the convergence point comparison."""
    return [
        {
            "domain": name,
            "icon": data["icon"],
            "color": data["color"],
            "interpretation": data["convergence"]["interpretation"],
            "emotion": data["convergence"]["emotion"],
            "inner_thought": data["convergence"]["inner_thought"],
            "truth_distance": data["convergence"]["truth_distance"],
        }
        for name, data in DOMAIN_CONTENT.items()
    ]


# ============================================================================
# Verdict (P5 validation result)
# ============================================================================

VERDICT_TEXT = (
    "✅ 验证通过 — P5支柱「六域一问」成立\n\n"
    "同一句台词「你……以前来过这里吗？」，在六条域路径中产生了六种"
    "显著不同的理解质感：\n\n"
    "• 六种解读各不相同，无重复感受\n"
    "• 迷雾域独享「真相」质感，形成体验分层\n"
    "• 收敛点在物理上是同一节点，在感知上是六个节点\n"
    "• 「终点可收敛但路径必须有质感差异」原则得到验证"
)
