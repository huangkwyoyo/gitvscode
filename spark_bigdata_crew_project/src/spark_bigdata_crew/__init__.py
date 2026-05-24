# -*- coding: utf-8 -*-
"""
@Project: spark_bigdata_crew_project
@File: __init__.py
@Desc: 大数据智能体核心模块统一入口、全局导出
@Author:
@Date: 2026-05-24
"""

# 核心模块统一导出
from .crew import SparkBigDataEnterpriseCrew as SparkBigDataCrew
from .agents import get_all_agents
from .tasks import get_all_tasks

__version__ = "1.0.0"
__all__ = [
    "SparkBigDataCrew",
    "get_all_agents",
    "get_all_tasks"
]
