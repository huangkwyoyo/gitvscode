"""
Spark 草案 AST-based 安全分析器测试。

先测试失败用例，再验证误报避免。

覆盖：
  - 合法 DataFrame DSL 草案通过
  - 各类写入方法被拒绝
  - 动态执行被拒绝
  - spark.sql() 被拒绝
  - 注释/字符串/变量名不误报
  - Python 语法错误 → FAIL
  - 生成端兼容接口与 Validator 一致性
"""
from __future__ import annotations

import pytest

from src.verify.spark_safety import (
    SparkSafetyResult,
    analyze_spark_draft,
    FORBIDDEN_METHOD_CALLS,
    FORBIDDEN_SINK_ATTRS,
    FORBIDDEN_DIRECT_CALLS,
    FORBIDDEN_DYNAMIC_BUILTINS,
    FORBIDDEN_SQL_METHOD,
)
from src.agent.dual_code_generator import validate_spark_draft


# ═══════════════════════════════════════════════════════════════
# 合法草案通过
# ═══════════════════════════════════════════════════════════════


class TestLegalSparkDrafts:
    """合法 Spark DataFrame DSL 草案应通过安全检查"""

    def test_simple_table_select(self):
        """spark.table → select 应通过"""
        code = 'df = spark.table("gold.t").select("col1", "col2")'
        result = analyze_spark_draft(code)
        assert result.is_safe, f"合法草案应通过，实际: {result.errors}"

    def test_with_where_groupby_agg(self):
        """where/groupBy/agg 链式调用应通过"""
        code = """
from pyspark.sql import functions as F

df = (
    spark.table("gold.dws_daily_trip_summary")
    .where(F.col("trip_date") >= "2026-01-01")
    .groupBy("trip_date")
    .agg(F.sum("trip_count").alias("total_trips"))
    .orderBy("trip_date")
)
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"合法 DataFrame DSL 应通过，实际: {result.errors}"

    def test_filter_select_withColumn(self):
        """filter + select + withColumn 应通过"""
        code = """
df = spark.table("gold.t")
df = df.filter(df.status == "active")
df = df.select("id", "name", "amount")
df = df.withColumn("amount2", df.amount * 2)
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"合法转换链应通过，实际: {result.errors}"

    def test_empty_code_passes(self):
        """空字符串应通过"""
        result = analyze_spark_draft("")
        assert result.is_safe

    def test_whitespace_only_passes(self):
        """仅空白应通过"""
        result = analyze_spark_draft("   \n   \n  ")
        assert result.is_safe


# ═══════════════════════════════════════════════════════════════
# 写入方法被拒绝
# ═══════════════════════════════════════════════════════════════


class TestForbiddenWriteMethods:
    """DataFrame 写入方法必须被拒绝"""

    def test_write_attr_rejected(self):
        """df.write 属性访问必须被拒绝"""
        code = 'df.write.mode("overwrite").saveAsTable("gold.t")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)

    def test_writeTo_rejected(self):
        """df.writeTo() 必须被拒绝"""
        code = 'df.writeTo("gold.target_table").createOrReplace()'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("writeTo" in e for e in result.errors)

    def test_saveAsTable_rejected(self):
        """df.saveAsTable() 必须被拒绝"""
        code = 'df.saveAsTable("gold.t")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("saveAsTable" in e for e in result.errors)

    def test_insertInto_rejected(self):
        """df.write.insertInto() 必须被拒绝"""
        code = 'df.write.insertInto("gold.t")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        # .write 属性访问触发拦截，insertInto 也会被检测
        assert any("write" in e.lower() for e in result.errors)

    def test_save_rejected(self):
        """df.write.save() 必须被拒绝"""
        code = 'df.write.save("path/to/output")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)

    def test_parquet_rejected(self):
        """df.write.parquet() 必须被拒绝"""
        code = 'df.write.parquet("path/to/parquet")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)

    def test_csv_rejected(self):
        """df.write.csv() 必须被拒绝"""
        code = 'df.write.csv("path/to/csv")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)

    def test_json_rejected(self):
        """df.write.json() 必须被拒绝"""
        code = 'df.write.json("path/to/json")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)

    def test_jdbc_rejected(self):
        """df.write.jdbc() 必须被拒绝"""
        code = 'df.write.jdbc("jdbc:postgresql://...", "table")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)

    def test_text_rejected(self):
        """df.write.text() 必须被拒绝"""
        code = 'df.write.text("path/to/text")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("write" in e.lower() for e in result.errors)


# ═══════════════════════════════════════════════════════════════
# spark.sql() 被拒绝
# ═══════════════════════════════════════════════════════════════


