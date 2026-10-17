"""
单入口 /v1/ask 的请求与响应模型。
"""
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional


class AskRequest(BaseModel):
    """用户/助理发往中央大脑的请求。"""
    message: str = Field(..., description="用户输入或意图描述")
    context: Optional[dict[str, Any]] = Field(default_factory=dict, description="可选上下文（user_id、session_id、resume_text 等）")
    resume_text: Optional[str] = Field(None, description="可选：用于 job_match 的简历全文，也可放在 context.resume_text")


class AskResponse(BaseModel):
    """中央大脑统一返回格式。"""
    intent: str = Field(..., description="解析出的意图")
    result: dict[str, Any] = Field(default_factory=dict, description="能力端口返回的结果")
    suggestions: list[str] = Field(default_factory=list, description="可选：后续建议或提示")
    port: Optional[str] = Field(
        None,
        description="GFCC ask.envelope.v1 的一等端口（memory 等）；契约 1.3.0 把 intent 归为 port 的别名，"
        "本字段先并存、不替代 intent",
    )


class DocumentConvertResponse(BaseModel):
    """文档上传转 Markdown + 可选结构化提取的响应。"""
    markdown: str = Field(..., description="MarkItDown 转换后的 Markdown 全文")
    document_type: str | None = Field(None, description="请求的文档类型（如 resume）")
    extracted: dict[str, Any] | None = Field(None, description="若为 resume/poetry/credit 等且已配置提取器，则返回结构化结果")
    error: str | None = Field(None, description="转换或提取失败时的错误信息")


class RagQueryRequest(BaseModel):
    """私有数据 RAG 查询请求。"""
    namespace: str = Field(..., description="索引命名空间，如 resume、poetry")
    query: str = Field(..., description="自然语言查询，如「总结文档的核心观点」")


class RagQueryResponse(BaseModel):
    """RAG 查询响应。"""
    answer: str = Field(..., description="基于私有索引检索后的回答")
    namespace: str = Field(..., description="查询的命名空间")
    error: str | None = Field(None, description="查询失败时的错误信息")


class JobMatchRequest(BaseModel):
    """POST /v1/jobs/match 请求（也可通过 /v1/ask 的 job_match 意图触发）。"""
    resume_text: str = Field(..., description="简历全文或摘要")
    top_n: Optional[int] = Field(5, ge=1, le=20, description="返回前 N 条匹配")
    source: Optional[str] = Field(None, description="职位源：mock | apify_linkedin，不传用配置")
    user_id_hash: Optional[str] = Field(None, description="可选：sha256(email) 用户哈希，传入则按 Guibu 证据增强简历")


class JobMatchResponse(BaseModel):
    """POST /v1/jobs/match 响应。"""
    matches: list[dict[str, Any]] = Field(default_factory=list, description="按综合分排序的匹配列表")
    total_evaluated: int = Field(0, description="参与打分的职位数")
    verified_skills: Optional[list[dict[str, Any]]] = Field(None, description="传入 user_id_hash 时返回：已验证技能 + 证据引用")
    message: Optional[str] = None
    error: Optional[str] = None


class SkillIngestResponse(BaseModel):
    """POST /v1/skills/ingest 响应。"""
    status: Literal["stored", "duplicate"] = Field(..., description="stored=新写入；duplicate=幂等命中已有记录")
    evidence_id: int = Field(..., description="skills_evidence 记录 id")
    evidence_count: int = Field(..., description="该用户累计摄入的 skill-proof 记录数")
    skill_tags: list[str] = Field(default_factory=list, description="该用户累计去重 skill_tags")
    verified: bool = Field(True, description="HMAC 验签是否通过；dev 免签模式下为 False")


class AuthLoginRequest(BaseModel):
    """POST /v1/auth/login 请求（Web 端登录测试用）。"""
    email: str = Field(..., description="邮箱")
    password: str = Field(..., description="密码")


class AuthRegisterRequest(BaseModel):
    """POST /v1/auth/register 请求（Web 端注册测试用）。"""
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, description="密码，至少 6 位")


