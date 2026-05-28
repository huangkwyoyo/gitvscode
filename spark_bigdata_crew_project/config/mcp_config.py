#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Project: spark_bigdata_crew_project
@File: mcp_config.py
@Desc: 全局配置管理（MCP改为可选辅助模块，核心状态由workflow/state.py + checkpoints管理）
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# ====================== 全局环境基础配置 ======================
ENV_MODE: str = os.getenv("ENV_MODE", "dev")
DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
PROJECT_ROOT: str = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# ====================== MCP可选辅助配置 ======================
class MCPGlobalConfig:
    """MCP全局配置（可选辅助模块，不作为核心状态中心）"""
    GLOBAL_CONTEXT_ENABLE: bool = os.getenv("MCP_ENABLE", "False").lower() == "true"
    CONTEXT_MAX_CACHE_NUM: int = 200
    TASK_EXEC_TIMEOUT: int = 1800

    # ====================== Hive默认兜底参数 ======================
    DEFAULT_HIVE_DATABASE: str = os.getenv("HIVE_DATABASE", "default")

    # ====================== Spark生产默认参数 ======================
    DEFAULT_SPARK_SHUFFLE_PARTITIONS: int = 200
    DEFAULT_MAX_PARTITION_BYTES: int = 134217728
    DEFAULT_MIN_COALESCE_PART_NUM: int = 10

    # ====================== 数据校验默认参数 ======================
    DEFAULT_SAMPLE_LIMIT: int = 100
    DEFAULT_CHECK_EMPTY: bool = True
    DEFAULT_CHECK_DUPLICATE: bool = True

    # ====================== Git版本管理 ======================
    GIT_REPO_PATH: str = os.path.join(PROJECT_ROOT, "spark_code_git_repo")
    DEFAULT_ITERATE_DESC: str = "Spark生产代码迭代优化"

    # ====================== 输出目录配置 ======================
    OUTPUT_ROOT_PATH: str = os.path.join(PROJECT_ROOT, "output")
    REPORT_OUTPUT_PATH: str = os.path.join(OUTPUT_ROOT_PATH, "reports")
    CODE_OUTPUT_PATH: str = os.path.join(OUTPUT_ROOT_PATH, "spark_code")


def get_env_custom_config() -> Dict[str, Any]:
    """根据运行环境返回差异化配置"""
    if ENV_MODE == "dev":
        return {"debug": True, "strict_verify": False, "log_level": "DEBUG"}
    elif ENV_MODE == "test":
        return {"debug": False, "strict_verify": True, "log_level": "INFO"}
    else:  # prod
        return {"debug": False, "strict_verify": True, "log_level": "WARN"}


ENV_CONFIG = get_env_custom_config()

__all__ = ["ENV_MODE", "DEBUG", "PROJECT_ROOT", "MCPGlobalConfig", "ENV_CONFIG"]
