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

# 磁盘清理配置
JOB_RETENTION_HOURS = int(os.getenv("JOB_RETENTION_HOURS", 24))  # 作业文件保留时间

# 数据预览与探索限制
PREVIEW_MAX_ROWS = int(os.getenv("PREVIEW_MAX_ROWS", 25))  # 预览行数
MAX_CORR_MATRIX_COLS = int(os.getenv("MAX_CORR_MATRIX_COLS", 20))  # 相关性矩阵最大列数
MAX_CATEGORY_COLS = int(os.getenv("MAX_CATEGORY_COLS", 12))  # 分类列展示上限
MAX_CATEGORY_VALUES = int(os.getenv("MAX_CATEGORY_VALUES", 8))  # 分类值展示上限
MAX_VIS_HISTOGRAM_COLS = int(os.getenv("MAX_VIS_HISTOGRAM_COLS", 4))  # 直方图最大列数
MAX_VIS_BAR_COLS = int(os.getenv("MAX_VIS_BAR_COLS", 4))  # 条形图最大列数
MAX_TOP_CORRELATIONS = int(os.getenv("MAX_TOP_CORRELATIONS", 10))  # 展示的最高相关对数

# 频率检测阈值（每年平均数据点数范围）
FREQUENCY_THRESHOLDS = {
    "daily": (
        int(os.getenv("FREQ_DAILY_LOW", 200)),
        int(os.getenv("FREQ_DAILY_HIGH", 260)),
    ),
    "weekly": (
        int(os.getenv("FREQ_WEEKLY_LOW", 40)),
        int(os.getenv("FREQ_WEEKLY_HIGH", 60)),
    ),
    "monthly": (
        int(os.getenv("FREQ_MONTHLY_LOW", 10)),
        int(os.getenv("FREQ_MONTHLY_HIGH", 14)),
    ),
}

# 各频率对应的年化乘数
FREQUENCY_MULTIPLIER = {
    "daily": int(os.getenv("FREQ_MULT_DAILY", 252)),
    "weekly": int(os.getenv("FREQ_MULT_WEEKLY", 52)),
    "monthly": int(os.getenv("FREQ_MULT_MONTHLY", 12)),
    "quarterly": int(os.getenv("FREQ_MULT_QUARTERLY", 4)),
    "insufficient": 0,  # 数据不足时不进行年化计算
}

