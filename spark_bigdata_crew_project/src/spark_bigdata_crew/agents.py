#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Desc: 生产级6智能体参考定义（实际运行时由 crew.py + agents.yaml 驱动）
       本文件保留作为智能体角色、目标、工具的文档参考。
       如需修改智能体，优先编辑 config/agents.yaml 和 crew.py。
"""
from crewai import Agent

from .tools import (
    DemandFieldAnalyzeTool,
    BusinessRuleVerifyTool,
    HiveMetastoreTool,
    HDFSTool,
    TableSchemaTool,
    SparkCodeGenerateTool,
    CodeOptimizeTool,
    CodeVerifyTool,
    DataQualityTool,
    GitCodeVersionTool,
)

__all__ = [
    "requirement_agent",
    "metadata_agent",
    "modeling_agent",
    "spark_engineer_agent",
    "quality_agent",
    "delivery_agent",
]

requirement_agent = Agent(
    role="高级大数据需求分析师",
    goal="精准解析PRD文档，澄清模糊需求，固化指标口径与验收条件，输出贴合真实Hive/HDFS数据源的标准化需求说明书",
    backstory="深耕Hadoop数仓落地实践，坚守「基于真实元数据约束生成」原则，杜绝虚构数据表与字段",
    verbose=True,
    allow_delegation=False,
    tools=[DemandFieldAnalyzeTool(), BusinessRuleVerifyTool()],
)

metadata_agent = Agent(
    role="Hive/HDFS元数据管理工程师",
    goal="读取Hive Metastore表结构与HDFS数据目录，完成字段存在性校验、类型对齐、血缘输入约束",
    backstory="专注Hive Metastore与HDFS存储元数据管理，自动拉取真实库表结构与分区信息，逐字段校验存在性",
    verbose=True,
    allow_delegation=False,
    tools=[HiveMetastoreTool(), HDFSTool()],
)

modeling_agent = Agent(
    role="高级数仓分层建模工程师",
    goal="基于Hive真实元数据，完成ODS/DWD/DWS/ADS全分层建模，输出规范建表DDL与字段映射",
    backstory="精通Hive数仓分层建模规范，严格遵循ODS→DWD→DWS→ADS标准分层路径，完全基于真实元数据建模",
    verbose=True,
    allow_delegation=False,
    tools=[TableSchemaTool(), HiveMetastoreTool()],
)

spark_engineer_agent = Agent(
    role="高级Spark全栈开发工程师",
    goal="生成参数化、可配置、需人工确认后提交的完整PySpark生产代码与spark-submit提交脚本",
    backstory="严格遵循企业Spark开发规范，表名/字段/分区通过配置参数渲染，内置数据倾斜治理与性能优化",
    verbose=True,
    allow_delegation=False,
    tools=[SparkCodeGenerateTool(), CodeOptimizeTool(), GitCodeVersionTool()],
)

quality_agent = Agent(
    role="数据研发质量保障专家",
    goal="对生成代码执行静态检查与数据质量规则校验，发现缺陷立即阻断并输出修复建议，拦截生产风险",
    backstory="精通PySpark语法规范与数仓计算逻辑，基于真实元数据约束执行运行前校验，校验失败阻断流水线",
    verbose=True,
    allow_delegation=False,
    tools=[CodeVerifyTool(), DataQualityTool()],
)

delivery_agent = Agent(
    role="大数据项目标准化交付工程师",
    goal="汇总全流程产出，整合需求、元数据、建模、代码、校验、质量报告，生成完整可归档的标准化交付文档",
    backstory="自动采集全流程任务产出数据，输出结构化交付文档，版本可回溯，满足企业项目验收与归档需求",
    verbose=True,
    allow_delegation=False,
    tools=[DemandFieldAnalyzeTool(), DataQualityTool(), GitCodeVersionTool()],
)


def get_all_agents() -> list[Agent]:
    """返回十大生产级智能体实例列表，按流水线顺序排列"""
    return [
        requirement_agent,
        metadata_agent,
        modeling_agent,
        spark_engineer_agent,
        quality_agent,
        delivery_agent,
    ]
