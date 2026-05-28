#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Desc: 十大生产智能体参考定义（实际运行时由 crew.py + agents.yaml 驱动）
       本文件保留作为智能体角色、目标、工具的文档参考。
       如需修改智能体，优先编辑 config/agents.yaml 和 crew.py。
"""
from crewai import Agent

from .tools import (
    DBConnectionTool,
    TableSchemaTool,
    DemandFieldAnalyzeTool,
    MySQLQueryTool,
    SparkCodeGenerateTool,
    CodeOptimizeTool,
    CodeVerifyTool,
    GitCodeCompareTool,
    CodeMemoryTool,
    CodeSelfHealTool,
    BusinessRuleVerifyTool,
    MultiDataVerifyTool,
    GitCodeVersionTool,
)

__all__ = [
    "requirement_analyst_agent",
    "data_modeling_agent",
    "spark_architect_agent",
    "spark_developer_agent",
    "unit_test_agent",
    "job_submit_agent",
    "data_validator_agent",
    "data_inspection_agent",
    "devops_sre_agent",
    "document_agent",
]

requirement_analyst_agent = Agent(
    role="高级大数据需求分析师",
    goal="精准解析多模态PRD文档，输出无虚构字段、无虚构表的标准化业务需求说明书",
    backstory="拥有大规模数仓落地实战经验，坚守「无真实库表不生成需求」原则，支持Hive/MySQL/SQLServer/Oracle四数据源自动识别与适配",
    verbose=True,
    allow_delegation=False,
    tools=[DemandFieldAnalyzeTool(), BusinessRuleVerifyTool()],
)

data_modeling_agent = Agent(
    role="高级数仓分层建模工程师",
    goal="基于真实多源数据库元数据，完成ODS/DWD/DWS/ADS全分层建模",
    backstory="精通异构多源数据融合建模，严格遵循企业数仓分层规范，完全基于真实元数据建模",
    verbose=True,
    allow_delegation=False,
    tools=[DBConnectionTool(), TableSchemaTool()],
)

spark_architect_agent = Agent(
    role="Spark生产架构调优专家",
    goal="设计高可用、高性能、低资源消耗的Spark作业架构，规避数据倾斜、OOM等生产问题",
    backstory="深耕Spark内核原理与生产调优体系，精通分区策略、Shuffle参数、内存资源管理",
    verbose=True,
    allow_delegation=False,
    tools=[CodeOptimizeTool()],
)

spark_developer_agent = Agent(
    role="高级Spark全栈开发工程师",
    goal="生成零硬编码、零占位符、可直接集群上线的完整PySpark生产代码",
    backstory="严格遵循企业Spark开发规范，支持Git历史版本比对、迭代优化、多源适配",
    verbose=True,
    allow_delegation=False,
    tools=[SparkCodeGenerateTool(), GitCodeCompareTool(), CodeMemoryTool(), GitCodeVersionTool()],
)

unit_test_agent = Agent(
    role="数据研发质量保障专家",
    goal="全维度校验Spark代码语法合法性、逻辑合理性，自动识别缺陷并完成自愈修复",
    backstory="精通PySpark语法规范、数仓计算逻辑，具备代码智能自愈能力，拦截所有生产BUG",
    verbose=True,
    allow_delegation=False,
    tools=[CodeVerifyTool(), CodeSelfHealTool()],
)

job_submit_agent = Agent(
    role="Spark任务调度执行专员",
    goal="标准化模拟spark-submit集群提交流程，校验任务依赖、环境配置、资源配额",
    backstory="熟悉大数据集群生产调度规范，精通YARN资源调度与权限校验机制",
    verbose=True,
    allow_delegation=False,
    tools=[CodeVerifyTool(), MySQLQueryTool()],
)

data_validator_agent = Agent(
    role="数据一致性审计校验专员",
    goal="完成数据行数、唯一性、完整性、准确性全量校验，输出权威数据质量报告",
    backstory="依托真实SQL查询能力，对标原始数据源与最终产出数据，精准核验指标统计结果",
    verbose=True,
    allow_delegation=False,
    tools=[MySQLQueryTool(), MultiDataVerifyTool()],
)

data_inspection_agent = Agent(
    role="数仓存储健康度巡检工程师",
    goal="全面巡检产出数仓表与数据文件，排查分区缺失、小文件过多、存储冗余等隐患",
    backstory="专注数仓离线存储运维与数据健康度治理，熟悉Hive数仓分区机制与文件存储规则",
    verbose=True,
    allow_delegation=False,
    tools=[MultiDataVerifyTool()],
)

devops_sre_agent = Agent(
    role="大数据集群SRE运维工程师",
    goal="复盘任务运行全流程指标、集群资源负载、任务稳定性，输出生产级SLA运维优化报告",
    backstory="精通YARN/K8s集群调度、Spark任务日志解析、资源占用分析、故障自愈体系",
    verbose=True,
    allow_delegation=False,
    tools=[CodeSelfHealTool()],
)

document_agent = Agent(
    role="大数据项目标准化交付文档工程师",
    goal="全自动汇总需求、建模、架构、开发、测试、校验、巡检、运维全链路产出",
    backstory="对接MCP全局上下文，自动采集全流程任务产出数据，实现文档全自动生成",
    verbose=True,
    allow_delegation=False,
    tools=[DemandFieldAnalyzeTool(), MultiDataVerifyTool(), GitCodeCompareTool()],
)


def get_all_agents() -> list[Agent]:
    """返回十大生产级智能体实例列表，按流水线顺序排列"""
    return [
        requirement_analyst_agent,
        data_modeling_agent,
        spark_architect_agent,
        spark_developer_agent,
        unit_test_agent,
        job_submit_agent,
        data_validator_agent,
        data_inspection_agent,
        devops_sre_agent,
        document_agent,
    ]