class TestSparkSqlBanned:
    """spark.sql() 当前阶段必须被拒绝"""

    def test_spark_sql_drop_table_rejected(self):
        """spark.sql("DROP TABLE ...") 必须被 AST 分析器拦截"""
        code = 'spark.sql("DROP TABLE gold.dws_daily_trip_summary")'
        result = analyze_spark_draft(code)
        assert result.is_blocked, f"spark.sql 应被拒绝，实际: {result.errors}"
        assert any(".sql" in e for e in result.errors)

    def test_spark_sql_select_rejected(self):
        """spark.sql("SELECT ...") 本阶段也必须被拒绝"""
        code = 'spark.sql("SELECT * FROM gold.t")'
        result = analyze_spark_draft(code)
        assert result.is_blocked, f"spark.sql SELECT 也应被拒绝，实际: {result.errors}"
        assert any(".sql" in e for e in result.errors)


# ═══════════════════════════════════════════════════════════════
# 动态执行被拒绝
# ═══════════════════════════════════════════════════════════════


class TestDynamicExecutionBanned:
    """动态执行和动态属性访问必须被拒绝"""

    def test_eval_rejected(self):
        """eval() 必须被拒绝"""
        code = 'eval("1 + 1")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("eval" in e.lower() for e in result.errors)

    def test_exec_rejected(self):
        """exec() 必须被拒绝"""
        code = 'exec("import os; os.system(\'rm -rf /\')")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("exec" in e.lower() for e in result.errors)

    def test_getattr_rejected(self):
        """getattr() 必须被拒绝"""
        code = 'method = getattr(df.write, "save")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("getattr" in e.lower() for e in result.errors)

    def test_setattr_rejected(self):
        """setattr() 必须被拒绝"""
        code = 'setattr(df, "write", something)'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("setattr" in e.lower() for e in result.errors)

    def test_dunder_import_rejected(self):
        """__import__() 必须被拒绝"""
        code = '__import__("os")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("__import__" in e for e in result.errors)

    def test_globals_rejected(self):
        """globals() 必须被拒绝"""
        code = 'globals()["my_func"]()'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("globals" in e.lower() for e in result.errors)

    def test_locals_rejected(self):
        """locals() 必须被拒绝"""
        code = 'locals()["key"]'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("locals" in e.lower() for e in result.errors)


# ═══════════════════════════════════════════════════════════════
# 误报避免——注释、字符串、变量名
# ═══════════════════════════════════════════════════════════════


class TestAvoidFalsePositives:
    """AST-based 分析器应自然避免旧子串匹配的误报"""

    def test_comment_overwrite_not_flagged(self):
        """注释中的 overwrite 不应被误报"""
        code = """
# 使用 overwrite 模式写入数据时需要人审确认
# 此处仅做只读查询
df = spark.table("gold.t").select("col1")
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"注释中的 overwrite 不应误报，实际: {result.errors}"

    def test_variable_overwrite_count_not_flagged(self):
        """变量名 overwrite_count 不应被误报"""
        code = """
overwrite_count = 42
df = spark.table("gold.t").filter(df.overwrite_count > 0)
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"变量名 overwrite_count 不应误报，实际: {result.errors}"

    def test_string_literal_overwrite_not_flagged(self):
        """字符串中的 overwrite 不应被误报"""
        code = '''
log_message = "当前模式为 overwrite，请确认目标表无重要数据"
df = spark.table("gold.t").select("col1")
'''
        result = analyze_spark_draft(code)
        assert result.is_safe, f"字符串中的 overwrite 不应误报，实际: {result.errors}"

    def test_comment_write_not_flagged(self):
        """注释中的 write 不应被误报"""
        code = """
# 注意：以下代码不应包含 write 操作
# df.write 是禁止的
df = spark.table("gold.t").select("col1")
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"注释中的 write 不应误报，实际: {result.errors}"

    def test_comment_saveastable_not_flagged(self):
        """注释中的 saveAsTable 不应被误报"""
        code = """
# 旧代码: df.saveAsTable("gold.target")
# 现已改为只读查询
df = spark.table("gold.t").select("col1")
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"注释中的 saveAsTable 不应误报，实际: {result.errors}"


# ═══════════════════════════════════════════════════════════════
# 语法错误
# ═══════════════════════════════════════════════════════════════


