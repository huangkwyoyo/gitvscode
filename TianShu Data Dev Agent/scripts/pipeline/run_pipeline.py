#!/usr/bin/env python3
"""
Data Dev Agent v1 legacy pipeline 主入口。
v2 主入口在 scripts/dev_agent/，本文件不作为 v2 Review Package 验证入口。

用法：
  # 完整管道（8层全链路）
  python scripts/pipeline/run_pipeline.py --requirement fixtures/requirements/trip_daily_report.yml

  # 仅校验不执行（dry-run）
  python scripts/pipeline/run_pipeline.py --requirement fixtures/requirements/trip_daily_report.yml --dry-run

  # 指定 TianShu DuckDB 路径
  python scripts/pipeline/run_pipeline.py --requirement fixtures/requirements/trip_daily_report.yml --db "/path/to/nyc_transport.duckdb"

流程：
  YAML 需求 → Layer 1(解析) → Layer 2(意图) → Layer 3(SQLPlan) → Layer 4(编译) → Layer 5(校验) → Layer 6(执行) → Layer 7(评估) → Layer 8(产出)
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# P1-2 修复：Windows 控制台编码安全包装
# GBK 编码无法处理 Unicode 字符（✓、✗、⚠、✅ 等），导致 UnicodeEncodeError。
# 此包装必须在任何 print() 之前执行，且同时处理 stdout 和 stderr。
# PYTHONIOENCODING=utf-8 环境变量可以解决，但不应依赖用户设置。
# ═══════════════════════════════════════════════════════════


def _wrap_stdio_utf8() -> None:
    """将 stdout/stderr 包装为 UTF-8 编码，防止 Windows GBK 终端崩溃"""
    for stream_name, stream in [("stdout", sys.stdout), ("stderr", sys.stderr)]:
        try:
            if hasattr(stream, "buffer") and stream.buffer is not None:
                sys.__dict__[stream_name] = io.TextIOWrapper(
                    stream.buffer, encoding="utf-8", errors="replace"
                )
        except (AttributeError, OSError, ValueError):
            # 管道重定向或非控制台环境——静默跳过
            pass


# 模块加载时执行（在任何可能输出 Unicode 的代码之前）
if sys.platform == "win32" and "PYTHONIOENCODING" not in os.environ:
    _wrap_stdio_utf8()

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pipeline.layer1_requirement import parse_requirement, Requirement
from scripts.pipeline.layer2_intent import build_intent, Intent
from scripts.pipeline.layer3_ir import SQLPlan
from scripts.pipeline.layer3_plan import construct_sqlplan
from scripts.pipeline.layer4_generate import compile_sql, SQLCompileError
from scripts.pipeline.layer5_validate import validate_sql, ValidationReport
from scripts.pipeline.layer6_execute import execute_sql, ExecutionResult
from scripts.pipeline.layer7_evaluate import evaluate_results, EvaluationReport
from scripts.pipeline.layer8_product import publish_outputs
from scripts.pipeline.column_binding import load_from_tianShu


def load_config():
    """加载 Agent 运行配置"""
    import yaml
    config_path = PROJECT_ROOT / "harness" / "config" / "agent_targets.yml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def run_pipeline(
    requirement_path: str | Path,
    duckdb_path: str | None = None,
    dry_run: bool = False,
    output_format: str | None = None,
    verbose: bool = False,
) -> dict:
    """
    运行完整 8 层管道

    返回：执行结果字典
    """
    config = load_config()
    pipeline_start = time.perf_counter()

    # ── 确定 DuckDB 路径 ──
    if duckdb_path is None:
        duckdb_path = config.get("tianShu", {}).get(
            "duckdb_path",
            "D:\\ProgramData\\Datawarehouse\\纽约市城市交通\\nyc_transport.duckdb",
        )

    # ── 从 TianShu DuckDB 动态加载指标和维度定义 ──
    # 优先使用 meta.metric_definitions 中的已审批数据，
    # 静态绑定作为 fallback
    if verbose:
        print("[Init] 从 TianShu DuckDB 加载事实源...")
    try:
        loaded = load_from_tianShu(duckdb_path)
        if verbose:
            print(f"  OK 已加载 {len(loaded['metrics'])} 个指标, {len(loaded['dimensions'])} 个维度")
    except Exception as e:
        if verbose:
            print(f"  [WARN] TianShu 加载失败，使用静态绑定: {e}")

    result_dirs = {
        "result": PROJECT_ROOT / "generated" / "results",
        "report": PROJECT_ROOT / "generated" / "reports",
        "task": PROJECT_ROOT / "generated" / "tasks",
    }

    # ═══════════════════════════════════════════════════════
    # Layer 1：需求解析
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 1] 解析需求说明书...")
    requirement = parse_requirement(requirement_path)

    if not requirement.is_valid:
        print(f"[FAIL] Layer 1 - 需求解析失败: {requirement.validation_errors}")
        return {"status": "fail", "layer": 1, "errors": requirement.validation_errors}

    if verbose:
        print(f"  [OK] 需求名称: {requirement.name}")
        print(f"  [OK] 指标数量: {len(requirement.metrics)}")
        print(f"  [OK] 时间范围: {requirement.filters.date_range}")

    # ═══════════════════════════════════════════════════════
    # Layer 2：意图理解
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 2] 理解意图、匹配指标...")
    intent = build_intent(requirement)

    if not intent.is_valid:
        print(f"[BLOCKED] Layer 2 - 意图理解失败: {intent.block_reason}")
        return {"status": "blocked", "layer": 2, "reason": intent.block_reason, "warnings": intent.warnings}

    if verbose:
        print(f"  [OK] 业务域: {intent.domain}")
        print(f"  [OK] 已解析指标: {[m.registered_name for m in intent.metrics_requested]}")
        print(f"  [OK] 置信度: {intent.confidence}")

    if intent.warnings:
        for w in intent.warnings:
            print(f"  [WARN] {w}")

    # ═══════════════════════════════════════════════════════
    # Layer 3：SQLPlan 构造（LLM 边界以下）
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 3] 确定性构造 SQLPlan...")
    sqlplan = construct_sqlplan(intent)

    if not sqlplan.is_valid:
        print(f"[BLOCKED] Layer 3 - SQLPlan 构造失败: {sqlplan.block_reason}")
        return {"status": "blocked", "layer": 3, "reason": sqlplan.block_reason, "warnings": sqlplan.warnings}

    if verbose:
        print(f"  [OK] 数据源层: {sqlplan.source_layer.upper()}")
        print(f"  [OK] 主表: {sqlplan.join_graph.primary.table}")
        joins_count = len(sqlplan.join_graph.joins) if sqlplan.join_graph else 0
        print(f"  [OK] JOIN 数: {joins_count}")
        print(f"  [OK] 指标绑定: {len(sqlplan.column_bindings)} 个")

    if sqlplan.warnings:
        for w in sqlplan.warnings:
            print(f"  [WARN] {w}")

    # ═══════════════════════════════════════════════════════
    # Layer 4：SQL 编译
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 4] 编译 SQL...")
    try:
        sql_text, sql_params = compile_sql(sqlplan)
    except SQLCompileError as e:
        print(f"[FAIL] Layer 4 - SQL 编译失败: {e}")
        return {"status": "fail", "layer": 4, "reason": str(e)}

    if verbose:
        print(f"  [OK] SQL 生成完成 ({len(sql_text)} 字符)")
        print(f"  [OK] 参数: {sql_params}")

    # 打印 SQL（总是显示）
    print("\n" + "-" * 60)
    print("[SQL]")
    print("-" * 60)
    print(sql_text)
    if sql_params:
        print(f"\n参数: {sql_params}")
    print("-" * 60 + "\n")

    # ═══════════════════════════════════════════════════════
    # Layer 5：SQL 校验
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 5] 校验 SQL 安全和语义...")
    validation = validate_sql(sql_text, sqlplan)

    if not validation.passed:
        print(f"[FAIL] Layer 5 - SQL 校验失败:")
        for issue in validation.issues:
            print(f"  [FAIL] {issue}")
        return {"status": "fail", "layer": 5, "issues": validation.issues, "warnings": validation.warnings}

    if verbose:
        print("  [OK] 所有安全检查和语义检查通过")

    if validation.warnings:
        for w in validation.warnings:
            print(f"  [WARN] {w}")

    # ── Dry-run 模式：到此为止，不执行 SQL ──
    if dry_run:
        elapsed = int((time.perf_counter() - pipeline_start) * 1000)
        print(f"\n[Dry-run] 管道校验完成（未执行 SQL），耗时 {elapsed}ms")
        return {
            "status": "pass",
            "layer": 5,
            "dry_run": True,
            "sqlplan": sqlplan,
            "sql": sql_text,
            "validation": validation,
        }

    # ═══════════════════════════════════════════════════════
    # Layer 6：SQL 执行
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 6] 执行 SQL（DuckDB 只读）...")
    result = execute_sql(
        sql_text,
        sql_params,
        duckdb_path=duckdb_path,
        timeout_seconds=30,
        max_retries=1,
    )

    if not result.success:
        print(f"[FAIL] Layer 6 - SQL 执行失败: {result.error_message}")
        return {
            "status": "fail",
            "layer": 6,
            "reason": result.error_message,
            "error_type": result.error_type,
            "sql": sql_text,
        }

    if verbose:
        print(f"  [OK] 返回 {result.row_count} 行 x {result.column_count} 列")
        print(f"  [OK] 执行耗时: {result.execution_time_ms}ms")

    # ═══════════════════════════════════════════════════════
    # Layer 7：结果评估
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 7] 评估结果质量...")
    eval_report = evaluate_results(result, sqlplan)

    if verbose:
        for check in eval_report.checks:
            icon = "[OK]" if check.passed else "[FAIL]"
            print(f"  {icon} {check.name}: {check.detail}")

    if eval_report.warnings:
        for w in eval_report.warnings:
            print(f"  [WARN] {w}")

    # ═══════════════════════════════════════════════════════
    # Layer 8：产出物生成
    # ═══════════════════════════════════════════════════════
    if verbose:
        print("[Layer 8] 生成产出物...")
    pipeline_elapsed = int((time.perf_counter() - pipeline_start) * 1000)

    outputs = publish_outputs(
        plan=sqlplan,
        validation=validation,
        eval_report=eval_report,
        result=result,
        pipeline_time_ms=pipeline_elapsed,
        result_dir=result_dirs["result"],
        report_dir=result_dirs["report"],
        task_dir=result_dirs["task"],
    )

    # ── 打印输出摘要 ──
    print("\n" + "=" * 60)
    print("管道执行完成")
    print("=" * 60)
    print(f"  状态: {eval_report.status.upper()}")
    print(f"  管道耗时: {pipeline_elapsed}ms")
    print(f"  SQL 耗时: {result.execution_time_ms}ms")
    print(f"  行数: {result.row_count}")
    print(f"  列数: {result.column_count}")
    print(f"  产物:")
    for key, path in sorted(outputs.items()):
        print(f"    [{key}] {path}")

    if eval_report.status != "clean":
        print(f"\n  [WARN] 结果标记为 DIRTY，请查看验证报告获取详情。")
    else:
        print(f"\n  [OK] 结果标记为 CLEAN，所有检查通过。")

    return {
        "status": eval_report.status,
        "layer": 8,
        "outputs": outputs,
        "pipeline_time_ms": pipeline_elapsed,
        "row_count": result.row_count,
        "column_count": result.column_count,
    }


def main():
    # 🚨 P1-2 修复：UTF-8 编码包装已在模块加载时执行（_wrap_stdio_utf8()），
    # 此处不再重复处理。详见文件顶部注释。
    parser = argparse.ArgumentParser(
        description="TianShu Data Dev Agent — 数据开发管道",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/pipeline/run_pipeline.py -r fixtures/requirements/trip_daily_report.yml
  python scripts/pipeline/run_pipeline.py -r fixtures/requirements/trip_daily_report.yml --dry-run
  python scripts/pipeline/run_pipeline.py -r fixtures/requirements/trip_daily_report.yml --verbose
        """,
    )
    parser.add_argument(
        "-r", "--requirement",
        required=True,
        help="需求说明书 YAML 文件路径",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="TianShu DuckDB 文件路径（默认从 agent_targets.yml 读取）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅校验不执行 SQL",
    )
    parser.add_argument(
        "--format",
        default=None,
        choices=["parquet", "csv"],
        help="输出格式（默认 parquet）",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="静默模式（仅输出结果摘要）",
    )

    args = parser.parse_args()

    verbose = args.verbose or not args.quiet

    result = run_pipeline(
        requirement_path=args.requirement,
        duckdb_path=args.db,
        dry_run=args.dry_run,
        output_format=args.format,
        verbose=verbose,
    )

    # 返回码
    if result["status"] in ("fail", "blocked"):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
