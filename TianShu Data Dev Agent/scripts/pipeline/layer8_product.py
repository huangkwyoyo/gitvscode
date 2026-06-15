"""
Layer 8：产出物生成层

职责：
  1. 保存查询结果为 Parquet/CSV 文件
  2. 生成可审计的验证报告（Markdown）
  3. 生成调度任务配置 YAML（Phase 2 接入调度平台）

LLM 角色：
  **完全禁止**。此层是纯文件 I/O。

输入：ExecutionResult + EvaluationReport + SQLPlan + ValidationReport
输出：
  - generated/results/{plan_id}.parquet
  - generated/reports/{plan_id}_report.md
  - generated/tasks/{plan_id}_task.yml
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .layer3_ir import SQLPlan
from .layer5_validate import ValidationReport
from .layer6_execute import ExecutionResult
from .layer7_evaluate import EvaluationReport


def _save_result_file(
    result: ExecutionResult,
    plan: SQLPlan,
    output_dir: Path,
    format_override: Optional[str] = None,
) -> str:
    """
    保存查询结果到文件

    返回：保存的绝对路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    fmt = format_override or plan.output_format
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{plan.plan_name}_{timestamp}.{fmt}"
    filepath = output_dir / filename

    df = result.dataframe
    if df is None:
        raise ValueError("无法保存：DataFrame 为空（SQL 执行失败）")

    if fmt == "parquet":
        df.to_parquet(str(filepath), index=False)
    elif fmt == "csv":
        df.to_csv(str(filepath), index=False, encoding="utf-8-sig")
    else:
        raise ValueError(f"不支持的输出格式: {fmt}")

    return str(filepath.absolute())