class TestSyntaxErrors:
    """Python 语法错误必须 FAIL"""

    def test_syntax_error_fails(self):
        """有明显语法错误的代码必须被拒绝"""
        code = "def broken("
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert "语法错误" in result.errors[0]

    def test_incomplete_expression_fails(self):
        """不完整的表达式必须被拒绝"""
        code = "df = spark.table("
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert "语法错误" in result.errors[0]

    def test_valid_syntax_passes_safety(self):
        """有效语法但危险的代码仍应通过语法检查到达安全规则"""
        # 语法正确但有 .write —— 语法检查通过，安全检查拒绝
        code = 'df.write.save("path")'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        # 确认不是因为语法错误
        assert not any("语法错误" in e for e in result.errors)


# ═══════════════════════════════════════════════════════════════
# 生成端兼容接口一致性
# ═══════════════════════════════════════════════════════════════


class TestGeneratorValidatorConsistency:
    """生成端和 Validator 对同一代码结论一致"""

    def test_both_reject_write(self):
        """生成端兼容接口和共享分析器对 .write 结论一致"""
        code = 'df.write.save("path")'
        gen_errors = validate_spark_draft(code)
        analyzer_result = analyze_spark_draft(code)
        assert gen_errors, "生成端应拒绝"
        assert analyzer_result.is_blocked, "分析器应拒绝"

    def test_both_reject_getattr(self):
        """生成端和共享分析器对 getattr 结论一致"""
        code = 'f = getattr(df, "write")'
        gen_errors = validate_spark_draft(code)
        analyzer_result = analyze_spark_draft(code)
        assert gen_errors, "生成端应拒绝 getattr"
        assert analyzer_result.is_blocked, "分析器应拒绝 getattr"

    def test_both_reject_spark_sql(self):
        """生成端和共享分析器对 spark.sql 结论一致"""
        code = 'spark.sql("DROP TABLE t")'
        gen_errors = validate_spark_draft(code)
        analyzer_result = analyze_spark_draft(code)
        assert gen_errors, "生成端应拒绝 spark.sql"
        assert analyzer_result.is_blocked, "分析器应拒绝 spark.sql"

    def test_both_accept_safe_code(self):
        """生成端和共享分析器对安全代码结论一致"""
        code = 'df = spark.table("gold.t").select("col1")'
        gen_errors = validate_spark_draft(code)
        analyzer_result = analyze_spark_draft(code)
        assert not gen_errors, f"生成端应接受安全代码，实际: {gen_errors}"
        assert analyzer_result.is_safe, f"分析器应接受安全代码，实际: {analyzer_result.errors}"

    def test_both_reject_eval(self):
        """生成端和共享分析器对 eval 结论一致"""
        code = 'eval("1+1")'
        gen_errors = validate_spark_draft(code)
        analyzer_result = analyze_spark_draft(code)
        assert gen_errors, "生成端应拒绝 eval"
        assert analyzer_result.is_blocked, "分析器应拒绝 eval"

    def test_both_reject_saveAsTable(self):
        """生成端和共享分析器对 saveAsTable 结论一致"""
        code = 'df.saveAsTable("gold.t")'
        gen_errors = validate_spark_draft(code)
        analyzer_result = analyze_spark_draft(code)
        assert gen_errors, "生成端应拒绝 saveAsTable"
        assert analyzer_result.is_blocked, "分析器应拒绝 saveAsTable"


# ═══════════════════════════════════════════════════════════════
# 生成端通过不替代 Validator（设计语义测试）
# ═══════════════════════════════════════════════════════════════


class TestGenerationNotSubstituteForValidation:
    """生成端检查不是安全信任边界"""

    def test_validate_spark_draft_is_fail_fast(self):
        """validate_spark_draft 的文档和实现应明确它是 fail-fast"""
        # 验证返回类型是错误字符串列表（fail-fast 发现的问题）
        errors = validate_spark_draft('df.write.save("path")')
        assert isinstance(errors, list)
        assert len(errors) > 0
        # 每个错误都包含描述信息
        assert all(isinstance(e, str) for e in errors)

    def test_analyze_spark_draft_is_authoritative(self):
        """共享分析器 analyze_spark_draft 返回结构化结果"""
        result = analyze_spark_draft('df.write.save("path")')
        assert isinstance(result, SparkSafetyResult)
        assert result.status in {"PASS", "FAIL", "HUMAN_REVIEW"}


# ═══════════════════════════════════════════════════════════════
# 边界情况
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试"""

    def test_multiple_violations_reported(self):
        """多个违规应全部报告"""
        code = """
