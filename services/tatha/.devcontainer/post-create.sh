#!/usr/bin/env bash
# Tatha Codespace 启动后的一次性引导脚本
# 目的：把"环境就绪"的等待时间压在 60 秒内
# 设计原则：幂等、可重跑、失败不阻断 shell

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

# ===== Step 1: 必备系统工具 =====
echo "[1/5] 系统工具检测..."
if ! command -v curl >/dev/null; then
    apt-get update -qq && apt-get install -y -qq curl wget postgresql-client
fi

# ===== Step 2: Python venv + 依赖 =====
echo "[2/5] Python venv 与依赖..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi
source .venv/bin/activate
python -m pip install --quiet --upgrade pip uv

# uv.lock 已存在，优先用 uv sync（比 pip 快 5-10x）
if command -v uv >/dev/null && [ -f uv.lock ]; then
    echo "  用 uv sync 安装依赖..."
    uv sync --frozen 2>&1 | tail -5 || python -m pip install -r requirements.txt
else
    echo "  fallback pip install..."
    python -m pip install --quiet -r requirements.txt
fi

# ===== Step 3: 前端依赖（静态站但有 npm 工具）=====
echo "[3/5] 前端工具检查..."
if [ ! -d "node_modules" ]; then
    npm install --no-audit --no-fund --silent 2>/dev/null || echo "  无 npm 依赖，跳过"
fi

# ===== Step 4: Vercel CLI（部署用，ADR-0004）=====
echo "[4/5] Vercel CLI..."
if ! command -v vercel >/dev/null 2>&1; then
    npm install -g --silent vercel@latest 2>&1 | tail -3 || echo "  Vercel CLI 安装失败（不影响本地开发）"
fi

# ===== Step 5: 配置文件提示 =====
echo "[5/5] 配置文件..."
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null && echo "  已生成 .env（基于 .env.example，请填入真实 key）"
fi

echo ""
echo "===================================="
echo "✅ Tatha Codespace 就绪"
echo ""
echo "下一步:"
echo "  source .venv/bin/activate"
echo "  uvicorn tatha.api.app:app --host 0.0.0.0 --port 8010 --reload"
echo ""
echo "端口转发:"
echo "  - 8010 (FastAPI) - 转发并通知"
echo "  - 8080 (Frontend Static) - 静默转发"
echo "===================================="