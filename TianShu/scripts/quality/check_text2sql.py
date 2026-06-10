"""
Text2SQL 中文问数能力评测门禁

基于规则引擎对标准中文问题集进行五维评测：
1. 表选择 — SQL 中引用的表是否与推荐表一致
2. 指标正确 — 引用的指标是否已在 meta.metric_definitions 注册
3. SQL 可执行性 — 标准 SQL 能否在 DuckDB 中成功执行
4. 结果一致性 — 执行结果的签名（行数、列名、列类型）与基线是否一致
5. 层级合规 — 是否遵循 Gold G3 > G2 > Silver > Bronze 的优先级规则

输出：pass/fail + 错误原因 + Markdown 评测报告 + 结果签名基线
"""
import argparse
import datetime
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness_config import load_harness_config

try:
    import duckdb
except ImportError:
    duckdb = None


# ─── 常量 ───────────────────────────────────────────

# 表层级优先级（数字越大越优先）
LAYER_PRIORITY = {
    "G3": 4,       # 汇总表，最优
    "G2": 3,       # 明细事实表，可接受
    "G1": 2,       # 业务维表
    "G0": 1,       # 公共维表
    "silver": 0,   # Silver 明细层，应回退到 Gold
    "bronze": -1,  # Bronze 原始层，禁止用于回答业务问题
}

LAYER_DESC = {
    "G3": "G3 汇总表，最优",
    "G2": "G2 明细事实表，可接受但非最优",
    "G1": "G1 业务维表，仅维度属性，无事实指标",
    "G0": "G0 公共维表，仅维度属性，无事实指标",
    "silver": "Silver 明细层，应优先使用 Gold",
    "bronze": "Bronze 原始层，禁止直接回答业务问题",
}

# SQL 表引用正则：匹配 FROM / JOIN 后的 schema.table 或单独 table
TABLE_REF_RE = re.compile(
    r'(?:FROM|JOIN)\s+`?([a-zA-Z][a-zA-Z0-9_]*)\.([a-zA-Z][a-zA-Z0-9_]*)`?',
    re.IGNORECASE,
)

# SQL 无 schema 前缀的表引用
BARE_TABLE_RE = re.compile(
    r'(?:FROM|JOIN)\s+`?([a-zA-Z][a-zA-Z0-9_]*)`?(?!\.)',
    re.IGNORECASE,
)

# G3 汇总表前缀
G3_PREFIX = "dws_"
# G2 明细事实表前缀
G2_PREFIX = "fact_"
# 维表前缀
DIM_PREFIX = "dim_"


# ─── 数据结构 ───────────────────────────────────────

@dataclass
class Question:
    """标准中文问数问题"""
    id: str
    question_zh: str
    recommended_table: str
    metric_names: list[str]
    sql: str
    caution: str = ""
    expected_tables: list[str] = field(default_factory=list)


@dataclass
class EvalItem:
    """单个评测维度的结果"""
    status: str        # PASS / WARN / FAIL
    label: str         # 维度中文名，如"表选择"
    detail: str        # 详细说明
    fix_hint: str      # 修复建议（仅 WARN/FAIL 时有值）


@dataclass
class QuestionResult:
    """单题评测结果"""
    question_id: str
    question_zh: str
    items: list[EvalItem]  # 五个维度的评测结果

    @property
    def has_failure(self) -> bool:
        """是否有 FAIL 项"""
        return any(item.status == "FAIL" for item in self.items)

    @property
    def has_warning(self) -> bool:
        """是否有 WARN 项（且无 FAIL）"""
        return (not self.has_failure
                and any(item.status == "WARN" for item in self.items))


# ─── 问题加载 ───────────────────────────────────────