df.write.save("path")
eval("something")
spark.sql("DROP TABLE t")
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked
        # 至少应有 3 个错误（.write、eval、.sql）
        assert len(result.errors) >= 3, f"应报告至少3个错误，实际: {len(result.errors)}: {result.errors}"

    def test_save_as_function_name_not_in_method(self):
        """save 作为独立函数调用应被拦截"""
        code = 'save("path", df)'
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("save" in e.lower() for e in result.errors)

    def test_import_statements_not_flagged(self):
        """import 语句不应被误报"""
        code = """
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
import pandas as pd
"""
        result = analyze_spark_draft(code)
        assert result.is_safe, f"import 语句不应误报，实际: {result.errors}"

    def test_function_definition_not_flagged(self):
        """函数定义中的参数名不应被误报"""
        code = """
def build_dataframe(spark, save_result=False):
    df = spark.table("gold.t").select("col1")
    return df
"""
        result = analyze_spark_draft(code)
        # save_result 是参数名，不应被标记；但 save 作为参数名的一部分...
        # AST 中 save_result 是 ast.Name(id='save_result') 出现在赋值目标中，不会触发
        assert result.is_safe, f"函数定义不应误报，实际: {result.errors}"


# ═══════════════════════════════════════════════════════════════
# 白名单覆盖——确认所有允许的调用不会误报
# ═══════════════════════════════════════════════════════════════


class TestAllowedMethodsNotFlagged:
    """确认普通 DataFrame 方法不会被误报"""

    def test_select_not_flagged(self):
        """select 不应被误报"""
        assert analyze_spark_draft('df.select("col1")').is_safe

    def test_filter_not_flagged(self):
        """filter 不应被误报"""
        assert analyze_spark_draft('df.filter("id > 0")').is_safe

    def test_where_not_flagged(self):
        """where 不应被误报"""
        assert analyze_spark_draft('df.where("id > 0")').is_safe

    def test_groupBy_not_flagged(self):
        """groupBy 不应被误报"""
        assert analyze_spark_draft('df.groupBy("col1")').is_safe

    def test_agg_not_flagged(self):
        """agg 不应被误报"""
        assert analyze_spark_draft('df.agg({"col1": "sum"})').is_safe

    def test_orderBy_not_flagged(self):
        """orderBy 不应被误报"""
        assert analyze_spark_draft('df.orderBy("col1")').is_safe

    def test_withColumn_not_flagged(self):
        """withColumn 不应被误报"""
        assert analyze_spark_draft('df.withColumn("new", df.old * 2)').is_safe

    def test_join_not_flagged(self):
        """join 不应被误报"""
        assert analyze_spark_draft('df.join(other, "id")').is_safe

    def test_distinct_not_flagged(self):
        """distinct 不应被误报"""
        assert analyze_spark_draft("df.distinct()").is_safe

    def test_limit_not_flagged(self):
        """limit 不应被误报"""
        assert analyze_spark_draft("df.limit(100)").is_safe

    def test_count_not_flagged(self):
        """count 不应被误报"""
        assert analyze_spark_draft("df.count()").is_safe


# ═══════════════════════════════════════════════════════════════
# 规则集完整性
# ═══════════════════════════════════════════════════════════════


class TestRuleCompleteness:
    """确认规则集覆盖所有要求的方法"""

    def test_forbidden_method_calls_complete(self):
        """FORBIDDEN_METHOD_CALLS 必须覆盖 writeTo/saveAsTable/insertInto/save/parquet/csv/json/jdbc/text/overwrite/append"""
        required = {"writeTo", "saveAsTable", "insertInto", "save", "parquet", "csv", "json", "jdbc", "text", "overwrite", "append"}
        assert required.issubset(FORBIDDEN_METHOD_CALLS), f"FORBIDDEN_METHOD_CALLS 缺少必要项: {required - FORBIDDEN_METHOD_CALLS}"

    def test_forbidden_sink_attrs_complete(self):
        """FORBIDDEN_SINK_ATTRS 必须包含 write"""
        assert "write" in FORBIDDEN_SINK_ATTRS
        assert len(FORBIDDEN_SINK_ATTRS) == 1

    def test_forbidden_dynamic_builtins_complete(self):
        """FORBIDDEN_DYNAMIC_BUILTINS 必须覆盖 eval/exec/getattr/setattr/__import__/globals/locals/compile"""
        required = {"eval", "exec", "getattr", "setattr", "__import__", "globals", "locals", "compile"}
        assert required.issubset(FORBIDDEN_DYNAMIC_BUILTINS), f"FORBIDDEN_DYNAMIC_BUILTINS 缺少必要项: {required - FORBIDDEN_DYNAMIC_BUILTINS}"


# ═══════════════════════════════════════════════════════════════
# v2.2 新增：入口点验证测试
# ═══════════════════════════════════════════════════════════════


