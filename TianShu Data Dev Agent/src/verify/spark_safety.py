"""
Spark 草案结构化安全分析器（AST-based）。

替代旧的纯子串扫描，提供以下能力：
  - 使用 ast.parse() 做结构化分析，自然忽略注释和字符串字面量
  - 显式拦截 DataFrame 写入 sink、落盘格式、动态执行方法
  - 默认拒绝 spark.sql(...) 调用
  - Python 语法错误 → FAIL
  - 无法证明安全的间接调用 → HUMAN_REVIEW

这是 v2 安全规则关于 Spark 草案的**唯一事实源**。
dual_code_generator.py 和 checker.py 都必须调用此模块的统一入口。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
# 禁止规则定义——本模块是 Spark 安全规则的唯一事实源
# ═══════════════════════════════════════════════════════════════

# 禁止的 DataFrame/DataStreamWriter 方法调用（无论调用对象是谁）
# 这些方法一旦调用，即触发数据落盘或写入外部存储
FORBIDDEN_METHOD_CALLS: set[str] = {
    "writeTo",       # DataFrame.writeTo() —— 写入目标表
    "saveAsTable",   # DataFrame.saveAsTable() / DataFrameWriter.saveAsTable()
    "insertInto",    # DataFrameWriter.insertInto()
    "save",          # DataFrameWriter.save()
    "parquet",       # DataFrameWriter.parquet()
    "csv",           # DataFrameWriter.csv()
    "json",          # DataFrameWriter.json()
    "jdbc",          # DataFrameWriter.jdbc()
    "text",          # DataFrameWriter.text()
}

# 禁止作为属性被访问的写入网关（即使未被调用也可能是写入准备）
# .write 返回 DataFrameWriter，是通往所有 .save*/.insertInto 的唯一入口
FORBIDDEN_SINK_ATTRS: set[str] = {
    "write",         # df.write → DataFrameWriter
}

# 禁止的独立函数调用（落盘 / 数据导出）
FORBIDDEN_DIRECT_CALLS: set[str] = {
    "save",          # 独立 save() 调用
    "parquet",       # 独立 parquet() 调用
    "csv",           # 独立 csv() 调用
    "json",          # 独立 json() 调用
    "jdbc",          # 独立 jdbc() 调用
    "text",          # 独立 text() 调用
}

# 禁止的动态执行 / 动态属性访问
FORBIDDEN_DYNAMIC_BUILTINS: set[str] = {
    "eval",          # 动态执行字符串代码
    "exec",          # 动态执行语句
    "getattr",       # 动态属性访问——可绕过静态方法名检查
    "setattr",       # 动态属性设置
    "__import__",    # 动态导入模块
    "globals",       # 访问全局命名空间
    "locals",        # 访问局部命名空间
}

# spark.sql(...) 暂时禁止
# 如果未来要允许，必须：参数是静态字符串 + 提取 SQL 进入统一 SQL Validator
FORBIDDEN_SQL_METHOD = "sql"


@dataclass
class SparkSafetyResult:
    """Spark 草案结构化安全检查结果。"""

    status: str  # "PASS" | "FAIL" | "HUMAN_REVIEW"
    errors: list[str] = field(default_factory=list)
    """阻断级问题——草案不得进入 sample run"""
    warnings: list[str] = field(default_factory=list)
    """需人审关注的问题"""

    @property
    def is_safe(self) -> bool:
        """草案是否通过安全检查（可进入后续流程）。"""
        return self.status == "PASS"

    @property
    def is_blocked(self) -> bool:
        """草案是否被阻断。"""
        return self.status == "FAIL"


def analyze_spark_draft(code: str) -> SparkSafetyResult:
    """
    对 Spark DSL 草案执行结构化安全检查。

    检查顺序：
      1. Python 语法解析（语法错误 → FAIL）
      2. AST 遍历——拦截禁止的方法调用（写入 sink）
      3. AST 遍历——拦截禁止的属性访问（写入网关）
      4. AST 遍历——拦截禁止的独立函数调用（落盘）
      5. AST 遍历——拦截动态执行函数（eval/exec/getattr 等）
      6. AST 遍历——拦截 spark.sql(...) 调用

    Args:
        code: Spark DSL Python 源代码字符串

    Returns:
        SparkSafetyResult——status 为 PASS/FAIL/HUMAN_REVIEW
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── 步骤 1：解析 Python 语法 ──
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return SparkSafetyResult(
            status="FAIL",
            errors=[f"Python 语法错误，无法进行安全检查: {exc}"],
        )

    # ── 步骤 2-6：遍历 AST 节点 ──
    for node in ast.walk(tree):
        # 步骤 2：拦截禁止的写入方法调用（df.writeTo(...) 等）
        if isinstance(node, ast.Call):
            _check_method_call(node, errors)

        # 步骤 3：拦截禁止的写入网关属性访问（df.write）
        if isinstance(node, ast.Attribute):
            _check_sink_attr(node, errors)

        # 步骤 4：拦截禁止的独立函数调用（save(...) 等）
        if isinstance(node, ast.Call):
            _check_direct_call(node, errors)

        # 步骤 5：拦截动态执行函数
        if isinstance(node, ast.Call):
            _check_dynamic_builtin(node, errors)

        # 步骤 6：拦截 spark.sql(...) / 任意 .sql() 调用
        if isinstance(node, ast.Call):
            _check_sql_method(node, errors)

    # ── 汇总结果 ──
    if errors:
        return SparkSafetyResult(status="FAIL", errors=errors, warnings=warnings)

    if warnings:
        return SparkSafetyResult(status="HUMAN_REVIEW", errors=errors, warnings=warnings)

    return SparkSafetyResult(status="PASS")


