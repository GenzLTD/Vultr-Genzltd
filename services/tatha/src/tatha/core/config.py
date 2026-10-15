"""
配置：从环境变量读取，供中央大脑与各能力模块使用。
"""
import os
from pathlib import Path

# 可选加载 .env（若存在）：先项目根（与 pyproject.toml 同层），再当前工作目录
_env_paths = [
    Path(__file__).resolve().parents[2] / ".env",  # 从 src/tatha/core 往上的项目根
    Path.cwd() / ".env",
]
for _p in _env_paths:
    if _p.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_p)
            break
        except Exception:
            pass

# 中央大脑：是否用 LLM 做意图解析（有任一 key 且为 true 时走 LLM，否则规则回退）
def use_llm_intent() -> bool:
    key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
    )
    use = os.getenv("TATHA_USE_LLM_INTENT", "true").lower() in ("true", "1", "yes")
    return bool(key) and use


def get_default_model() -> str:
    return os.getenv("TATHA_DEFAULT_MODEL", "openai/gpt-4o")


def get_extractors_schema_path() -> Path | None:
    """提取器/分类器 JSON schema 路径；为空则使用默认示例路径（若存在）。"""
    env_path = os.getenv("TATHA_EXTRACTORS_SCHEMA")
    if env_path:
        p = Path(env_path)
        return p if p.exists() else None
    default = Path(__file__).resolve().parents[2] / "config" / "extractors_schema.example.json"
    return default if default.exists() else None


def document_analysis_backend() -> str:
    """文档解读后端：pydantic_ai（类型安全边界，默认）或 marvin（由 JSON schema 动态生成）。"""
    return (os.getenv("TATHA_DOCUMENT_ANALYSIS_BACKEND") or "pydantic_ai").strip().lower()


def embed_model_type() -> str:
    """
    索引/检索用的 embedding 模型类型。
    openai = 使用 OpenAI embedding（需 OPENAI_API_KEY）；
    local = 使用本地 HuggingFace（无需 API Key，适配仅配置 DeepSeek 的场景）。
    """
    return (os.getenv("TATHA_EMBED_MODEL") or "local").strip().lower()


def job_source_id() -> str:
    """职位源：mock（默认，无需 Key）| apify_linkedin（需 APIFY_API_KEY）。"""
    return (os.getenv("TATHA_JOB_SOURCE") or "mock").strip().lower()


def job_top_n() -> int:
    """匹配结果返回条数，默认 5。"""
    try:
        return max(1, min(20, int(os.getenv("TATHA_JOB_TOP_N", "5"))))
    except ValueError:
        return 5


def get_index_storage_root() -> Path:
    """
    私有索引存储根目录（简历等敏感数据仅存于此，不提交到仓库）。
    默认：项目根（与 pyproject.toml 同层）下的 .data/indices；可通过 TATHA_INDEX_STORAGE 覆盖。
    """
    env_path = os.getenv("TATHA_INDEX_STORAGE")
    if env_path:
        return Path(env_path)
    # src/tatha/core/config.py -> parents[3] = 项目根
    return Path(__file__).resolve().parents[3] / ".data" / "indices"


def signal_bridge_secret() -> str | None:
    """
    Guibu ↔ Tatha 信号桥 HMAC 密钥（X-Signature）。
    未配置时，POST /v1/skills/ingest 进入 dev 免签模式（仅本地冒烟用，响应中标记 verified=false）。
    """
    return os.getenv("SIGNAL_BRIDGE_SECRET") or None


def require_signal_hmac() -> bool:
    """生产门禁开关：REQUIRE_SIGNAL_HMAC=true 时，密钥缺失则拒绝启动。"""
    return os.getenv("REQUIRE_SIGNAL_HMAC", "false").lower() in ("true", "1", "yes")


def assert_signal_bridge_ready() -> None:
    """
    生产环境门禁：REQUIRE_SIGNAL_HMAC=true 且未配置 SIGNAL_BRIDGE_SECRET 时抛错，
    在服务启动阶段即拒绝启动，堵死「免签进生产」这条路（而非等到 ingest 请求时才暴露）。
    """
    if require_signal_hmac() and not signal_bridge_secret():
        raise RuntimeError(
            "REQUIRE_SIGNAL_HMAC=true 但 SIGNAL_BRIDGE_SECRET 为空："
            "生产环境禁止 HMAC 免签，拒绝启动。请配置 SIGNAL_BRIDGE_SECRET（>=32 字符）。"
        )


def get_evidence_db_path() -> Path:
    """
    skills_evidence 表（SQLite）路径；可通过 TATHA_EVIDENCE_DB 覆盖。
    默认：项目根 .data/skills_evidence.db（.data/ 已 gitignore，证据不入库）。
    """
    env_path = os.getenv("TATHA_EVIDENCE_DB")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[3] / ".data" / "skills_evidence.db"