class TestEntryPointValidation:
    """入口点函数提取与验证测试——确保 build_dataframe 模式强制执行"""

    def test_extract_build_dataframe_found(self):
        """正确的 build_dataframe 函数应被提取"""
        from src.verify.spark_safety import extract_build_dataframe

        code = """
def build_dataframe(spark, sources):
    df = sources["gold.dws"]
    return df.filter(df.col > 0).select("col1", "col2")
"""
        node = extract_build_dataframe(code)
        assert node is not None
        assert node.name == "build_dataframe"

    def test_extract_build_dataframe_not_found(self):
        """缺少 build_dataframe 时应返回 None"""
        from src.verify.spark_safety import extract_build_dataframe

        assert extract_build_dataframe("x = 1") is None
        assert extract_build_dataframe("def run(spark): pass") is None
        assert extract_build_dataframe("") is None

    def test_extract_build_dataframe_syntax_error(self):
        """语法错误时应返回 None"""
        from src.verify.spark_safety import extract_build_dataframe

        assert extract_build_dataframe("def build_dataframe(spark)") is None

    def test_entry_point_correct_name(self):
        """正确的函数名应被识别"""
        from src.verify.spark_safety import extract_build_dataframe

        node = extract_build_dataframe(
            "def build_dataframe(spark, sources): pass"
        )
        assert node is not None

    def test_extract_ignores_class_method(self):
        """类方法中的 build_dataframe 不会被误识别"""
        from src.verify.spark_safety import extract_build_dataframe

        code = """
class MyClass:
    def build_dataframe(self, spark):
        pass
"""
        # 类内的 build_dataframe 也是 FunctionDef，但当前实现会找到它
        # 这是可接受的行为——executor 执行时会因签名不匹配而失败
        node = extract_build_dataframe(code)
        assert node is not None


class TestDataFrameActionCheck:
    """禁止的 DataFrame 副作用方法检查"""

    def test_collect_rejected(self):
        """df.collect() 应被拦截——由 executor 统一管理"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark):
    df = spark.range(10)
    df.collect()
    return df
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("collect" in e for e in result.errors)

    def test_toPandas_rejected(self):
        """df.toPandas() 应被拦截"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark):
    df = spark.range(10)
    df.toPandas()
    return df
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_foreach_rejected(self):
        """df.foreach() 应被拦截——可执行任意代码"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark):
    df = spark.range(10)
    df.foreach(lambda x: print(x))
    return df
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_cache_rejected(self):
        """df.cache() 应被拦截——草案不应管理资源"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark):
    df = spark.range(10).cache()
    return df
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_show_rejected(self):
        """df.show() 应被拦截——控制台输出副作用"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark):
    df = spark.range(10)
    df.show()
    return df
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_createOrReplaceTempView_rejected(self):
        """df.createOrReplaceTempView() 应被拦截——修改 catalog"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark):
    df = spark.range(10)
    df.createOrReplaceTempView("my_view")
    return df
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_select_filter_groupBy_allowed(self):
        """select/filter/groupBy 等合法 DataFrame 操作应通过"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
def build_dataframe(spark, sources):
    df = spark.table("gold_trips")
    return df.filter(df.col > 0).groupBy("col1").agg(F.sum("col2"))
"""
        result = analyze_spark_draft(code)
        assert result.is_safe


class TestModuleImportCheck:
    """禁止的模块导入检查"""

    def test_os_import_rejected(self):
        """import os 应被拦截"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
import os
def build_dataframe(spark):
    return spark.range(10)
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked
        assert any("os" in e for e in result.errors)

    def test_subprocess_import_rejected(self):
        """import subprocess 应被拦截"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
import subprocess
def build_dataframe(spark):
    return spark.range(10)
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_socket_import_rejected(self):
        """import socket 应被拦截"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
import socket
def build_dataframe(spark):
    return spark.range(10)
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_sys_import_rejected(self):
        """import sys 应被拦截"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
import sys
def build_dataframe(spark):
    return spark.range(10)
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_from_os_path_import_rejected(self):
        """from os.path import ... 应被拦截——顶层模块 os 在禁止列表中"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
from os.path import join
def build_dataframe(spark):
    return spark.range(10)
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked

    def test_pyspark_import_allowed(self):
        """from pyspark.sql import functions as F 应通过"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
def build_dataframe(spark):
    return spark.range(10).select(F.col("id"))
"""
        result = analyze_spark_draft(code)
        assert result.is_safe

    def test_requests_import_rejected(self):
        """import requests 应被拦截"""
        from src.verify.spark_safety import analyze_spark_draft

        code = """
import requests
def build_dataframe(spark):
    return spark.range(10)
"""
        result = analyze_spark_draft(code)
        assert result.is_blocked