def _generate_report(
    plan: SQLPlan,
    validation: ValidationReport,
    eval_report: EvaluationReport,
    result: ExecutionResult,
    result_path: str,
    pipeline_time_ms: int,
    output_dir: Path,
) -> str:
    """
    生成可审计的验证报告（Markdown 格式）

    返回：报告文件路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{plan.plan_id}_report_{timestamp}.md"
    filepath = output_dir / filename

    # 管道状态
    if not plan.is_valid:
        pipeline_status = "blocked"
    elif not validation.passed:
        pipeline_status = "fail"
    elif eval_report.status == "dirty":
        pipeline_status = "dirty"
    else:
        pipeline_status = "pass"

    # 构建 Markdown 报告
    lines = [
        f"# 数据开发 Agent 执行报告",
        f"",
        f"## 基本信息",
        f"",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 计划 ID | `{plan.plan_id}` |",
        f"| 需求名称 | {plan.plan_name} |",
        f"| 数据源层 | {plan.source_layer.upper()} |",
        f"| 业务域 | {plan.domain} |",
        f"| 执行时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| 管道耗时 | {pipeline_time_ms}ms |",
        f"| SQL 执行耗时 | {result.execution_time_ms}ms |",
        f"| 管道状态 | **{pipeline_status.upper()}** |",
        f"",
        f"## SQL 校验结果（Layer 5）",
        f"",
        f"**状态**: {'✅ 通过' if validation.passed else '❌ 未通过'}",
        f"",
    ]

    # 安全检查
    lines.append("### 安全检查")
    lines.append("")
    for check in validation.safety_checks:
        icon = "✅" if check.passed else "❌"
        lines.append(f"- {icon} **{check.name}**: {check.detail}")
    lines.append("")

    # 表引用检查
    lines.append("### 表引用检查")
    lines.append("")
    for check in validation.table_reference_checks:
        icon = "✅" if check.passed else "❌"
        lines.append(f"- {icon} **{check.name}**: {check.detail}")
    lines.append("")

    # JOIN 检查
    lines.append("### JOIN 白名单检查")
    lines.append("")
    for check in validation.join_checks:
        icon = "✅" if check.passed else "❌"
        lines.append(f"- {icon} **{check.name}**: {check.detail}")
    lines.append("")

    # 日期合规
    lines.append("### 日期合规检查")
    lines.append("")
    for check in validation.date_compliance:
        icon = "✅" if check.passed else "❌"
        lines.append(f"- {icon} **{check.name}**: {check.detail}")
    lines.append("")

    # 结果评估
    lines.append("## 结果评估（Layer 7）")
    lines.append("")
    lines.append(f"**状态**: {'✅ 通过' if eval_report.passed else '⚠️ DIRTY'}")
    lines.append("")
    lines.append("| 检查项 | 结果 | 阈值 | 实际值 |")
    lines.append("|--------|------|------|--------|")
    for check in eval_report.checks:
        icon = "✅" if check.passed else "❌"
        lines.append(f"| {icon} {check.name} | {'通过' if check.passed else '未通过'} | {check.threshold} | {check.actual} |")
    lines.append("")

    # 结果统计
    lines.append("## 结果统计")
    lines.append("")
    lines.append(f"- 查询行数: **{result.row_count}**")
    lines.append(f"- 查询列数: **{result.column_count}**")
    lines.append(f"- 输出文件: `{result_path}`")
    lines.append(f"- 文件格式: `{plan.output_format}`")
    lines.append("")

    # 列信息
    if result.columns:
        lines.append("### 结果列")
        lines.append("")
        lines.append("| 列名 | 类型 |")
        lines.append("|------|------|")
        for col in result.columns:
            lines.append(f"| {col.name} | {col.dtype} |")
        lines.append("")

    # SQL
    lines.append("## 执行的 SQL")
    lines.append("")
    lines.append("```sql")
    lines.append(result.sql_compiled)
    lines.append("```")
    lines.append("")

    # 警告
    all_warnings = validation.warnings + eval_report.warnings
    if all_warnings:
        lines.append("## ⚠️ 警告")
        lines.append("")
        for w in all_warnings:
            lines.append(f"- {w}")
        lines.append("")

    report_content = "\n".join(lines)
    filepath.write_text(report_content, encoding="utf-8")
    return str(filepath.absolute())


def _generate_task_config(
    plan: SQLPlan,
    result_path: str,
    report_path: str,
    output_dir: Path,
) -> Optional[str]:
    """
    生成调度任务配置 YAML（预留给 Phase 2 调度平台接入）

    返回：任务配置文件路径，或 None（如果调度平台未就绪）
    """
    # Phase 1：生成基本任务元数据 YAML，供未来调度平台解析
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{plan.plan_id}_task_{timestamp}.yml"
    filepath = output_dir / filename

    import yaml

    task_config = {
        "task_id": plan.plan_id,
        "task_name": plan.plan_name,
        "domain": plan.domain,
        "source_layer": plan.source_layer,
        "execution": {
            "read_only": True,
            "timeout_seconds": 30,
            "retry_on_timeout": 1,
        },
        "output": {
            "result_file": result_path,
            "report_file": report_path,
            "format": plan.output_format,
        },
        "schedule": {
            "enabled": False,  # Phase 2 启用
            "cron": None,      # Phase 2 配置
        },
        "depends_on": [],      # Phase 2 DAG 依赖
        "generated_at": datetime.now().isoformat(),
    }

    content = yaml.dump(task_config, allow_unicode=True, default_flow_style=False)
    filepath.write_text(content, encoding="utf-8")
    return str(filepath.absolute())


def publish_outputs(
    plan: SQLPlan,
    validation: ValidationReport,
    eval_report: EvaluationReport,
    result: ExecutionResult,
    pipeline_time_ms: int,
    result_dir: Path,
    report_dir: Path,
    task_dir: Path,
) -> dict[str, str]:
    """
    生成所有产出物

    返回：{type: path} 字典
    """
    outputs: dict[str, str] = {}

    # ── 1. 保存结果文件 ──
    if result.success and result.dataframe is not None:
        try:
            result_path = _save_result_file(result, plan, result_dir)
            outputs["result"] = result_path
        except Exception as e:
            outputs["result_error"] = str(e)
    else:
        outputs["result"] = "skipped (execution failed)"

    # ── 2. 生成验证报告 ──
    try:
        report_path = _generate_report(
            plan, validation, eval_report, result,
            outputs.get("result", "N/A"),
            pipeline_time_ms, report_dir,
        )
        outputs["report"] = report_path
    except Exception as e:
        outputs["report_error"] = str(e)

    # ── 3. 生成任务配置 ──
    try:
        task_path = _generate_task_config(
            plan,
            outputs.get("result", "N/A"),
            outputs.get("report", "N/A"),
            task_dir,
        )
        if task_path:
            outputs["task_config"] = task_path
    except Exception as e:
        outputs["task_config_error"] = str(e)

    return outputs
