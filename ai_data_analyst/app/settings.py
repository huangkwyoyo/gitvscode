import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
STATIC_DIR = BASE_DIR / "frontend"
TEMPLATE_DIR = BASE_DIR / "templates"

for path in [UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATE_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# 上传限制
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 50 * 1024 * 1024))  # 默认 50MB
MAX_JOBS = int(os.getenv("MAX_JOBS", 50))  # 并发任务上限

# 金融分析基准
TRADING_DAYS = int(os.getenv("TRADING_DAYS", 252))  # 年交易日数
RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", 0.015))  # 无风险利率（中国金融市场常用一年期定存利率）

# 滚动收益窗口配置（交易日数）
ROLLING_WINDOWS = {
    "3个月": int(os.getenv("ROLLING_WINDOW_3M", 63)),
    "6个月": int(os.getenv("ROLLING_WINDOW_6M", 126)),
    "1年": int(os.getenv("ROLLING_WINDOW_1Y", 252)),
}

# 前端图表默认尺寸
CHART_DEFAULT_WIDTH = int(os.getenv("CHART_WIDTH", 520))
CHART_DEFAULT_HEIGHT = int(os.getenv("CHART_HEIGHT", 260))

