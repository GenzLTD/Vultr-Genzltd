"""
中央大脑：意图解析 + 分发到内部能力端口。

设计原则：不以占位为长期方案。中央大脑需结合 LLM 进化——意图解析、多轮理解、
编排与反思均可由 LLM 承担，通过改 Prompt 或模型即可迭代；规则仅作无 key 或
LLM 失败时的回退，保证链路可跑通。
"""
import json
import random
import re
from typing import Any

from tatha.core.config import use_llm_intent
from tatha.core.llm import completion as llm_completion
from .schemas import AskRequest, AskResponse

# 支持的意图（与 LLM 的 system prompt 一致，便于进化）
INTENTS = ("job_match", "resume_upload", "poetry", "credit", "mbti", "unknown")

# 规则回退：关键词 → 意图（仅当 LLM 未启用或失败时使用）
INTENT_KEYWORDS = {
    "poetry": ["诗词", "诗人", "古诗", "推荐一句", "陪伴", "安慰", "思乡", "送别", "山水", "边塞", "励志", "一句诗"],
    "job_match": ["匹配", "职位", "找工作", "有没有适合", "岗位"],
    "resume_upload": ["上传", "简历", "解析简历"],
    "credit": ["征信", "信用", "验证"],
    "mbti": ["人格", "MBTI", "测评", "性格"],
}

# 诗词推荐时随机注入主题，避免「推荐一句诗」总返回同一首、结果跑空
POETRY_RECOMMEND_THEMES = ("思乡", "送别", "山水", "边塞", "咏物", "励志", "田园", "怀古")


def _poetry_is_recommendation_query(text: str) -> bool:
    """
    判断是否为「推荐一句诗」类短句（无诗词正文），以便注入随机主题，让推荐结果多样化。
    """
    if not (text and text.strip()) or len(text.strip()) > 80:
        return False
    t = text.strip()
    return bool(re.search(r"推荐|来一句|来首|随便.*诗|一句诗", t))


def _parse_intent_llm(message: str) -> tuple[str, float, dict[str, Any]] | None:
    """
    用 LLM 解析意图（主路径）。返回 (intent, confidence, slots) 或 None（失败时回退）。
    通过改 prompt 或模型即可让中央大脑进化，无需改代码逻辑。
    """
    try:
        system = (
            "你是一个意图分类器。根据用户输入，输出且仅输出一个 JSON 对象，不要其他文字。"
            "JSON 必须包含：\"intent\"（取值仅限: job_match, resume_upload, poetry, credit, mbti, unknown），"
            "\"confidence\"（0 到 1 的浮点数），可选 \"slots\"（对象，如 {\"query\": \"...\"}）。"
            "job_match=求职/职位匹配，resume_upload=上传或解析简历，poetry=诗词/诗人/陪伴，credit=征信/验证，mbti=人格测评。"
        )
        resp = llm_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": message.strip() or "（无输入）"},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        # 允许被 markdown 代码块包裹
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        data = json.loads(text)
        intent = (data.get("intent") or "unknown").lower()
        if intent not in INTENTS:
            intent = "unknown"
        confidence = float(data.get("confidence", 0.5))
        slots = data.get("slots") if isinstance(data.get("slots"), dict) else {}
        return (intent, confidence, slots)
    except Exception:
        return None


def _parse_intent_rules(message: str) -> str:
    """规则回退：关键词匹配。"""
    msg = (message or "").strip().lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            return intent
    return "unknown"


def parse_intent(message: str) -> tuple[str, float, dict[str, Any]]:
    """
    解析用户消息得到意图 + 置信度 + 槽位。
    主路径：LLM（可进化）；回退：规则（保证无 key 时也能跑）。
    """
    if use_llm_intent():
        out = _parse_intent_llm(message)
        if out is not None:
            return out
    intent = _parse_intent_rules(message)
    return (intent, 0.8 if intent != "unknown" else 0.3, {})


def _document_analysis(document_type: str, text: str) -> dict[str, Any] | None:
    """
    文档解读：优先 PydanticAI（result_type 数据边界），回退 Marvin（JSON schema 动态）。
    返回可序列化的 dict，无有效结果时返回 None。
    """
    from tatha.core.config import document_analysis_backend
    backend = document_analysis_backend()
    if backend == "pydantic_ai":
        try:
            from tatha.agents import run_document_analysis
            data = run_document_analysis(document_type, text)
            return data.model_dump() if data else None
        except Exception:
            backend = "marvin"
    if backend == "marvin":
        _ensure_extractors_loaded()
        from tatha.ai.fn_from_schema import get_extractor
        extract_fn = get_extractor(document_type)
        if not extract_fn:
            return None
        out = extract_fn(text)
        if out and not out.get("_placeholder"):
            return out
    return None