def load_questions(questions_path: Path) -> list[Question]:
    """从 YAML 文件读取标准中文问数集"""
    if not questions_path.exists():
        raise FileNotFoundError(f"标准中文问数集不存在: {questions_path}")

    data = yaml.safe_load(questions_path.read_text(encoding="utf-8")) or {}
    raw = data.get("questions", [])
    if not isinstance(raw, list):
        raise ValueError("questions 必须是列表")

    questions: list[Question] = []
    for item in raw:
        qid = item.get("id", "")
        for field in ["question_zh", "recommended_table", "sql"]:
            if not item.get(field):
                raise ValueError(f"{qid or '未命名问题'} 缺少必填字段: {field}")
        # metric_names 允许为空列表（纯维度查询）
        if "metric_names" not in item:
            raise ValueError(f"{qid or '未命名问题'} 缺少必填字段: metric_names")

        questions.append(Question(
            id=qid,
            question_zh=item["question_zh"],
            recommended_table=item["recommended_table"],
            metric_names=list(item.get("metric_names", [])),
            sql=item["sql"],
            caution=item.get("caution", ""),
            expected_tables=list(item.get("expected_tables", [])),
        ))
    return questions


# ─── Schema 层级解析 ────────────────────────────────

def parse_schema_hierarchy(conn) -> dict[str, dict]:
    """
    从 DuckDB information_schema 构建表→层级映射。

    返回:
        {"gold.dws_daily_trip_summary": {"layer": "G3", "layer_desc": "G3 汇总表", "columns": {...}}, ...}
    """
    hierarchy: dict[str, dict] = {}

    rows = conn.execute(
        """
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE table_schema IN ('gold', 'silver', 'bronze')
        ORDER BY table_schema, table_name, ordinal_position
        """
    ).fetchall()

    for schema, table, column in rows:
        full_name = f"{schema}.{table}"
        if full_name not in hierarchy:
            layer = _classify_layer(schema, table)
            hierarchy[full_name] = {
                "schema": schema,
                "table": table,
                "layer": layer,
                "layer_desc": LAYER_DESC.get(layer, f"未知层级: {schema}"),
                "columns": set(),
            }
        hierarchy[full_name]["columns"].add(column.lower())

    return hierarchy


def _classify_layer(schema: str, table: str) -> str:
    """根据 schema 和表名前缀判断层级"""
    if schema == "bronze":
        return "bronze"
    if schema == "silver":
        return "silver"
    if schema == "gold":
        if table.startswith("dws_"):
            return "G3"
        if table.startswith("fact_"):
            return "G2"
        if table.startswith("dim_date"):
            return "G0"
        if table.startswith("dim_"):
            return "G1"
    return schema


# ─── SQL 解析 ───────────────────────────────────────

def extract_referenced_tables(sql: str) -> set[str]:
    """从 SQL 中提取所有引用的 schema.table 全限定名"""
    tables: set[str] = set()

    # 匹配 schema.table 格式
    for m in TABLE_REF_RE.finditer(sql):
        tables.add(f"{m.group(1)}.{m.group(2)}")

    return tables


