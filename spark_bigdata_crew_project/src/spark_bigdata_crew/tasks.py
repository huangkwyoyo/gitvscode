#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Desc: 全链路11步生产流水线任务参考定义（实际运行时由 crew.py + tasks.yaml 驱动）
       本文件保留作为任务描述、依赖关系的文档参考。
       如需修改任务，优先编辑 config/tasks.yaml 和 crew.py。

       流水线顺序：
         task_1 (PRD解析) → task_2 (需求拆解) → task_3 (数仓建模) → task_4 (架构调优)
       → task_5 (代码生成) → task_6 (单元测试) → task_7 (提交预检) → task_8 (数据审计)
       → task_9 (巡检治理) → task_10 (SRE复盘) → task_11 (文档汇总)
"""
from crewai import Task

from .agents import (
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
)

__all__ = ["get_all_tasks"]


def get_all_tasks() -> list[Task]:
    task_1_source_parse = Task(
        description="接收业务PRD文档，解析多源数据源类型、原始业务表清单、核心业务字段、基础业务规则",
        expected_output="标准化多源数据源解析报告",
        agent=requirement_analyst_agent,
    )

    task_2_requirement_analysis = Task(
        description="基于Task1解析结果，深度拆解业务统计口径、维度体系、指标计算规则、验收标准",
        expected_output="完整可落地大数据业务需求说明书",
        agent=requirement_analyst_agent,
        context=[task_1_source_parse],
    )

    task_3_data_modeling = Task(
        description="拉取真实库表元数据，完成ODS/DWD/DWS/ADS标准化分层设计",
        expected_output="数仓分层设计方案、全层级生产建表SQL",
        agent=data_modeling_agent,
        context=[task_2_requirement_analysis],
    )

    task_4_spark_architecture = Task(
        description="定制Spark分布式作业架构，解决数据倾斜、Shuffle拥堵、小文件泛滥等问题",
        expected_output="Spark分布式架构设计文档、生产级参数调优方案",
        agent=spark_architect_agent,
        context=[task_2_requirement_analysis, task_3_data_modeling],
    )

    task_5_spark_development = Task(
        description="动态渲染全量代码逻辑，生成零硬编码、可直接集群提交的PySpark生产代码",
        expected_output="完整可上线PySpark生产代码",
        agent=spark_developer_agent,
        context=[task_1_source_parse, task_2_requirement_analysis, task_3_data_modeling, task_4_spark_architecture],
    )

    task_6_unit_test = Task(
        description="对生成代码进行全维度校验，覆盖语法错误、空值漏洞、逻辑冲突等，自动完成缺陷修复",
        expected_output="代码单元测试报告、自愈修复记录、最终优化版可运行代码",
        agent=unit_test_agent,
        context=[task_5_spark_development],
    )

    task_7_job_submit = Task(
        description="模拟spark-submit集群提交流程，前置校验代码可用性、数据源连通性、权限合规性",
        expected_output="Spark任务集群前置预检报告、调度参数配置清单",
        agent=job_submit_agent,
        context=[task_6_unit_test],
    )

    task_8_data_validation = Task(
        description="对标原始业务数据源与PRD验收口径，全量核验产出数据的完整性、准确性、一致性",
        expected_output="全维度数据质量审计报告、异常数据明细、问题根因分析",
        agent=data_validator_agent,
        context=[task_7_job_submit],
    )

    task_9_data_inspection = Task(
        description="深度巡检数仓分区完整性、小文件数量、存储冗余、分区断裂等生产隐患",
        expected_output="数仓健康度巡检报告、小文件治理方案、分区修复策略",
        agent=data_inspection_agent,
        context=[task_8_data_validation],
    )

    task_10_devops_monitor = Task(
        description="复盘全链路任务耗时、资源利用率、失败风险，定位性能瓶颈与稳定性隐患",
        expected_output="集群全链路运维复盘报告、SLA稳定性优化方案",
        agent=devops_sre_agent,
        context=[task_9_data_inspection],
    )

    task_11_document_generate = Task(
        description="汇总全流程所有产出物，自动整合生成整套企业级标准化交付文档",
        expected_output="全套项目交付文档合集（含需求/建模/架构/代码/测试/质检/巡检/运维全流程归档）",
        agent=document_agent,
        context=[
            task_1_source_parse, task_2_requirement_analysis, task_3_data_modeling,
            task_4_spark_architecture, task_5_spark_development, task_6_unit_test,
            task_7_job_submit, task_8_data_validation, task_9_data_inspection,
            task_10_devops_monitor,
        ],
    )

    return [
        task_1_source_parse,
        task_2_requirement_analysis,
        task_3_data_modeling,
        task_4_spark_architecture,
        task_5_spark_development,
        task_6_unit_test,
        task_7_job_submit,
        task_8_data_validation,
        task_9_data_inspection,
        task_10_devops_monitor,
        task_11_document_generate,
    ]