def _check_method_call(node: ast.Call, errors: list[str]) -> None:
    """检查是否为禁止的写入方法调用（如 df.saveAsTable(...)）。"""
    if not isinstance(node.func, ast.Attribute):
        return
    method_name = node.func.attr
    if method_name in FORBIDDEN_METHOD_CALLS:
        errors.append(
            f"禁止的写入方法调用: .{method_name}()——"
            f"Spark 草案不得包含数据写入或落盘操作"
        )


def _check_sink_attr(node: ast.Attribute, errors: list[str]) -> None:
    """检查是否为禁止的写入网关属性访问（如 df.write）。"""
    if node.attr in FORBIDDEN_SINK_ATTRS:
        errors.append(
            f"禁止的写入网关属性: .{node.attr}——"
            f"DataFrame.write 是通往所有写入操作的入口，在只读草案中禁止"
        )


def _check_direct_call(node: ast.Call, errors: list[str]) -> None:
    """检查是否为禁止的独立落盘函数调用（如 save(...)）。"""
    if not isinstance(node.func, ast.Name):
        return
    func_name = node.func.id
    if func_name in FORBIDDEN_DIRECT_CALLS:
        errors.append(
            f"禁止的落盘函数调用: {func_name}()——Spark 草案不得直接调用数据导出函数"
        )


def _check_dynamic_builtin(node: ast.Call, errors: list[str]) -> None:
    """检查是否为禁止的动态执行或动态属性访问函数。"""
    if not isinstance(node.func, ast.Name):
        return
    func_name = node.func.id
    if func_name in FORBIDDEN_DYNAMIC_BUILTINS:
        errors.append(
            f"禁止的动态执行函数: {func_name}()——"
            f"Spark 草案不得使用动态执行或动态属性访问，这会绕过静态安全检查"
        )


def _check_sql_method(node: ast.Call, errors: list[str]) -> None:
    """检查是否为 .sql() 方法调用（如 spark.sql("DROP TABLE ...")）。

    当前阶段禁止任意 .sql() 调用，因为无法对其中的 SQL 字符串做静态安全分析。
    如果未来要允许，必须：
      - 参数是静态字符串字面量
      - 提取 SQL 进入统一 SQL Validator（checks.FORBIDDEN_KEYWORDS）
      - 动态 SQL（f-string / 变量拼接）必须 FAIL
    """
    if not isinstance(node.func, ast.Attribute):
        return
    if node.func.attr == FORBIDDEN_SQL_METHOD:
        errors.append(
            f"禁止的 SQL 方法调用: .sql()——"
            f"Spark 草案当前阶段不允许嵌入 SQL 字符串，"
            f"请使用 PySpark DataFrame DSL 表达查询逻辑"
        )
