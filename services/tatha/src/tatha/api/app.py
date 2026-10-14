"""
Tatha 主仓 HTTP 入口：供 ZeroClaw 助理 Tool 调用。

架构：单入口 + 中央大脑。用户/助理只调用一个入口（POST /v1/ask），
需求由中央大脑解析并分发到内部各能力端口（解析、匹配、诗人 RAG、征信等），
内部实现与端口对用户不可见。

文档上传：POST /v1/documents/convert 使用 MarkItDown 转 Markdown，并可选做结构化提取（如简历）。

可选演示页：GET /demo.html 返回单文件 demo.html（与 API 同源，便于浏览器直接体验匹配结果）。
"""
import io
import os
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from .auth import AuthContext, get_auth
from .quota import (
    RESOURCE_ASK,
    RESOURCE_JOB_MATCH,
    RESOURCE_MBTI,
    RESOURCE_RAG,
    RESOURCE_RESUME_PARSE,
    consume,
    clamp_top_n,
)
from .region import get_region_response
from .schemas import (
    AskRequest,
    AskResponse,
    AuthLoginRequest,
    AuthRegisterRequest,
    DocumentConvertResponse,
    JobMatchRequest,
    JobMatchResponse,
    MbtiAnalyzeRequest,
    MbtiAnalyzeResponse,
    RagQueryRequest,
    RagQueryResponse,
    SkillIngestResponse,
)
from .central_brain import handle_ask
from ..core.config import assert_signal_bridge_ready

app = FastAPI(
    title="Tatha API",
    description="Tatha 主仓：单入口 + 中央大脑，简历解析、匹配、诗人/诗词 RAG",
    version="0.1.0",
)

# ---------- CORS ----------
# 前端部署在独立域名（如 Vercel）时浏览器跨域调用 /v1/* 需要此处放行。
# 环境变量 TATHA_CORS_ORIGINS：逗号分隔的来源列表，如
#   TATHA_CORS_ORIGINS=https://tatha.vercel.app,https://xxx.vercel.app
# 未配置时默认放行所有来源（Bearer token 鉴权、无 Cookie，风险可控）；
# 上线后建议收紧为实际前端域名。
_cors_env = os.getenv("TATHA_CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# 生产门禁：REQUIRE_SIGNAL_HMAC=true 且 SIGNAL_BRIDGE_SECRET 为空时，
# 在 import（即 uvicorn 启动）阶段抛错，进程无法启动，堵死免签进生产。
assert_signal_bridge_ready()


# 项目根目录（便于同源提供 demo.html，避免 CORS；app.py 在 src/tatha/api/）
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


@app.get("/health")
def health():
    """探活：唯一对外端口下的健康检查。"""
    return {"status": "ok", "service": "tatha"}


def _serve_html(filename: str):
    path = os.path.join(_ROOT, filename)
    if not os.path.isfile(path):
        return PlainTextResponse(f"{filename} not found", status_code=404)
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def serve_index():
    """认证订阅入口页：三档（免费/Basic/Pro），参考 ServBay 定价页形态。"""
    return _serve_html("index.html")


@app.get("/demo.html", response_class=HTMLResponse)
def serve_demo():
    """可选演示页：单文件 HTML，调用 /v1/ask 与 /v1/jobs/match 并在页面展示结果。仅用于开发期直观感受。"""
    return _serve_html("demo.html")


@app.get("/auth.html", response_class=HTMLResponse)
def serve_auth():
    """登录/注册页：Web 端登录注册测试用，当前为演示桩，未对接真实认证。"""
    return _serve_html("auth.html")


@app.get("/v1/region")
def region(request: Request):
    """
    按请求 IP 返回地区与定价，供订阅页展示币种与价格。无需鉴权。
    国内（CN）返回 CNY + pricing_cn，境外返回 USD + pricing_intl。
    """
    return get_region_response(request)


def _supabase_auth_enabled() -> bool:
    """Phase 2: Supabase Auth 已配置时返回 True。"""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))


