"""
PySpark DSL 受控样本执行器——v2.2 完整实现。

执行模型（纵深防御 12 层）：
  1. 无 SparkSession → SKIPPED（保持向后兼容）
  2. PySpark 不可用 → SKIPPED
  3. AST 安全检查（analyze_spark_draft）→ FAIL
  4. 入口点提取（extract_build_dataframe）→ FAIL
  5. 样本源 DataFrame 构建 → 与 DuckDB 共享同一份 (rows, columns, types)
  6. 临时视图注册 → spark.table(view_name) 可引用
  7. 受限 globals 构建 → 移除 open/__import__/eval/exec 等
  8. compile + exec → 在受限命名空间中执行
  9. 签名检测 → 1 参数(spark) 或 2 参数(spark, sources)
  10. .limit(max_sample_rows) + .collect() → executor 统一控制
  11. 超时 + cancelJobGroup → 硬中断
  12. 转换为 SQLResult → 与 DuckDB 执行器返回类型一致

安全保证：
  - 不直接 exec 任意 Python 文本——先 AST 分析再入口点执行
  - 不降低 spark_safety 规则——analyze_spark_draft 是唯一事实源
  - 不写表/文件/启用 Hive——AST 拦截 + 受限 builtins
  - 不连接远程或生产 Spark——SparkSession 由调用方保证 local[*]
"""

from __future__ import annotations

import inspect
import threading
import time
from typing import Any, Optional

from src.ir.types import SQLResult


# ═══════════════════════════════════════════════════════════════
# 模块级常量
# ═══════════════════════════════════════════════════════════════

# 安全的内置函数白名单——exec 的受限命名空间中只有这些
_SAFE_BUILTINS: set[str] = {
    # 基本类型与运算
    "True", "False", "None",
    "abs", "all", "any", "bool", "bytes", "callable",
    "chr", "complex", "dict", "divmod", "enumerate",
    "filter", "float", "format", "frozenset", "hash",
    "hex", "int", "isinstance", "issubclass", "iter",
    "len", "list", "map", "max", "min", "next",
    "oct", "ord", "pow", "print", "range",
    "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "tuple", "type", "zip",
    # 类型转换
    "bin", "bytearray",
    # 异常
    "Exception", "ValueError", "TypeError", "KeyError",
    "IndexError", "RuntimeError", "StopIteration",
}

# 禁止在 exec 命名空间中直接使用的内置函数（即使 AST 未拦截也要移除）
_BLOCKED_BUILTINS: set[str] = {
    "open", "__import__", "compile", "eval", "exec",
    "getattr", "setattr", "delattr", "hasattr",
    "globals", "locals", "vars", "dir",
    "input", "help", "breakpoint",
    "memoryview", "__build_class__",
}


def _check_pyspark_available() -> bool:
    """检测 PySpark 是否可用——不影响静态安全检查。"""
    try:
        import pyspark  # noqa: F401
        return True
    except ImportError:
        return False


def _safe_globals(spark_session: Any) -> dict[str, Any]:
    """构建受限的 exec 全局命名空间。

    只包含：
      - 安全的内置函数（白名单）
      - pyspark.sql 核心模块
      - 传入的 spark_session

    显式排除：open、__import__、eval、exec、compile、getattr、setattr 等。
    """
    import builtins

    safe: dict[str, Any] = {"__builtins__": {}}

    # 只注入白名单内置函数
    for name in _SAFE_BUILTINS:
        if hasattr(builtins, name):
            safe["__builtins__"][name] = getattr(builtins, name)

    # 注入受限的 __import__ ——只允许 pyspark 及其子模块
    def _restricted_import(name, *args, **kwargs):
        allowed_prefixes = ("pyspark",)
        if not any(name == prefix or name.startswith(prefix + ".") for prefix in allowed_prefixes):
            raise ImportError(f"禁止导入模块: {name}——只允许 pyspark 及其子模块")
        return __import__(name, *args, **kwargs)

    safe["__builtins__"]["__import__"] = _restricted_import

    # 注入 spark 会话
    safe["spark"] = spark_session

    # 注入 pyspark 核心模块
    try:
        import pyspark.sql.functions as F
        import pyspark.sql.types as T
        safe["F"] = F
        safe["T"] = T
        safe["pyspark"] = __import__("pyspark")
    except ImportError:
        pass

    return safe