def _credit_has_document_body(text: str) -> bool:
    """
    判断是否为「信用报告/文档片段」而非短句查询。
    仅当文本像报告内容（含主体/报告类型/摘要等，或足够长）时才返回 True，
    避免把「查一下征信」等短句当正文解析导致结果不稳定。
    """
    if not (text and text.strip()):
        return False
    t = text.strip()
    # 过短且无报告特征：视为查询语
    if len(t) < 25:
        return False
    # 含报告常见字段/用语则视为有正文
    report_markers = ("主体", "报告类型", "摘要", "信用报告", "信用代码", "信用等级", "经营状态", "无不良")
    if any(m in t for m in report_markers):
        return True
    # 较长且含「信用/征信」可能是一段描述
    if len(t) >= 40 and ("信用" in t or "征信" in t):
        return True
    return False


def _ensure_extractors_loaded() -> None:
    """懒加载：若尚未根据 schema 生产函数，则加载默认或配置的 schema 并生产。"""
    from tatha.ai.fn_from_schema import REGISTRY
    if REGISTRY.get("_loaded"):
        return
    from tatha.core.config import get_extractors_schema_path
    path = get_extractors_schema_path()
    if path:
        from tatha.ai.fn_from_schema import load_and_produce
        load_and_produce(path=path)
    REGISTRY["_loaded"] = True