def _supabase_sign_in(email: str, password: str) -> dict:
    """
    Phase 2 接入点：调用 Supabase Auth REST API 做真实登录。
    环境变量：SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    文档：https://supabase.com/docs/reference/javascript/auth-signinwithpassword
    """
    import urllib.request, json as _json
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/token?grant_type=password"
    body = _json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = _json.loads(resp.read().decode())
    return data  # contains access_token, user, etc.


def _supabase_sign_up(email: str, password: str) -> dict:
    """
    Phase 2 接入点：调用 Supabase Auth REST API 做真实注册。
    """
    import urllib.request, json as _json
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/signup"
    body = _json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = _json.loads(resp.read().decode())
    return data


@app.post("/v1/auth/login")
def auth_login(request: AuthLoginRequest):
    """
    登录：
    - Phase 1（default）：演示桩，格式校验后返回 demo-token。
    - Phase 2（配置 SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY）：转发 Supabase Auth，返回真实 JWT。
    """
    if _supabase_auth_enabled():
        try:
            data = _supabase_sign_in(request.email or "", request.password or "")
            token = data.get("access_token")
            if not token:
                err = data.get("error_description") or data.get("msg") or "Login failed"
                raise HTTPException(status_code=401, detail=err)
            return {"ok": True, "message": "Signed in", "token": token}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail=str(e))
    # Demo stub (Phase 1)
    return {
        "ok": True,
        "message": "登录成功（演示用，未对接真实认证）",
        "token": "demo-token-" + (request.email or "").replace("@", "-at-")[:32],
    }


@app.post("/v1/auth/register")
def auth_register(request: AuthRegisterRequest):
    """
    注册：
    - Phase 1（default）：演示桩，格式校验后返回 demo-token。
    - Phase 2（配置 SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY）：转发 Supabase Auth 注册。
    """
    if _supabase_auth_enabled():
        try:
            data = _supabase_sign_up(request.email or "", request.password or "")
            token = data.get("access_token")
            if not token:
                err = data.get("error_description") or data.get("msg") or "Registration failed"
                raise HTTPException(status_code=400, detail=err)
            return {"ok": True, "message": "Account created", "token": token}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    # Demo stub (Phase 1)
    return {
        "ok": True,
        "message": "注册成功（演示用，未对接真实认证）",
        "token": "demo-token-" + (request.email or "").replace("@", "-at-")[:32],
    }


def _quota_exceeded_response():
    return HTTPException(
        status_code=429,
        detail={
            "code": "quota_exceeded",
            "message": "当日配额已用尽，请升级后继续使用。",
        },
    )


@app.post("/v1/ask", response_model=AskResponse)
def ask(request: AskRequest, auth: AuthContext = Depends(get_auth)):
    """单入口：用户需求由此进入，中央大脑解析意图并分发到内部端口，返回统一 JSON。V1 需鉴权与配额。"""
    if not consume(auth.user_id, auth.tier, RESOURCE_ASK):
        raise _quota_exceeded_response()
    return handle_ask(request)


@app.post("/v1/mbti/analyze", response_model=MbtiAnalyzeResponse)
def mbti_analyze(request: MbtiAnalyzeRequest, auth: AuthContext = Depends(get_auth)):
    """16 型人格测评（小工具）：一段自述 → MBTI 类型 + 花语 + 职业建议。

    与 /v1/ask 分开计量：独立配额 resource=mbti，免费档可体验，basic/pro 额度更高，
    不必与文档问答争抢 ask 的每日额度。响应为结构化契约，不再塞进 ask 的通用信封。

    三态契约：ok 才给花语与职业建议；partial 列出缺信号的轴；insufficient 明确不给结论
    （无信号时猜类型等于把噪声当结论展示）。
    """
    if not consume(auth.user_id, auth.tier, RESOURCE_MBTI):
        raise _quota_exceeded_response()

    from tatha.agents.mbti_analyzer import MBTITextAnalyzer
    from tatha.agents.mbti_career_match import get_career_match

    analysis = MBTITextAnalyzer().analyze_text(request.text)
    status = analysis.get("status", "insufficient")
    undetermined = list(analysis.get("undetermined_axes") or [])

    if status == "ok":
        message = "已根据您的描述完成性格分析并给出职业建议"
        hint = None
        career = get_career_match(analysis.get("mbti_type", ""))
    elif status == "partial":
        message = "已识别部分性格维度，尚不足以给出确定类型"
        hint = (
            "以下维度信号不足："
            + "、".join(undetermined)
            + "。请补充描述您的做事风格、决策方式或社交偏好，以获得完整类型与职业建议"
        )
        career = None
    else:
        message = "描述中未检测到可用于判断性格类型的信号"
        hint = (
            "请用更具体的说法描述自己（如「我习惯先做计划再动手」「我喜欢独立思考」"
            "「我做事看重逻辑」），至少 20 字，我再为您分析"
        )
        career = None

    return MbtiAnalyzeResponse(
        status=status,
        message=message,
        hint=hint,
        mbti_type=analysis.get("mbti_type", "XXXX"),
        flower_personality=analysis.get("flower_personality"),
        flower_traits=analysis.get("flower_traits") or [],
        mbti_confidence=analysis.get("mbti_confidence"),
        undetermined_axes=undetermined,
        insufficient_reason=analysis.get("insufficient_reason"),
        career_match=career,
    )