class MbtiAnalyzeRequest(BaseModel):
    """POST /v1/mbti/analyze 请求：一段自述文本。"""
    text: str = Field(..., description="自述文本，建议 ≥20 字：做事风格、决策方式、社交偏好等")


class MbtiAnalyzeResponse(BaseModel):
    """POST /v1/mbti/analyze 响应：16 型人格测评结果。

    三态契约：只有 status=ok 时才给出 career_match 与花语，
    partial / insufficient 不给结论（无信号时猜类型等于把噪声当结论展示）。
    """
    status: Literal["ok", "partial", "insufficient"] = Field(..., description="ok=四轴齐全；partial=部分轴缺信号；insufficient=无信号")
    message: str = Field(..., description="面向用户的回话")
    hint: Optional[str] = Field(None, description="partial / insufficient 时的引导话术")
    mbti_type: str = Field(..., description="四字母类型；缺轴以 X 占位，无信号为 XXXX")
    flower_personality: Optional[str] = Field(None, description="花语人格；非 ok 时为「待分析」")
    flower_traits: list[str] = Field(default_factory=list, description="花语关键词")
    mbti_confidence: Optional[float] = Field(None, description="置信度 0–100")
    undetermined_axes: list[str] = Field(default_factory=list, description="partial / insufficient 时信号不足的轴，如 E/I")
    insufficient_reason: Optional[str] = Field(None, description="text_too_short / no_keyword_signal / all_axes_tied")
    career_match: Optional[dict[str, list[str]]] = Field(None, description="仅 status=ok 时给出：suitable_careers / work_style / strengths / growth_areas")


# ============ IoT 设备控制 ============


class IntentParseRequest(BaseModel):
    """POST /api/v1/intent-parse：自然语言 → 设备命令/场景识别。"""
    message: str = Field(..., description="自然语言输入，如「开灯」「打开影院模式」")
    device_id: Optional[str] = Field(None, description="目标设备 ID，不传则尝试自动识别")
    context: Optional[dict[str, Any]] = Field(default_factory=dict, description="可选上下文（user_id、devices 等）")


class IntentParseResponse(BaseModel):
    """意图解析响应。"""
    intent: str = Field(..., description="意图类型：device_control | scene_trigger | unknown")
    parsed_command: Optional[dict[str, Any]] = Field(None, description="解析后的设备命令")
    scene_id: Optional[str] = Field(None, description="场景 ID（如有）")
    scene_name: Optional[str] = Field(None, description="场景名称（如有）")
    confidence: float = Field(..., description="置信度 0.0-1.0")
    message: str = Field(..., description="解析结果描述")
    raw_command: Optional[dict[str, Any]] = Field(None, description="MQTT 原始命令")


class DeviceCommandRequest(BaseModel):
    """POST /api/v1/device/command：直接下发设备控制命令。"""
    device_id: str = Field(..., description="设备 ID")
    action: str = Field(..., description="动作：power_on | power_off | brightness | temperature 等")
    value: Optional[int | str] = Field(None, description="参数值（如亮度百分比、温度数值）")
    device_type: Optional[str] = Field(None, description="设备类型：light | ac | curtain 等")


class DeviceCommandResponse(BaseModel):
    """设备命令响应。"""
    status: str = Field(..., description="执行状态：ok | error")
    device_id: str = Field(..., description="设备 ID")
    command: dict[str, Any] = Field(..., description="执行的命令")
    message: str = Field(..., description="执行结果描述")


class SceneTriggerRequest(BaseModel):
    """POST /api/v1/scene/trigger：触发预设场景。"""
    scene_id: str = Field(..., description="场景 ID：morning | night | away | movie | work")
    devices: Optional[list[str]] = Field(None, description="指定执行的设备 ID 列表，不传则执行所有")


class SceneTriggerResponse(BaseModel):
    """场景触发响应。"""
    status: str = Field(..., description="执行状态：ok | error")
    scene_id: str = Field(..., description="场景 ID")
    scene_name: str = Field(..., description="场景名称")
    actions: list[dict[str, Any]] = Field(default_factory=list, description="动作列表")
    message: str = Field(..., description="执行结果描述")