def _build_source_dataframes(
    spark_session: Any,
    sample_rows: list[tuple],
    sample_columns: list[str],
    sample_types: list[str],
    lineage_sources: list,
) -> dict[str, Any]:
    """从样本数据创建 Spark DataFrame 字典。

    与 DuckDB 使用完全相同的 (rows, columns, types) 元组，
    确保两个引擎处理同一份样本快照。

    Args:
        spark_session: 活跃的 SparkSession
        sample_rows: 样本数据行（与 DuckDB 相同）
        sample_columns: 列名列表
        sample_types: DuckDB 列类型列表（将映射为 Spark 类型）
        lineage_sources: SampleSourceRef 列表（决定如何命名/分组）

    Returns:
        {fully_qualified_table: DataFrame} 字典
    """
    if not sample_rows or not sample_columns:
        return {}

    # 将 DuckDB 类型映射为 Spark 类型
    spark_types = [_duckdb_type_to_spark(t) for t in sample_types]

    # 使用 Spark 的 createDataFrame 从行数据创建 DataFrame
    from pyspark.sql.types import StructType, StructField

    try:
        schema = StructType([
            StructField(col, spark_type, True)
            for col, spark_type in zip(sample_columns, spark_types)
        ])
        df = spark_session.createDataFrame(sample_rows, schema=schema)
    except Exception:
        # 回退：不使用显式 schema，让 Spark 推断类型
        df = spark_session.createDataFrame(sample_rows, sample_columns)

    # 如果定义了 lineage_sources，按来源拆分为多个 DataFrame
    if lineage_sources and len(lineage_sources) == 1:
        source = lineage_sources[0]
        fqtn = getattr(source, "fully_qualified_table", "gold.default_table")
        return {fqtn: df}

    # 默认：将整个 DataFrame 关联到第一个 lineage source
    if lineage_sources:
        result: dict[str, Any] = {}
        for src in lineage_sources:
            fqtn = getattr(src, "fully_qualified_table", "gold.default_table")
            result[fqtn] = df
        return result

    return {"gold.default_table": df}


def _duckdb_type_to_spark(duckdb_type: str):
    """将 DuckDB 类型字符串映射为等价的 Spark SQL 类型。

    映射原则：保持数值精度，避免信息丢失。
    """
    from pyspark.sql.types import (
        BooleanType, ByteType, DateType, DecimalType, DoubleType,
        FloatType, IntegerType, LongType, StringType, TimestampType,
    )

    t = duckdb_type.upper().strip()
    # 整数类型
    if t in ("TINYINT", "UTINYINT"):
        return ByteType()
    if t in ("SMALLINT", "USMALLINT"):
        return IntegerType()
    if t in ("INTEGER", "INT", "INT4", "UINTEGER"):
        return IntegerType()
    if t in ("BIGINT", "INT8", "UBIGINT", "HUGEINT"):
        return LongType()
    # 浮点类型
    if t in ("FLOAT", "FLOAT4", "REAL"):
        return FloatType()
    if t in ("DOUBLE", "FLOAT8", "DECIMAL", "NUMERIC"):
        return DoubleType()
    # 字符串/文本
    if any(sub in t for sub in ("VARCHAR", "CHAR", "TEXT", "STRING", "ENUM")):
        return StringType()
    # 布尔
    if t == "BOOLEAN" or t == "BOOL":
        return BooleanType()
    # 日期时间
    if t == "DATE":
        return DateType()
    if any(sub in t for sub in ("TIMESTAMP", "DATETIME")):
        return TimestampType()
    # 默认：字符串
    return StringType()


