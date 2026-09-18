# backend/gunicorn_config.py
import multiprocessing
import os

# 工作进程数 = CPU核心数 × 2 + 1
workers = multiprocessing.cpu_count() * 2 + 1

# 工作进程类型
worker_class = "sync"

# 绑定地址和端口
bind = "0.0.0.0:5200"

# 超时设置（LLM请求可能较长）
timeout = 120

# 日志配置
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 进程名
proc_name = "looma-backend"

# 优雅重启
graceful_timeout = 30

# 最大并发请求数
worker_connections = 1000

# 预加载应用，减少fork后的内存占用和启动时间
preload_app = True

# 守护进程模式（生产环境推荐）
daemon = False  # 开发环境设为False便于调试

# 环境变量
raw_env = [
    f"FLASK_ENV={os.getenv('FLASK_ENV', 'production')}",
    f"PYTHONPATH={os.path.join(os.path.dirname(__file__), '..')}",
]

# 错误时重启worker
max_requests = 1000
max_requests_jitter = 50