@app.post("/v1/documents/convert", response_model=DocumentConvertResponse)
async def documents_convert(
    file: UploadFile = File(..., description="待转换文档（PDF/Word/Excel 等）"),
    document_type: str | None = Form("resume", description="文档类型：resume / poetry / credit，用于选择提取器"),
    auth: AuthContext = Depends(get_auth),
):
    """
    高效解析标准流程：MarkItDown 多格式 → Markdown，再按 document_type 做可选结构化提取。
    V1 需鉴权与配额（resume 类型计入简历解析配额）。
    """
    dtype = (document_type or "resume").strip().lower() or "resume"
    if dtype == "resume" and not consume(auth.user_id, auth.tier, RESOURCE_RESUME_PARSE):
        raise _quota_exceeded_response()
    try:
        content = await file.read()
    except Exception as e:
        return DocumentConvertResponse(markdown="", error=f"读取文件失败: {e}")
    if not content:
        return DocumentConvertResponse(markdown="", error="文件为空")

    try:
        from tatha.ingest.markitdown_convert import stream_to_markdown

        markdown = stream_to_markdown(
            io.BytesIO(content),
            filename=file.filename or None,
        )
    except Exception as e:
        return DocumentConvertResponse(markdown="", error=f"MarkItDown 转换失败: {e}")

    extracted = None
    if dtype and markdown:
        try:
            from tatha.api.central_brain import _document_analysis
            extracted = _document_analysis(dtype, markdown)
        except Exception as e:
            return DocumentConvertResponse(
                markdown=markdown,
                document_type=dtype,
                error=f"结构化提取失败: {e}",
            )

    return DocumentConvertResponse(
        markdown=markdown,
        document_type=dtype,
        extracted=extracted,
    )


@app.post("/v1/jobs/match", response_model=JobMatchResponse)
def jobs_match(request: JobMatchRequest, auth: AuthContext = Depends(get_auth)):
    """
    职位匹配流水线：拉取职位 → 简历 vs 职位 LLM 打分 → 按综合分排序返回 Top-N。V1 需鉴权与配额。
    top_n 按档位限制（Free≤3，Basic≤5，Pro≤20）；超配额返回 429。
    """
    if not consume(auth.user_id, auth.tier, RESOURCE_JOB_MATCH):
        raise _quota_exceeded_response()
    top_n = clamp_top_n(auth.tier, request.top_n or 5)
    try:
        from tatha.jobs import run_job_match_pipeline

        verified_skills = None
        if request.user_id_hash:
            try:
                from tatha.evidence import get_store

                verified_skills = get_store().get_verified_skills(request.user_id_hash)
            except Exception:
                verified_skills = None

        results, total = run_job_match_pipeline(
            resume_text=request.resume_text,
            top_n=top_n,
            source_id=request.source,
            user_id_hash=request.user_id_hash,
        )
        return JobMatchResponse(
            matches=[r.model_dump() for r in results],
            total_evaluated=total,
            verified_skills=verified_skills,
        )
    except Exception as e:
        return JobMatchResponse(matches=[], total_evaluated=0, error=str(e))