def dispatch(intent: str, request: AskRequest, slots: dict[str, Any] | None = None) -> dict[str, Any]:
    """按意图分发到内部能力端口，返回 result 字典（能力实现可逐步接入）。"""
    slots = slots or {}
    text = (request.message or "").strip() or (slots.get("text") or slots.get("content") or "")

    if intent == "job_match":
        resume_text = (
            (request.resume_text or "").strip()
            or (request.context or {}).get("resume_text") or ""
            or (slots.get("resume_text") or slots.get("resume") or "")
        )
        if not resume_text:
            return {
                "message": "请先提供简历内容",
                "status": "pending",
                "hint": "可通过上传简历（POST /v1/documents/convert）或在本请求中传入 resume_text / context.resume_text",
                "slots": slots,
            }
        try:
            from tatha.jobs import run_job_match_pipeline
            from tatha.core.config import job_top_n

            results, total = run_job_match_pipeline(resume_text=resume_text, top_n=job_top_n())
            matches = [r.model_dump() for r in results]
            return {
                "message": "已根据简历完成职位匹配",
                "status": "ok",
                "matches": matches,
                "total_evaluated": total,
                "slots": slots,
            }
        except Exception as e:
            return {"message": "职位匹配失败", "status": "error", "error": str(e), "slots": slots}
    if intent == "resume_upload":
        if text:
            try:
                extracted = _document_analysis("resume", text)
                if extracted is not None:
                    return {"message": "已解析简历结构化信息", "status": "ok", "extracted": extracted, "slots": slots}
                return {"message": "简历解析未返回结果", "status": "pending", "hint": "请检查 .env 中 OPENAI/DEEPSEEK 等 API Key 及 TATHA_DOCUMENT_ANALYSIS_BACKEND", "slots": slots}
            except Exception as e:
                return {"message": "简历解析失败", "status": "error", "error": str(e), "slots": slots}
        return {"message": "简历上传与解析服务开发中", "status": "pending", "hint": "V0 将接入 MarkItDown + 解析", "slots": slots}
    if intent == "poetry":
        if text:
            try:
                # 直接导入 chroma_poetry（独立模块，不依赖 llama_index）
                from tatha.retrieval.chroma_poetry import search_poems

                # 确定检索关键词
                search_query = text
                if _poetry_is_recommendation_query(text):
                    theme = random.choice(POETRY_RECOMMEND_THEMES)
                    search_query = theme

                # RAG 检索
                poems = search_poems(search_query, n_results=3)
                if poems:
                    # 用检索结果构建上下文，交给 LLM 生成推荐
                    context = "\n\n".join(
                        f"【{p['dynasty']}】{p['title']} — {p['author']}\n{p['content']}"
                        for p in poems
                    )
                    prompt = (
                        f"从以下诗词中挑选最合适的一首推荐给用户。用户查询：{text}\n\n"
                        f"候选诗词：\n{context}\n\n"
                        f"请以 JSON 格式返回：title（标题）、author（作者）、dynasty（朝代）、"
                        f"content（选其中最有代表性的两句）、theme（主题如思乡/送别/励志等）。只输出 JSON。"
                    )
                    try:
                        resp = llm_completion(
                            messages=[
                                {"role": "system", "content": "你是诗词推荐助手，只输出 JSON。"},
                                {"role": "user", "content": prompt},
                            ],
                        )
                        resp_text = (resp.choices[0].message.content or "").strip()
                        # 清理 markdown 包裹
                        if "```" in resp_text:
                            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp_text)
                            if m:
                                resp_text = m.group(1).strip()
                        extracted = json.loads(resp_text)
                        return {"message": "已为您推荐诗词", "status": "ok", "extracted": extracted, "slots": slots}
                    except Exception:
                        # LLM 失败则直接返回检索结果
                        best = poems[0]
                        return {
                            "message": "已为您检索诗词",
                            "status": "ok",
                            "extracted": {
                                "title": best["title"],
                                "author": best["author"],
                                "dynasty": best["dynasty"],
                                "content": best["content"][:100],
                                "theme": search_query,
                            },
                            "slots": slots,
                        }
                return {"message": "未找到匹配的诗词", "status": "pending", "hint": "请尝试其他主题词", "slots": slots}
            except Exception as e:
                return {"message": "诗词检索失败", "status": "error", "error": str(e), "slots": slots}
        return {"message": "诗人/诗词推荐已就绪", "status": "pending", "hint": "请描述您想找的诗词主题，如「推荐一句思乡的诗」", "slots": slots}
    if intent == "credit":
        # 仅当消息像「信用报告/文档片段」时才调用解析；短句查询（如「查一下征信」）视为无正文
        if _credit_has_document_body(text):
            try:
                extracted = _document_analysis("credit", text)
                if extracted is not None:
                    return {"message": "已解析征信相关信息", "status": "ok", "extracted": extracted, "slots": slots}
                return {"message": "征信解析未返回结果", "status": "pending", "hint": "请检查 API Key 与 TATHA_DOCUMENT_ANALYSIS_BACKEND", "slots": slots}
            except Exception as e:
                return {"message": "征信解析失败", "status": "error", "error": str(e), "slots": slots}
        return {"message": "征信/验证服务开发中", "status": "pending", "hint": "请提供信用报告摘要或主体/报告类型/摘要等文本后再解析", "slots": slots}
    if intent == "mbti":
        from tatha.agents.mbti_analyzer import MBTITextAnalyzer, MIN_TEXT_LENGTH
        from tatha.agents.mbti_career_match import get_career_match

        if text and len(text.strip()) >= MIN_TEXT_LENGTH:
            try:
                analyzer = MBTITextAnalyzer()
                analysis = analyzer.analyze_text(text)
                # 旧实现此处判断 mbti_type != "XXXX"，但 XXXX 只在正文 < 20 字时出现，
                # 而该路径已被外层 MIN_TEXT_LENGTH 拦截 → 守卫恒为真（死代码），
                # 导致「零关键词」文本也被当作分析完成并给出职业建议。
                # 现改为按 analyzer 显式返回的 status 分流：
                if analysis.get("status") == "ok":
                    career = get_career_match(analysis["mbti_type"])
                    extracted = {**analysis, "career_match": career}
                    return {
                        "message": "已根据您的描述完成性格分析并给出职业建议",
                        "status": "ok",
                        "extracted": extracted,
                        "slots": slots,
                    }
                if analysis.get("status") == "partial":
                    pending_axes = "、".join(analysis.get("undetermined_axes") or [])
                    return {
                        "message": "已识别部分性格维度，尚不足以给出确定类型",
                        "status": "pending",
                        "hint": f"以下维度信号不足：{pending_axes}。"
                        "请补充描述您的做事风格、决策方式或社交偏好，以获得完整类型与职业建议",
                        "extracted": analysis,
                        "slots": slots,
                    }
                return {
                    "message": "描述中未检测到可用于判断性格类型的信号",
                    "status": "pending",
                    "hint": "请用更具体的说法描述自己（如「我习惯先做计划再动手」「我喜欢独立思考」"
                    "「我做事看重逻辑」），至少 20 字，我再为您分析",
                    "extracted": analysis,
                    "slots": slots,
                }
            except Exception as e:
                return {"message": "人格测评分析失败", "status": "error", "error": str(e), "slots": slots}
        return {
            "message": "职业人格测评已就绪",
            "status": "pending",
            "hint": "请描述您的做事风格或发一段自述（至少20字），我会帮您分析性格类型并给出职业建议",
            "slots": slots,
        }
    return {"message": "暂未识别到明确意图", "status": "unknown", "received": (request.message or "")[:100]}


def handle_ask(request: AskRequest) -> AskResponse:
    """单入口处理：解析意图（LLM 主路径 + 规则回退）→ 分发 → 统一响应。"""
    intent, confidence, slots = parse_intent(request.message)
    result = dispatch(intent, request, slots)
    result["confidence"] = confidence
    suggestions = []
    if intent == "unknown":
        suggestions.append("可以说：帮我匹配职位、上传简历、推荐一句诗 等")
    return AskResponse(intent=intent, result=result, suggestions=suggestions)
