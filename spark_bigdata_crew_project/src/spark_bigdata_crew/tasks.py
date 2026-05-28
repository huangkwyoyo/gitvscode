#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Desc: 生产级8步工作流 + 3道人工审批Gate（实际运行时由 crew.py + tasks.yaml 驱动）
       本文件保留作为任务描述、依赖关系的文档参考。
       如需修改任务，优先编辑 config/tasks.yaml 和 crew.py。

       工作流顺序：
         task_1 (PRD解析) → task_2 (元数据校验)
       → Gate 1 (需求与数据源确认·人工审批)
       → task_3 (字段映射) → task_4 (数仓分层建模)
       → Gate 2 (模型与字段映射确认·人工审批)
       → task_5 (Spark代码生成) → task_6 (静态检查)
       → Gate 3 (代码执行前确认·人工审批)
       → task_7 (质量报告) → task_8 (文档归档)
"""
from crewai import Task

from .agents import (
    requirement_agent,
    metadata_agent,
    modeling_agent,
    spark_engineer_agent,
    quality_agent,
    delivery_agent,
)

__all__ = ["get_all_tasks"]


def get_all_tasks() -> list[Task]:
    # ---- 阶段一：需求与元数据 ----
    task_1_requirement_analysis = Task(
        description="接收业务PRD文档，解析数据源范围、业务表清单、核心业务字段、统计口径与指标计算规则，输出标准化需求说明书与验收条件",
        expected_output="标准化业务需求说明书（含Hive/HDFS数据源范围、指标口径字典、验收标准）",
        agent=requirement_agent,
    )

    task_2_metadata_validation = Task(
        description="连接Hive Metastore与HDFS NameNode，拉取全部库表元数据，逐字段校验存在性、类型对齐、分区覆盖度，输出校验报告",
        expected_output="元数据校验报告（含表/字段存在性验证、分区覆盖度检查、阻断或放行判定）",
        agent=metadata_agent,
        context=[task_1_requirement_analysis],
    )

    # Gate 1：需求与数据源确认
    gate_1_requirement_data_confirm = Task(
        description="【人工审批Gate 1】确认需求说明书与元数据校验报告：数据源范围、表/字段映射、指标口径。审批通过后进入建模阶段",
        expected_output="审批通过/驳回确认记录",
        agent=requirement_agent,
        context=[task_1_requirement_analysis, task_2_metadata_validation],
    )

    # ---- 阶段二：映射与建模 ----
    task_3_field_mapping = Task(
        description="完成业务字段到Hive物理字段的精确映射，构建字段血缘关系矩阵，明确指标计算路径与依赖表关系",
        expected_output="字段映射确认文档（含业务-物理字段映射表、血缘矩阵、指标计算路径）",
        agent=requirement_agent,
        context=[gate_1_requirement_data_confirm],
    )

    task_4_data_modeling = Task(
        description="基于字段映射与真实元数据，完成ODS/DWD/DWS/ADS分层设计，输出Hive建表DDL、分区策略与存储格式规范",
        expected_output="数仓分层设计方案、全层级Hive建表DDL、字段映射字典、分区与存储规范",
        agent=modeling_agent,
        context=[task_3_field_mapping],
    )

    # Gate 2：模型与字段映射确认
    gate_2_model_confirm = Task(
        description="【人工审批Gate 2】确认数仓分层设计：分层路径、字段映射、分区策略、建表DDL可执行性。审批通过后进入代码生成阶段",
        expected_output="审批通过/驳回确认记录",
        agent=modeling_agent,
        context=[task_4_data_modeling],
    )

    # ---- 阶段三：代码与校验 ----
    task_5_spark_development = Task(
        description="基于审批通过的建模方案，生成参数化PySpark生产代码与spark-submit提交脚本模板，内置数据倾斜治理与性能优化",
        expected_output="完整PySpark生产代码（参数化配置）、spark-submit脚本模板、性能优化说明",
        agent=spark_engineer_agent,
        context=[gate_2_model_confirm],
    )

    task_6_code_quality_check = Task(
        description="对生成代码执行全维度静态检查：语法、字段存在性、类型兼容性、空值处理、资源释放。校验失败阻断流水线",
        expected_output="代码静态检查报告、缺陷明细（如有）、修复建议、通过/阻断判定",
        agent=quality_agent,
        context=[task_5_spark_development],
    )

    # Gate 3：代码执行前确认
    gate_3_code_approval = Task(
        description="【人工审批Gate 3】确认代码静态检查通过、逻辑与需求一致、性能优化合理、提交脚本参数正确。审批通过后进入交付阶段",
        expected_output="审批通过/驳回确认记录",
        agent=quality_agent,
        context=[task_6_code_quality_check],
    )

    # ---- 阶段四：质量与交付 ----
    task_7_quality_report = Task(
        description="基于PRD验收标准，生成数据质量校验规则与验收SQL脚本，输出数据质量预期报告",
        expected_output="数据质量规则清单、验收SQL脚本、数据质量预期报告、验收标准对照表",
        agent=quality_agent,
        context=[gate_3_code_approval],
    )

    task_8_delivery_archive = Task(
        description="汇总全流程产出物，生成版本化交付包与运行报告，归档至artifacts目录",
        expected_output="完整项目交付文档合集（含需求/元数据/建模/代码/校验/质量全流程归档）、版本记录",
        agent=delivery_agent,
        context=[
            task_1_requirement_analysis, task_2_metadata_validation,
            task_3_field_mapping, task_4_data_modeling,
            task_5_spark_development, task_6_code_quality_check,
            task_7_quality_report,
        ],
    )

    return [
        task_1_requirement_analysis,
        task_2_metadata_validation,
        gate_1_requirement_data_confirm,
        task_3_field_mapping,
        task_4_data_modeling,
        gate_2_model_confirm,
        task_5_spark_development,
        task_6_code_quality_check,
        gate_3_code_approval,
        task_7_quality_report,
        task_8_delivery_archive,
    ]
