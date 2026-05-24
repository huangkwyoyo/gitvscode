"""
全链路统一日志模块
支持：控制台+文件双输出、环境感知日志级别、结构化格式、旋转文件
"""
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config.mcp_config import ENV_MODE, ENV_CONFIG


def setup_logging(name: str = "spark_bigdata_crew") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, ENV_CONFIG.get("log_level", "INFO"), logging.INFO)
    logger.setLevel(log_level)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"pipeline_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()
