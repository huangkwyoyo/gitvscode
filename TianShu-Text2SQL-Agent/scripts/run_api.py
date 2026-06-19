#!/usr/bin/env python
"""Phase 6B —— API 服务启动脚本。

用法：
    python scripts/run_api.py --config config/api_config.yml
    或：
    tianshu-api --config config/api_config.yml

安全默认：
    - 绑定 127.0.0.1:8000
    - 关闭 CORS
    - 不启用认证
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.app import main

if __name__ == "__main__":
    main()
