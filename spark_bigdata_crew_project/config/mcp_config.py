#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Project: spark_bigdata_crew_project
@File: mcp_config.py
@Desc: MCP全局上下文协议配置、环境隔离、全局参数兜底、流水线参数透传
@Feature: 环境变量优先、双层参数兜底、全局上下文开关、多环境适配、防幻觉配置
@Author:
@Date: 2026-05-24
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

# 加载项目根目录.env全局环境变量
load_dotenv()

# ====================== 全局环境基础配置 ======================
# 运行环境：dev/test/prod
ENV_MODE: str = os.getenv("ENV_MODE", "dev")
# 调试模式开关
DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
# 项目根路径
PROJECT_ROOT: str = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# ====================== MCP核心协议全局配置 ======================
class MCPGlobalConfig:
    """
    MCP全局协议统一配置类
    核心能力：统一参数管理、双层兜底、全流水线上下文透传、防幻觉约束
    """
    # 全局上下文总开关（控制全流程参数缓存与复用）
    GLOBAL_CONTEXT_ENABLE: bool = True

    # 上下文存储最大缓存条数（防止内存溢出）
    CONTEXT_MAX_CACHE_NUM: int = 200

    # 任务执行超时时间（秒）
    TASK_EXEC_TIMEOUT: int = 1800

    # ====================== 数据源全局默认兜底参数 ======================
    # 默认数据源类型
    DEFAULT_DS_TYPE: str = "mysql"
    # 默认业务数据库
    DEFAULT_DB_NAME: str = os.getenv("DEFAULT_DB_NAME", "test_db")

    # ====================== Spark生产全局兜底参数 ======================
    # 默认Shuffle分区数
    DEFAULT_SPARK_SHUFFLE_PARTITIONS: int = 200
    # 单分区最大文件字节数（128MB）
    DEFAULT_MAX_PARTITION_BYTES: int = 134217728
    # 自适应合并最小分区数
    DEFAULT_MIN_COALESCE_PART_NUM: int = 10

    # ====================== 数据校验全局兜底参数 ======================
    # 默认数据抽样条数
    DEFAULT_SAMPLE_LIMIT: int = 100
    # 默认开启空数据校验
    DEFAULT_CHECK_EMPTY: bool = True
    # 默认开启重复数据校验
    DEFAULT_CHECK_DUPLICATE: bool = True

    # ====================== Git版本迭代全局参数 ======================
    # Git代码仓库路径
    GIT_REPO_PATH: str = os.path.join(PROJECT_ROOT, "spark_code_git_repo")
    # 默认版本迭代备注
    DEFAULT_ITERATE_DESC: str = "Spark生产代码迭代优化｜MCP自动流水线生成"

    # ====================== 输出目录全局配置 ======================
    # 交付物输出根目录
    OUTPUT_ROOT_PATH: str = os.path.join(PROJECT_ROOT, "output")
    # 报告输出子目录
    REPORT_OUTPUT_PATH: str = os.path.join(OUTPUT_ROOT_PATH, "reports")
    # 代码输出子目录
    CODE_OUTPUT_PATH: str = os.path.join(OUTPUT_ROOT_PATH, "spark_code")

# ====================== 环境差异化配置 ======================
def get_env_custom_config() -> Dict[str, Any]:
    """
    根据运行环境返回差异化配置
    dev: 全开调试、宽松校验
    test: 标准校验、日志全开
    prod: 严格校验、关闭调试、性能优先
    """
    if ENV_MODE == "dev":
        return {
            "debug": True,
            "strict_verify": False,
            "log_level": "DEBUG",
            "auto_fix_error": True
        }
    elif ENV_MODE == "test":
        return {
            "debug": False,
            "strict_verify": True,
            "log_level": "INFO",
            "auto_fix_error": True
        }
    else:
        return {
            "debug": False,
            "strict_verify": True,
            "log_level": "WARN",
            "auto_fix_error": False
        }

# 初始化环境配置
ENV_CONFIG = get_env_custom_config()

# ====================== 全局统一导出 ======================
__all__ = [
    "ENV_MODE",
    "DEBUG",
    "PROJECT_ROOT",
    "MCPGlobalConfig",
    "ENV_CONFIG"
]