@app.post("/v1/skills/ingest", response_model=SkillIngestResponse)
async def skills_ingest(request: Request):
    """
    Guibu egress 落点：摄入技能学习证据（skill-proof.v1）。

    安全：
    - HMAC 验签：X-Signature = HMAC-SHA256(SIGNAL_BRIDGE_SECRET, raw_body)。
      配置 SIGNAL_BRIDGE_SECRET 则强制验签；未配置走 dev 免签（verified=false，仅本地冒烟）。
    - 幂等：唯一键 (signal_type, user_id_hash, nonce)，重复摄入返回 duplicate。

    信封（JSON body）：
      { "signal_type": "skill_proof", "user_id_hash": "<sha256(email)>",
        "nonce": "<uuid>", "payload": { ...skill-proof.v1... } }
    """
    from tatha.core.config import signal_bridge_secret
    from tatha.evidence import (
        SIGNAL_TYPE_SKILL_PROOF,
        SignalEnvelope,
        get_store,
        verify_signature,
    )

    raw_body = await request.body()

    secret = signal_bridge_secret()
    signature = request.headers.get("X-Signature")
    if secret:
        if not verify_signature(secret, raw_body, signature):
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_signature", "message": "HMAC 验签失败"},
            )
        verified = True
    else:
        verified = False  # dev 免签模式（未配置 SIGNAL_BRIDGE_SECRET）

    try:
        envelope = SignalEnvelope.model_validate_json(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_envelope", "message": f"信封或 payload 不符合契约: {e}"},
        )

    if envelope.signal_type != SIGNAL_TYPE_SKILL_PROOF:
        raise HTTPException(
            status_code=422,
            detail={"code": "unsupported_signal", "message": f"仅支持 signal_type={SIGNAL_TYPE_SKILL_PROOF}"},
        )
    if envelope.user_id_hash != envelope.payload.user_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "user_id_mismatch", "message": "user_id_hash 与 payload.user_id 不一致"},
        )

    store = get_store()
    row, created = store.insert(
        envelope.signal_type,
        envelope.user_id_hash,
        envelope.nonce,
        envelope.payload.model_dump(),
    )
    return SkillIngestResponse(
        status="stored" if created else "duplicate",
        evidence_id=int(row["id"]),
        evidence_count=store.count_for_user(envelope.user_id_hash),
        skill_tags=store.distinct_skill_tags(envelope.user_id_hash),
        verified=verified,
    )


@app.post("/v1/rag/query", response_model=RagQueryResponse)
def rag_query(request: RagQueryRequest, auth: AuthContext = Depends(get_auth)):
    """
    对私有索引做 RAG 查询：仅使用已构建的命名空间索引，数据不离开本地。V1 需鉴权与配额。
    """
    if not consume(auth.user_id, auth.tier, RESOURCE_RAG):
        raise _quota_exceeded_response()
    try:
        from tatha.retrieval import get_query_engine
        engine = get_query_engine(namespace=request.namespace)
        answer = str(engine.query(request.query))
        return RagQueryResponse(answer=answer, namespace=request.namespace)
    except FileNotFoundError:
        return RagQueryResponse(
            answer="",
            namespace=request.namespace,
            error=f"索引不存在。请先用 build_index_from_dir 或 build_index_from_documents 构建 namespace={request.namespace} 的索引（存储于 .data/indices/<namespace>）。",
        )
    except Exception as e:
        return RagQueryResponse(
            answer="",
            namespace=request.namespace,
            error=str(e),
        )


# ============ IoT 设备控制（MVP 暂不启用）============
# 以下路由依赖 src/tatha/iot/ 模块（尚未实现），MVP 阶段注释掉
#
# @app.post("/api/v1/intent-parse", ...)
# @app.post("/api/v1/device/command", ...)
# @app.post("/api/v1/scene/trigger", ...)
# @app.get("/api/v1/mqtt/status")
# @app.post("/api/v1/mqtt/connect")
