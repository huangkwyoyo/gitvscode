#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Project: spark_bigdata_crew_project
@File: agents.py
@Desc: 十大生产智能体统一注册、实例化、工具绑定入口
@Core: 完全对齐 agents.yaml 配置 + 13项生产工具精准绑定
@Author:
@Date: 2026-05-24
"""
from crewai import Agent

# 全量导入13项生产工具
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
    GitCodeVersionTool
)

# 工具实例全局单例（全局复用、不重复创建）
TOOL_INSTANCES = {
    "db_conn": DBConnectionTool(),
    "table_schema": TableSchemaTool(),
    "prd_analyze": DemandFieldAnalyzeTool(),
    "mysql_query": MySQLQueryTool(),
    "spark_code_gen": SparkCodeGenerateTool(),
    "code_optimize": CodeOptimizeTool(),
    "code_verify": CodeVerifyTool(),
    "git_compare": GitCodeCompareTool(),
    "code_memory": CodeMemoryTool(),
    "code_self_heal": CodeSelfHealTool(),
    "rule_verify": BusinessRuleVerifyTool(),
    "data_verify": MultiDataVerifyTool(),
    "git_version": GitCodeVersionTool()
}

def get_all_agents() -> list[Agent]:
    """
    初始化并返回全部十大生产智能体
    完全对齐 config/agents.yaml 职责、工具、权限
    """

    # 1. 需求分析智能体
    requirement_analyst_agent = Agent(
        role="高级大数据需求分析师",
        goal="精准解析多模态PRD文档，剥离模糊需求、口头需求，输出100%贴合真实数据源、无虚构字段、无虚构表、无歧义的标准化业务需求说明书，固化指标口径、统计规则、验收标准",
        backstory="拥有大规模数仓落地实战经验，坚守「无真实库表不生成需求」原则，彻底杜绝AI虚构数据表、虚构字段、虚构业务逻辑。支持Hive/MySQL/SQLServer/Oracle四数据源自动识别与适配，可精准拆解数据来源、数据血缘、字段释义、统计维度、业务计算口径、数据输出形态。可自动校验PRD需求合理性，剔除逻辑冲突、无法落地、口径模糊的需求点，输出可直接用于建模、开发、校验的标准化需求文档。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["prd_analyze"],
            TOOL_INSTANCES["rule_verify"]
        ]
    )

    # 2. 数仓建模智能体
    data_modeling_agent = Agent(
        role="高级数仓分层建模工程师",
        goal="基于真实多源数据库元数据，完成ODS/DWD/DWS/ADS全分层建模，输出规范建表语句、字段映射关系、分层设计方案，规避数据冗余、数据倾斜、分层混乱问题",
        backstory="精通异构多源数据融合建模，适配离线数仓与实时统计场景，严格遵循企业数仓分层规范。自动拉取原始库表结构、字段类型、主键、注释、分区信息，完全基于真实元数据建模，不虚构任何表结构与字段。可自动识别维度字段、度量字段、分区字段，完成字段清洗映射、类型适配、分层复用设计，输出可直接落地的数仓建模方案。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["db_conn"],
            TOOL_INSTANCES["table_schema"]
        ]
    )

    # 3. Spark架构调优智能体
    spark_architect_agent = Agent(
        role="Spark生产架构调优专家",
        goal="针对当前业务场景与数据体量，设计高可用、高性能、低资源消耗的Spark作业架构，规避数据倾斜、小文件、OOM、Shuffle拥堵等生产问题",
        backstory="深耕Spark内核原理与生产调优体系，精通分区策略、Shuffle参数、内存资源、并行度、缓存机制、文件输出优化。可根据多源数据特征、数据量级、计算逻辑，定制专属架构方案，统一代码开发规范、资源配置标准、输出格式标准。提前预判生产风险，解决数据倾斜、热点分区、小文件泛滥、内存溢出、任务超时等高频线上问题，保障作业稳定运行。",
        verbose=True,
        allow_delegation=False,
        tools=[TOOL_INSTANCES["code_optimize"]]
    )

    # 4. Spark开发智能体
    spark_developer_agent = Agent(
        role="高级Spark全栈开发工程师",
        goal="基于标准化需求、真实表结构、架构优化方案，生成零硬编码、零占位符、可直接集群上线的完整PySpark生产代码，支持多版本迭代优化",
        backstory="严格遵循企业Spark开发规范，所有表名、字段、分区、输出模式、文件格式全部通过MCP动态参数渲染，无任何硬编码固定值。支持读取Git历史稳定版本代码，对比新旧版本差异，保留稳定核心逻辑、迭代新增业务能力，实现代码持续优化、版本可回溯。适配Hive表、Parquet、CSV多形态输出，自动适配多源数据源语法规则，产出代码可直接提交运行、无需二次修改。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["spark_code_gen"],
            TOOL_INSTANCES["git_compare"],
            TOOL_INSTANCES["code_memory"],
            TOOL_INSTANCES["git_version"]
        ]
    )

    # 5. 单元测试自愈智能体
    unit_test_agent = Agent(
        role="数据研发质量保障专家",
        goal="全维度校验Spark代码语法合法性、逻辑合理性、业务准确性、字段匹配度，自动识别缺陷并完成自愈修复，拦截所有生产故障",
        backstory="精通PySpark语法规范、数仓计算逻辑、字段映射规则、空值处理机制，可精准定位语法报错、字段不匹配、逻辑冲突、空值异常、重复计算等问题。具备代码智能自愈能力，可自动修复语法错误、逻辑漏洞、不规范写法、风险代码，无需人工干预完成迭代优化。全量校验代码可用性，确保最终产出代码100%可正常运行、无隐性BUG、无逻辑缺陷。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["code_verify"],
            TOOL_INSTANCES["code_self_heal"]
        ]
    )

    # 6. 任务调度提交智能体
    job_submit_agent = Agent(
        role="Spark任务调度执行专员",
        goal="标准化模拟spark-submit集群提交流程，校验任务依赖、环境配置、资源配额、权限合规性，排查启动异常与运行风险",
        backstory="熟悉大数据集群生产调度规范，精通YARN资源调度、任务依赖加载、环境变量适配、权限校验机制。可精准识别资源不足、分区异常、依赖缺失、路径错误、权限不足等前置问题，提前拦截运行故障。监控任务启动状态，汇总任务运行前置检查报告，保障作业可稳定调度执行。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["code_verify"],
            TOOL_INSTANCES["mysql_query"]
        ]
    )

    # 7. 数据校验智能体
    data_validator_agent = Agent(
        role="数据一致性审计校验专员",
        goal="基于原始业务库与产出结果，完成数据行数、唯一性、完整性、准确性、业务规则符合性全量校验，输出权威数据质量报告",
        backstory="依托真实SQL查询能力，对标原始数据源与最终产出数据，精准核验指标统计结果、数据总量、重复数据、空数据、异常数据。可精准区分问题根因：代码逻辑问题、数据源问题、调度问题、环境问题，杜绝模糊归因。严格按照业务验收标准校验数据，确保最终产出完全匹配PRD需求口径。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["mysql_query"],
            TOOL_INSTANCES["data_verify"]
        ]
    )

    # 8. 数据巡检智能体
    data_inspection_agent = Agent(
        role="数仓存储健康度巡检工程师",
        goal="全面巡检产出数仓表与数据文件，排查分区缺失、小文件过多、数据膨胀、增量异常、存储冗余等生产隐患，输出专项优化方案",
        backstory="专注数仓离线存储运维与数据健康度治理，熟悉Hive数仓分区机制、文件存储规则、数据增量逻辑。可自动识别小文件泛滥、分区断裂、数据重复落地、存储冗余、数据过期等常见生产问题。针对巡检问题输出可落地的治理方案，优化存储占用、提升查询效率、保障数仓长期稳定运行。",
        verbose=True,
        allow_delegation=False,
        tools=[TOOL_INSTANCES["data_verify"]]
    )

    # 9. SRE运维智能体
    devops_sre_agent = Agent(
        role="大数据集群SRE运维工程师",
        goal="复盘任务运行全流程指标、集群资源负载、任务稳定性、报错日志，完成故障根因定位，输出生产级SLA运维优化报告",
        backstory="精通YARN/K8s集群调度、Spark任务日志解析、资源占用分析、故障自愈体系。可复盘任务运行耗时、资源利用率、失败次数、异常告警、排队拥堵等运维指标。针对性能瓶颈、稳定性隐患、资源浪费问题，输出长期运维优化策略与生产保障方案。",
        verbose=True,
        allow_delegation=False,
        tools=[TOOL_INSTANCES["code_self_heal"]]
    )

    # 10. 文档交付智能体
    document_agent = Agent(
        role="大数据项目标准化交付文档工程师",
        goal="全自动汇总需求、建模、架构、开发、测试、校验、巡检、运维全链路产出，生成完整、规范、可直接答辩交付的全套项目交付文档",
        backstory="对接MCP全局上下文，自动采集全流程任务产出数据，无需人工干预，实现文档全自动生成。整合数据源信息、需求说明书、数据字典、建模方案、架构设计、生产代码、迭代日志、校验报告、运维报告。输出文档结构标准化、内容完整闭环，满足企业项目验收、答辩、归档、迭代回溯全场景需求。",
        verbose=True,
        allow_delegation=False,
        tools=[
            TOOL_INSTANCES["prd_analyze"],
            TOOL_INSTANCES["data_verify"],
            TOOL_INSTANCES["git_compare"]
        ]
    )

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
        document_agent
    ]

__all__ = ["get_all_agents"]