def extract_select_columns(sql: str) -> set[str]:
    """
    从 SQL SELECT 子句中提取返回值列名。

    解析策略：
    1. 提取 SELECT 和 FROM 之间的内容
    2. 按逗号分割
    3. 对每个表达式取最后一个标识符（即别名或列名）
    """
    # 找到最后一个 FROM（处理子查询嵌套）
    select_match = re.search(r'\bSELECT\b\s+(.+?)\s+\bFROM\b', sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return set()

    select_clause = select_match.group(1)

    # 移除注释
    select_clause = re.sub(r'--.*$', '', select_clause, flags=re.MULTILINE)

    columns: set[str] = set()
    # 简单按逗号分割（不够完美，但对标准 SQL 够用）
    parts = _split_select_parts(select_clause)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 处理 "expr AS alias" → 取 alias
        as_match = re.search(r'\bAS\s+`?(\w+)`?\s*$', part, re.IGNORECASE)
        if as_match:
            columns.add(as_match.group(1).lower())
            continue
        # 处理 "table.column" → 取 column
        dot_match = re.search(r'\.([A-Za-z0-9_]+)\s*$', part)
        if dot_match:
            columns.add(dot_match.group(1).lower())
            continue
        # 处理简单列名或聚合函数 → 取最后一个标识符
        ident_match = re.findall(r'([A-Za-z][A-Za-z0-9_]*)', part)
        if ident_match:
            # 跳过 SQL 关键字
            sql_keywords = {
                "select", "from", "where", "and", "or", "as", "on",
                "order", "by", "group", "having", "limit", "offset",
                "asc", "desc", "null", "not", "in", "is", "like",
                "between", "case", "when", "then", "else", "end",
                "distinct", "all", "count", "sum", "avg", "min", "max",
                "left", "right", "inner", "outer", "cross", "join",
            }
            meaningful = [w.lower() for w in ident_match if w.lower() not in sql_keywords]
            if meaningful:
                # 聚合函数取值：count(*) → count, sum(col) → sum, col → col
                # 取最后一个有意义的标识符（聚合函数的参数）
                columns.add(meaningful[-1])

    return columns


def _split_select_parts(select_clause: str) -> list[str]:
    """按逗号分割 SELECT 子句，考虑括号嵌套"""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in select_clause:
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            current.append(ch)
    if current:
        parts.append(''.join(current))
    return parts


# ─── 指标解析 ───────────────────────────────────────

def load_registered_metrics(conn) -> set[str]:
    """读取 meta.metric_definitions 中已注册的指标名"""
    try:
        rows = conn.execute(
            "SELECT metric_name FROM meta.metric_definitions"
        ).fetchall()
        return {row[0].lower() for row in rows}
    except Exception:
        return set()


def load_registered_dimensions(conn) -> dict[str, str]:
    """读取 meta.semantic_dimensions，返回 {dimension_name: source_table}"""
    try:
        rows = conn.execute(
            "SELECT dimension_name, source_table FROM meta.semantic_dimensions"
        ).fetchall()
        return {row[0].lower(): row[1] for row in rows}
    except Exception:
        return {}


# ─── 五维评测函数 ──────────────────────────────────

def check_table_selection(
    sql: str, question: Question, schema: dict,
) -> EvalItem:
    """
    表选择评测。

    检查逻辑：
    1. 提取 SQL 中实际引用的表
    2. 与 expected_tables（或 recommended_table）比对
    3. 判定是否准确选择了推荐表
    """
    actual_tables = extract_referenced_tables(sql)
    # 若无 schema 前缀的表，尝试匹配
    if not actual_tables:
        # 可能与 Gold 表名匹配（无 schema）
        bare_matches = {m.group(1).lower() for m in BARE_TABLE_RE.finditer(sql)}
        for full_name in schema:
            if full_name.split(".")[-1].lower() in bare_matches:
                actual_tables.add(full_name)

    expected = set(question.expected_tables) if question.expected_tables else {question.recommended_table}

    if not actual_tables:
        return EvalItem(
            status="FAIL",
            label="表选择",
            detail="无法从 SQL 中解析出表引用",
            fix_hint="检查 SQL 是否包含 FROM 子句，表名是否使用了 schema 前缀（如 gold.dws_xxx）",
        )

    # 检查推荐表是否在 SQL 中被引用
    rec_schema, rec_table = _split_table_name(question.recommended_table)
    rec_in_sql = any(
        (rec_table.lower() == t.split(".")[-1].lower())
        for t in actual_tables
    )

    # 检查 expected_tables 的覆盖情况
    missing_expected = set()
    for exp_table in expected:
        exp_schema, exp_name = _split_table_name(exp_table)
        if not any(
            exp_name.lower() == t.split(".")[-1].lower()
            for t in actual_tables
        ):
            missing_expected.add(exp_table)

    if not missing_expected:
        # 所有期望表都已引用
        layer_info = ", ".join(
            f"`{t}` ({schema.get(t, {}).get('layer_desc', '未知')})"
            for t in actual_tables if t in schema
        )
        return EvalItem(
            status="PASS",
            label="表选择",
            detail=f"SQL 正确引用了推荐表: {layer_info}",
            fix_hint="",
        )

    return EvalItem(
        status="FAIL",
        label="表选择",
        detail=f"期望引用 {sorted(missing_expected)}，但实际引用 {sorted(actual_tables)}",
        fix_hint=f"修改 SQL 的 FROM 子句，使用推荐表 `{question.recommended_table}`",
    )


def check_metrics(
    sql: str, question: Question, registered_metrics: set[str],
    schema: dict,
) -> EvalItem:
    """
    指标正确性评测。

    检查逻辑：
    1. 验证 question.metric_names 都已在 meta.metric_definitions 注册
    2. 从 SQL 中提取引用的表，获取这些表的列集合
    3. 验证 SELECT 返回的列名能在相关表的列集合中找到
    注意：指标名（如 parking_violation_count）可能与物理列名（如 violation_count）不同，
    不要求字面匹配——只要指标已注册、SQL 列在表中存在即可。
    """
    metric_names_lower = {m.lower() for m in question.metric_names}
    select_columns = extract_select_columns(sql)
    actual_tables = extract_referenced_tables(sql)

    # 收集 SQL 引用的表中所有可用列
    available_columns: set[str] = set()
    for table_full in actual_tables:
        if table_full in schema:
            available_columns |= schema[table_full].get("columns", set())

    violations: list[str] = []

    # 检查 1：指标是否已注册
    unregistered = metric_names_lower - registered_metrics
    if unregistered:
        violations.append(f"指标未在 meta.metric_definitions 注册: {sorted(unregistered)}")

    # 检查 2：SQL 返回值列是否都能在引用表中找到
    # 注意：已注册的指标名和聚合函数别名是合法的派生列，不需要在物理列中存在
    if select_columns and available_columns:
        unknown_columns = select_columns - available_columns
        # 排除已注册指标（它们可能是 count(*) AS trip_count 等派生列）
        unknown_columns = {
            c for c in unknown_columns
            if c not in registered_metrics
        }
        # 排除明确的聚合函数名和字面量
        unknown_columns = {
            c for c in unknown_columns
            if c not in {"count", "sum", "avg", "min", "max"} and not c.startswith("?")
        }
        if unknown_columns:
            violations.append(
                f"SQL 返回值列在引用表中找不到: {sorted(unknown_columns)}"
            )
    elif not available_columns:
        # 无法解析表引用，只检查指标注册
        pass

    if violations:
        return EvalItem(
            status="FAIL",
            label="指标",
            detail="; ".join(violations),
            fix_hint=(
                "确保指标已在 meta.metric_definitions 注册，"
                "且 SELECT 列名与引用表的物理列名一致"
            ),
        )

    detail_parts: list[str] = []
    if metric_names_lower:
        detail_parts.append(f"指标已注册: {sorted(metric_names_lower)}")
    elif select_columns:
        detail_parts.append(f"返回值列: {sorted(select_columns)}")
    if not metric_names_lower:
        detail_parts.insert(0, "无指标要求（纯维度查询）")

    return EvalItem(
        status="PASS",
        label="指标",
        detail="; ".join(detail_parts) if detail_parts else "指标检查通过",
        fix_hint="",
    )


def check_sql_executable(conn, sql: str) -> EvalItem:
    """
    SQL 可执行性评测。

    使用 LIMIT 0 子查询验证 SQL 语法正确性，不做实际数据扫描。
    """
    if duckdb is None:
        return EvalItem(
            status="FAIL",
            label="SQL 可执行性",
            detail="duckdb 未安装，无法检查",
            fix_hint="安装 duckdb: pip install duckdb",
        )

    try:
        # 用 LIMIT 0 验证语法，不实际扫描数据
        conn.execute(f"SELECT * FROM ({sql}) AS _check LIMIT 0").fetchall()
        return EvalItem(
            status="PASS",
            label="SQL 可执行性",
            detail="SQL 语法正确，可执行",
            fix_hint="",
        )
    except Exception as exc:
        return EvalItem(
            status="FAIL",
            label="SQL 可执行性",
            detail=f"SQL 执行失败: {exc}",
            fix_hint="检查表名、字段名是否正确，日期格式是否符合 DuckDB 语法",
        )


def check_result_signature(
    conn, sql: str, question_id: str,
    baseline: dict[str, dict] | None,
) -> tuple[EvalItem, dict[str, dict]]:
    """
    结果一致性评测。

    执行 SQL，记录结果签名（行数、列名、列类型），与基线比对。
    首次运行时自动创建基线。

    返回: (EvalItem, 更新后的签名映射)
    """
    new_signatures = dict(baseline or {})

    if duckdb is None:
        return EvalItem(
            status="FAIL",
            label="结果一致性",
            detail="duckdb 未安装",
            fix_hint="",
        ), new_signatures

    try:
        result = conn.execute(sql).fetchall()
        description = conn.description
        row_count = len(result)
        col_names = [d[0] for d in description]
        col_types = [str(d[1]) if len(d) > 1 else "unknown" for d in description]

        # 计算签名哈希
        sig_str = f"rows={row_count}|cols={','.join(col_names)}|types={','.join(col_types)}"
        sig_hash = hashlib.md5(sig_str.encode()).hexdigest()

        current = {
            "row_count": row_count,
            "columns": col_names,
            "column_types": col_types,
            "md5": sig_hash,
        }
        new_signatures[question_id] = current

        # 与基线比对
        if question_id in (baseline or {}):
            prev = baseline[question_id]
            if prev.get("md5") == sig_hash:
                return EvalItem(
                    status="PASS",
                    label="结果一致性",
                    detail=f"与基线一致: {row_count} 行, {len(col_names)} 列 ({', '.join(col_names)})",
                    fix_hint="",
                ), new_signatures
            else:
                diffs: list[str] = []
                if prev.get("row_count") != row_count:
                    diffs.append(f"行数 {prev.get('row_count')} → {row_count}")
                if prev.get("columns") != col_names:
                    diffs.append(f"列 {prev.get('columns')} → {col_names}")
                if prev.get("column_types") != col_types:
                    diffs.append(f"类型 {prev.get('column_types')} → {col_types}")
                return EvalItem(
                    status="FAIL",
                    label="结果一致性",
                    detail=f"结果签名与基线不一致: {'; '.join(diffs)}",
                    fix_hint=(
                        "确认标准 SQL 未修改、底层数据未重建。"
                        "若变更是预期内的，删除基线文件以重新建立基线。"
                    ),
                ), new_signatures
        else:
            return EvalItem(
                status="PASS",
                label="结果一致性",
                detail=f"基线已建立: {row_count} 行, {len(col_names)} 列",
                fix_hint="",
            ), new_signatures

    except Exception as exc:
        return EvalItem(
            status="FAIL",
            label="结果一致性",
            detail=f"无法执行 SQL 获取结果: {exc}",
            fix_hint="先修复 SQL 可执行性问题",
        ), new_signatures


def check_layer_compliance(sql: str, question: Question, schema: dict) -> EvalItem:
    """
    层级合规评测。

    规则（来自 agents/text2sql/AGENTS.md）：
    1. 禁止使用 Bronze 表回答业务问题
    2. 禁止在 Gold 层有合适表的情况下使用 Silver 表
    3. 当 G3 汇总表能回答问题却使用 G2 明细表时，给出 WARN
    """
    actual_tables = extract_referenced_tables(sql)
    if not actual_tables:
        return EvalItem(
            status="WARN",
            label="层级合规",
            detail="未能从 SQL 中解析出表引用，跳过层级检查",
            fix_hint="使用全限定表名（如 gold.dws_xxx）",
        )

    # 分类引用表
    layers_used: dict[str, list[str]] = {}
    for table_full in actual_tables:
        info = schema.get(table_full, {})
        layer = info.get("layer", "unknown")
        layers_used.setdefault(layer, []).append(table_full)

    violations: list[str] = []
    warnings: list[str] = []

    # 规则 1：禁止 Bronze
    if "bronze" in layers_used:
        violations.append(
            f"引用了 Bronze 表 {layers_used['bronze']}，"
            f"禁止直接使用原始层回答业务问题"
        )

    # 规则 2：禁止无必要地使用 Silver
    if "silver" in layers_used:
        violations.append(
            f"引用了 Silver 表 {layers_used['silver']}，"
            f"当前 Gold 层已建成，应使用 Gold 表"
        )

    # 规则 3：检查 G3 vs G2 降级
    if "G2" in layers_used and "G3" not in layers_used:
        # 检查推荐表是否为 G3 → 如果是，说明应该用 G3
        rec_info = schema.get(question.recommended_table, {})
        if rec_info.get("layer") == "G3":
            warnings.append(
                f"使用了 G2 明细表 {layers_used['G2']}，"
                f"但问题可用 G3 汇总表 `{question.recommended_table}` 回答。"
                f"优先使用 G3 汇总表可避免扫描大表"
            )

    if violations:
        return EvalItem(
            status="FAIL",
            label="层级合规",
            detail="; ".join(violations),
            fix_hint="遵循 Text2SQL 规则: Gold G3 > G2 > Silver > Bronze",
        )

    if warnings:
        return EvalItem(
            status="WARN",
            label="层级合规",
            detail="; ".join(warnings),
            fix_hint=f"建议将 SQL 改为使用推荐表 `{question.recommended_table}`",
        )

    # 层级合规，列出使用的表层级
    layer_summary = ", ".join(
        f"`{t}` ({schema.get(t, {}).get('layer_desc', '?')})"
        for t in sorted(actual_tables)
    )
    return EvalItem(
        status="PASS",
        label="层级合规",
        detail=f"表层级使用正确: {layer_summary}",
        fix_hint="",
    )


# ─── 辅助 ───────────────────────────────────────────

def _split_table_name(full_name: str) -> tuple[str, str]:
    """拆分 schema.table 为 (schema, table)"""
    parts = full_name.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "gold", parts[0]


# ─── 基线管理 ───────────────────────────────────────

def load_baseline(baseline_path: Path) -> dict[str, dict] | None:
    """读取结果签名基线，文件不存在时返回 None"""
    if not baseline_path.exists():
        return None
    data = yaml.safe_load(baseline_path.read_text(encoding="utf-8")) or {}
    return data.get("signatures", {})


def save_baseline(baseline_path: Path, signatures: dict[str, dict]) -> None:
    """保存结果签名基线"""
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "description": "Text2SQL 结果签名基线。删除此文件可强制重新生成。",
        "signatures": signatures,
    }
    baseline_path.write_text(
        yaml.dump(content, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


# ─── 报告生成 ───────────────────────────────────────

def generate_report(
    results: list[QuestionResult],
    report_dir: Path,
    schema_summary: dict[str, int],
) -> Path:
    """生成 Markdown 评测报告，返回报告路径"""
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"text2sql_report_{timestamp}.md"

    total = len(results)
    passed = sum(1 for r in results if not r.has_failure and not r.has_warning)
    warned = sum(1 for r in results if r.has_warning)
    failed = sum(1 for r in results if r.has_failure)

    lines: list[str] = []
    lines.append("# Text2SQL 中文问数能力评测报告")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**评测问题数**: {total}")
    lines.append(f"**通过**: {passed} | **警告**: {warned} | **失败**: {failed}")
    lines.append("")

    # 汇总表
    lines.append("## 评测汇总")
    lines.append("")
    lines.append("| 问题ID | 问题 | 表选择 | 指标 | 可执行 | 结果一致性 | 层级合规 | 总评 |")
    lines.append("|--------|------|--------|------|--------|------------|----------|------|")
    for r in results:
        status_icons: list[str] = []
        for item in r.items:
            if item.status == "PASS":
                status_icons.append("✅")
            elif item.status == "WARN":
                status_icons.append("⚠️")
            else:
                status_icons.append("❌")
        overall = "✅ 通过" if not r.has_failure and not r.has_warning else (
            "⚠️ 警告" if r.has_warning else "❌ 失败"
        )
        question_short = r.question_zh[:15] + ("..." if len(r.question_zh) > 15 else "")
        lines.append(
            f"| {r.question_id} | {question_short} | "
            + " | ".join(status_icons)
            + f" | {overall} |"
        )
    lines.append("")

    # 逐题详情
    lines.append("## 逐题详情")
    lines.append("")
    for r in results:
        overall = "✅ 通过" if not r.has_failure and not r.has_warning else (
            "⚠️ 警告" if r.has_warning else "❌ 失败"
        )
        lines.append(f"### {r.question_id} — {overall}")
        lines.append("")
        lines.append(f"> **问题**: {r.question_zh}")
        lines.append("")
        lines.append("| 维度 | 结果 | 详情 | 修复建议 |")
        lines.append("|------|------|------|----------|")
        for item in r.items:
            icon = "✅" if item.status == "PASS" else ("⚠️" if item.status == "WARN" else "❌")
            detail = item.detail[:120] + ("..." if len(item.detail) > 120 else "")
            fix = item.fix_hint[:100] + ("..." if len(item.fix_hint) > 100 else "") if item.fix_hint else "—"
            lines.append(f"| {item.label} | {icon} {item.status} | {detail} | {fix} |")
        lines.append("")

    # 统计
    lines.append("## 统计")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 问题总数 | {total} |")
    lines.append(f"| 全部通过 | {passed} |")
    lines.append(f"| 存在警告 | {warned} |")
    lines.append(f"| 存在失败 | {failed} |")
    lines.append(f"| 通过率 | {passed / total * 100:.1f}% |" if total > 0 else "| 通过率 | N/A |")
    lines.append("")
    lines.append("## Schema 概况")
    lines.append("")
    for schema_name, count in sorted(schema_summary.items()):
        lines.append(f"- **{schema_name}**: {count} 个表/指标")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    # 同时更新稳定版报告（覆盖写入，可提交的代表性报告）
    latest_path = report_dir / "text2sql_report_latest.md"
    latest_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path


# ─── 主评测流程 ─────────────────────────────────────

def evaluate_questions(
    conn, questions: list[Question], schema: dict,
    baseline: dict[str, dict] | None,
) -> tuple[list[QuestionResult], dict[str, dict]]:
    """对全部问题执行五维评测"""
    registered_metrics = load_registered_metrics(conn)
    results: list[QuestionResult] = []
    signatures = dict(baseline or {})

    for q in questions:
        items: list[EvalItem] = []

        # 1. 表选择
        items.append(check_table_selection(q.sql, q, schema))

        # 2. 指标正确
        items.append(check_metrics(q.sql, q, registered_metrics, schema))

        # 3. SQL 可执行
        items.append(check_sql_executable(conn, q.sql))

        # 4. 结果一致性
        sig_item, signatures = check_result_signature(conn, q.sql, q.id, signatures)
        items.append(sig_item)

        # 5. 层级合规
        items.append(check_layer_compliance(q.sql, q, schema))

        results.append(QuestionResult(
            question_id=q.id,
            question_zh=q.question_zh,
            items=items,
        ))

    return results, signatures


def main() -> int:
    """命令行入口"""
    # 确保 Windows 下中文和特殊字符能正常输出
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    config = load_harness_config()

    parser = argparse.ArgumentParser(description="Text2SQL 中文问数能力评测")
    parser.add_argument(
        "--db", type=Path, default=config.duckdb_path,
        help="DuckDB 数据库路径",
    )
    parser.add_argument(
        "--questions", type=Path,
        default=config.project_root / "harness" / "questions" / "gold_standard_questions.yml",
        help="标准中文问数集路径",
    )
    parser.add_argument(
        "--report-dir", type=Path,
        default=config.project_root / "harness" / "reports",
        help="评测报告输出目录",
    )
    parser.add_argument(
        "--baseline", type=Path,
        default=config.project_root / "harness" / "reports" / "text2sql_signature_baseline.yml",
        help="结果签名基线文件路径",
    )
    parser.add_argument(
        "--reset-baseline", action="store_true",
        help="强制重建基线（删除旧基线后重新生成）",
    )
    args = parser.parse_args()

    if duckdb is None:
        print("[FAIL] duckdb 未安装，无法执行 Text2SQL 评测")
        return 1

    if not args.db.exists():
        print(f"[FAIL] DuckDB 数据库不存在: {args.db}")
        return 1

    if not args.questions.exists():
        print(f"[FAIL] 标准中文问数集不存在: {args.questions}")
        return 1

    # 强制重建基线
    if args.reset_baseline and args.baseline.exists():
        args.baseline.unlink()
        print("[INFO] 已删除旧基线，将重新生成")

    try:
        # 加载问题
        questions = load_questions(args.questions)
        if len(questions) == 0:
            print("[FAIL] 标准中文问数集为空")
            return 1

        # 连接数据库
        conn = duckdb.connect(str(args.db), read_only=True)
        try:
            # 解析 schema 层级
            schema = parse_schema_hierarchy(conn)

            # 加载基线
            baseline = load_baseline(args.baseline)

            # 执行评测
            results, new_signatures = evaluate_questions(conn, questions, schema, baseline)

            # 构建 schema 概况
            schema_summary = {
                "Gold G3 汇总表 (dws_*)": sum(
                    1 for v in schema.values() if v["layer"] == "G3"
                ),
                "Gold G2 明细事实表 (fact_*)": sum(
                    1 for v in schema.values() if v["layer"] == "G2"
                ),
                "Gold G0/G1 维表 (dim_*)": sum(
                    1 for v in schema.values() if v["layer"] in ("G0", "G1")
                ),
                "已注册指标 (meta.metric_definitions)": len(
                    load_registered_metrics(conn)
                ),
            }
        finally:
            conn.close()

        # 保存基线
        save_baseline(args.baseline, new_signatures)

        # 生成报告
        report_path = generate_report(results, args.report_dir, schema_summary)

        # 输出结果摘要
        failed_count = sum(1 for r in results if r.has_failure)
        warn_count = sum(1 for r in results if r.has_warning)
        pass_count = len(results) - failed_count - warn_count

        print(f"\n[INFO] Text2SQL 评测报告: {report_path}")
        print(f"[INFO] 结果签名基线: {args.baseline}")
        print(f"[INFO] 评测完成: {pass_count} 通过, {warn_count} 警告, {failed_count} 失败 (共 {len(results)} 题)")

        # 逐题输出
        for r in results:
            if r.has_failure:
                for item in r.items:
                    if item.status == "FAIL":
                        print(f"  ❌ {r.question_id}: [{item.label}] {item.detail[:100]}")
            elif r.has_warning:
                for item in r.items:
                    if item.status == "WARN":
                        print(f"  ⚠️ {r.question_id}: [{item.label}] {item.detail[:100]}")

        if failed_count > 0:
            print(f"\n[FAIL] Text2SQL 问数能力评测未通过，{failed_count} 题存在失败")
            return 1

        print(f"\n[OK] Text2SQL 问数能力评测通过 ({len(results)}/{len(results)})")
        return 0

    except Exception as exc:
        print(f"[FAIL] Text2SQL 问数能力评测执行失败: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