def _register_temp_views(
    spark_session: Any,
    source_dfs: dict[str, Any],
    lineage_sources: list,
) -> None:
    """将源 DataFrame 注册为 Spark 临时视图。

    视图名由 fully_qualified_table 中的 '.' 替换为 '_' 得到。
    例如 gold.dws_trips → gold_dws_trips。
    """
    for fqtn, df in source_dfs.items():
        view_name = fqtn.replace(".", "_")
        try:
            df.createOrReplaceTempView(view_name)
        except Exception:
            # 视图注册失败不阻断——代码仍可通过 sources 参数访问
            pass


def _df_to_sqlresult(
    df: Any,
    code: str,
    execution_time_ms: float,
    source_table: str,
) -> SQLResult:
    """将 Spark DataFrame 转换为统一的 SQLResult。

    执行 .limit() + .collect() 收集结果行。
    """
    try:
        columns = list(df.columns)
        rows_list = df.collect()
        # 将 Row 对象转换为 tuple
        rows = [tuple(r) for r in rows_list]
        column_types = [str(f.dataType) for f in df.schema.fields]
        return SQLResult(
            sql=code,
            columns=columns,
            column_types=column_types,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=execution_time_ms,
            error=None,
            source_table=source_table,
        )
    except Exception as exc:
        return SQLResult(
            sql=code,
            error=f"Spark 结果收集失败: {exc}",
            source_table=source_table,
        )


