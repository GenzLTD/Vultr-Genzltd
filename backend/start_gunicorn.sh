#!/bin/bash
# backend/start_gunicorn.sh
# 内测环境gunicorn启动脚本

set -e

cd "$(dirname "$0")"

echo "🚀 启动Looma后端服务 (gunicorn)"
echo "工作目录: $(pwd)"

# 激活虚拟环境
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

# 检查Python环境
echo "Python版本: $(python --version)"
echo "Python路径: $(which python)"

# 设置环境变量
export FLASK_ENV=${FLASK_ENV:-production}
export PYTHONPATH="$PWD:$PYTHONPATH"

echo "环境配置:"
echo "  FLASK_ENV: $FLASK_ENV"
echo "  PYTHONPATH: $PYTHONPATH"

# 检查gunicorn是否安装
if ! python -c "import gunicorn" 2>/dev/null; then
    echo "安装gunicorn..."
    pip install gunicorn
fi

# 创建必要的目录
mkdir -p ../data ../logs

echo ""
echo "🔧 启动参数:"
echo "  绑定地址: 0.0.0.0:5200"
echo "  workers数: $(python -c "import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)")"
echo "  超时时间: 120s"
echo ""

# 启动gunicorn
echo "启动gunicorn..."
exec gunicorn \
    --config gunicorn_config.py \
    "src.app:create_app()"