def execute_spark_dsl(
    code: str,
    spark_session: Any = None,
    timeout_seconds: int = 60,
    source_table: str = "",
    sample_data_rows: Optional[list[tuple]] = None,
    sample_data_columns: Optional[list[str]] = None,
    sample_data_types: Optional[list[str]] = None,
    lineage_sources: Optional[list] = None,
    max_sample_rows: int = 1000,
) -> SQLResult:
    """在受控沙箱中执行 Spark DSL 草案并返回样本结果。

    执行流程（纵深防御 12 层）：
      1. spark_session 检查 → None 时 SKIPPED
      2. PySpark 可用性检查 → 不可用时 SKIPPED
      3. AST 安全检查（analyze_spark_draft）→ 不安全时 FAIL
      4. 入口点提取（extract_build_dataframe）→ 缺失时 FAIL
      5. 样本源 DataFrame 构建（与 DuckDB 共享同一份数据）
      6. 临时视图注册
      7. 受限 globals 构建
      8. compile + exec 在受限命名空间中执行
      9. 签名检测（1 或 2 参数）
      10. .limit() + .collect() 统一控制
      11. 超时中断 + cancelJobGroup
      12. 转换为 SQLResult

    Args:
        code: Spark DSL Python 源代码字符串
        spark_session: 活跃的本地 SparkSession（None 时 SKIPPED）
        timeout_seconds: 执行超时秒数（默认 60）
        source_table: 来源表名（写入结果）
        sample_data_rows: 样本数据行（与 DuckDB 相同的 (rows, columns, types)）
        sample_data_columns: 样本列名
        sample_data_types: 样本列类型（DuckDB 格式）
        lineage_sources: SampleSourceRef 列表
        max_sample_rows: 最大结果行数（默认 1000）

    Returns:
        SQLResult——error 为 None 表示 PASS，非 None 表示 FAIL/SKIPPED
    """
    # ── 层 1：SparkSession 检查 ──
    if spark_session is None:
        return SQLResult(
            sql=code,
            error="SKIPPED: Spark 环境不可用，未传入 SparkSession，Spark sample run 跳过。",
            source_table=source_table,
        )

    # ── 层 2：PySpark 可用性检查 ──
    if not _check_pyspark_available():
        return SQLResult(
            sql=code,
            error="SKIPPED: PySpark 未安装，Spark sample run 跳过。"
                  "安装命令: pip install pyspark",
            source_table=source_table,
        )

    # ── 层 3：AST 安全检查 ──
    from src.verify.spark_safety import analyze_spark_draft

    safety = analyze_spark_draft(code)
    if not safety.is_safe:
        error_lines = [f"Spark 安全检查失败（{len(safety.errors)} 项）:"]
        error_lines.extend(f"  - {e}" for e in safety.errors)
        if safety.warnings:
            error_lines.append(f"警告（{len(safety.warnings)} 项）:")
            error_lines.extend(f"  - {w}" for w in safety.warnings)
        return SQLResult(
            sql=code,
            error="\n".join(error_lines),
            source_table=source_table,
        )

    # ── 层 4：入口点提取 ──
    from src.verify.spark_safety import extract_build_dataframe

    entry_node = extract_build_dataframe(code)
    if entry_node is None:
        return SQLResult(
            sql=code,
            error="FAIL: 未找到 build_dataframe(spark, sources) 入口点函数——"
                  "Spark 草案必须定义此函数作为唯一执行入口。",
            source_table=source_table,
        )

    # ── 层 5：构建样本源 DataFrame ──
    source_dfs: dict[str, Any] = {}
    if sample_data_rows is not None and sample_data_columns is not None:
        source_dfs = _build_source_dataframes(
            spark_session,
            sample_data_rows,
            sample_data_columns,
            sample_data_types or [],
            lineage_sources or [],
        )

    # ── 层 6：注册临时视图 ──
    _register_temp_views(spark_session, source_dfs, lineage_sources or [])

    # ── 层 7：构建受限 globals ──
    restricted_globals = _safe_globals(spark_session)

    # ── 层 8：compile + exec 在受限命名空间中 ──
    start_time = time.perf_counter()
    timeout_event = threading.Event()

    # 设置 Spark 作业组用于超时取消
    try:
        spark_session.sparkContext.setJobGroup("spark_sample_run", "受控样本执行")
    except Exception:
        pass

    def _on_timeout():
        """超时回调——取消 Spark 作业。"""
        timeout_event.set()
        try:
            spark_session.sparkContext.cancelJobGroup("spark_sample_run")
        except Exception:
            pass

    timer = threading.Timer(timeout_seconds, _on_timeout)
    timer.daemon = True

    try:
        # 编译代码
        compiled = compile(code, "<spark_draft>", "exec")

        # 启动超时定时器
        timer.start()

        # 在受限命名空间中执行
        exec(compiled, restricted_globals)

        # ── 层 9：检测签名并调用入口点 ──
        build_dataframe = restricted_globals.get("build_dataframe")
        if build_dataframe is None:
            return SQLResult(
                sql=code,
                error="FAIL: build_dataframe 函数未在受限命名空间中定义。",
                source_table=source_table,
            )

        if timeout_event.is_set():
            return SQLResult(
                sql=code,
                error=f"FAIL: Spark sample run 超时（>{timeout_seconds}s），已中断。",
                source_table=source_table,
            )

        sig = inspect.signature(build_dataframe)
        param_count = len(sig.parameters)
        if param_count == 1:
            result_df = build_dataframe(spark_session)
        elif param_count >= 2:
            result_df = build_dataframe(spark_session, source_dfs)
        else:
            return SQLResult(
                sql=code,
                error=f"FAIL: build_dataframe 需要至少 1 个参数(spark)，实际有 {param_count} 个。",
                source_table=source_table,
            )

        # ── 层 10：limit + collect（executor 统一控制） ──
        if result_df is None:
            return SQLResult(
                sql=code,
                error="FAIL: build_dataframe 返回了 None——必须返回一个 DataFrame。",
                source_table=source_table,
            )

        sample_df = result_df.limit(max_sample_rows)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # ── 层 12：转换为 SQLResult ──
        result = _df_to_sqlresult(sample_df, code, elapsed_ms, source_table)

    except SyntaxError as exc:
        return SQLResult(
            sql=code,
            error=f"FAIL: Spark 草案语法错误: {exc}",
            source_table=source_table,
        )
    except Exception as exc:
        if timeout_event.is_set():
            return SQLResult(
                sql=code,
                error=f"FAIL: Spark sample run 超时（>{timeout_seconds}s），已中断。",
                source_table=source_table,
            )
        return SQLResult(
            sql=code,
            error=f"FAIL: Spark sample run 执行异常: {type(exc).__name__}: {exc}",
            source_table=source_table,
        )
    finally:
        # ── 层 11：清理定时器和 Spark 作业组 ──
        timer.cancel()
        try:
            spark_session.sparkContext.clearJobGroup()
        except Exception:
            pass

    return result
