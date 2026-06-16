"""
ChartSpec 规则图表规格生成器。

职责：
    基于 ResultSummary / MergedResult 的结构化摘要，用纯规则（非 LLM、
    非前端代码）生成图表规格。输出为纯 JSON 可序列化结构，
    供后续 UI 或报告层消费。

严格边界：
    1. 不生成前端代码（HTML/CSS/JS）
    2. 不调用浏览器
    3. 不调用 LLM
    4. 不执行 SQL
    5. 不访问 DuckDB
    6. 不修改 SQLPlan
    7. 不改变 result_merge
    8. 不做因果解释
    9. 不把图表当成事实推断来源

图表类型选择规则：
    - MergedResult 且 merge_key=date、多值列 → line
    - 单个 ResultSummary 有 date + 数值列 → line
    - 单个 ResultSummary 无 date 有类别列 + 数值列 → bar
    - 单行单指标 → metric_card
    - 无法判断 → table
    - 跨域策略禁止展示 → table + warning
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .ir import MergeStatus, MergedResult, ResultSummary


# ═══════════════════════════════════════════════════════════
# ChartSpec —— 图表规格
# ═══════════════════════════════════════════════════════════


@dataclass
class ChartSpec:
    """
    图表规格 —— 纯结构化描述，不含任何前端代码。

    字段说明：
        chart_type: 图表类型 — line / bar / table / metric_card
        title: 图表标题（中文）
        x_field: X 轴字段名（line/bar 时有效）
        y_fields: Y 轴字段名列表（line/bar 时有效）
        series: 数据系列列表，每个系列含 name 和 values
        source: 数据来源说明（表名 / 摘要来源）
        warnings: 生成过程中产生的警告
        data_preview: 数据预览（前 10 行，JSON 可序列化）
    """
    chart_type: str = "table"
    """图表类型：line / bar / table / metric_card"""

    title: str = ""
    """图表标题（中文）"""

    x_field: str = ""
    """X 轴字段名"""

    y_fields: list[str] = field(default_factory=list)
    """Y 轴字段名列表"""

    series: list[dict] = field(default_factory=list)
    """数据系列，每个元素为 {"name": str, "values": list}"""

    source: str = ""
    """数据来源说明（表名或摘要来源）"""

    warnings: list[str] = field(default_factory=list)
    """生成过程中产生的警告"""

    data_preview: list[list] = field(default_factory=list)
    """数据预览（前 10 行，JSON 可序列化）"""

    def to_dict(self) -> dict[str, Any]:
        """序列化为纯 JSON 可序列化字典"""
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "x_field": self.x_field,
            "y_fields": self.y_fields,
            "series": self.series,
            "source": self.source,
            "warnings": self.warnings,
            "data_preview": self.data_preview,
        }

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ═══════════════════════════════════════════════════════════
# 构建函数
# ═══════════════════════════════════════════════════════════


def build_chart_spec_from_summary(
    summary: ResultSummary,
    cross_domain_warning: str | None = None,
) -> ChartSpec:
    """
    从单个 ResultSummary 构建 ChartSpec。

    根据摘要的结构特征自动选择图表类型：
        - 有 date 列 + 数值列 → line
        - 无 date 列 + 有类别列 + 数值列 → bar
        - 单行单指标 → metric_card
        - 无法判断 → table

    Args:
        summary: 单个 ResultSummary
        cross_domain_warning: 跨域策略警告（若传入且含展示禁止语义，降级为 table）

    Returns:
        ChartSpec 实例
    """
    warnings = list(summary.warnings)

    # ── 跨域策略警告注入 ──
    if cross_domain_warning:
        warnings.append(cross_domain_warning)

    # ── 提取列信息 ──
    columns = summary.columns
    sample_rows = summary.sample_rows
    metrics = summary.metrics
    row_count = summary.row_count
    has_date = summary.has_date_column
    primary_table = summary.primary_table

    # ── 空结果 ──
    if row_count == 0 or not columns:
        return ChartSpec(
            chart_type="table",
            title=f"查询结果为空（{', '.join(metrics) if metrics else '无指标'}）",
            source=primary_table,
            warnings=warnings,
        )

    # ── 分类列（非 date、非数值的列）──
    date_cols = _find_date_columns(columns)
    numeric_cols = _find_numeric_columns(columns, sample_rows)
    category_cols = [
        c for c in columns
        if c not in date_cols and c not in numeric_cols
    ]

    # ── 构建标题 ──
    title = _build_title(metrics, primary_table)

    # ── 跨域警告降级 ──
    if cross_domain_warning and ("禁止" in cross_domain_warning or "refusal" in cross_domain_warning.lower()):
        return ChartSpec(
            chart_type="table",
            title=title,
            source=primary_table,
            warnings=warnings,
            data_preview=_serialize_rows(sample_rows),
        )

    # ── 规则 1: metric_card — 单行单指标 ──
    if row_count == 1 and len(numeric_cols) == 1:
        val = _extract_value(sample_rows, 0, columns.index(numeric_cols[0]))
        return ChartSpec(
            chart_type="metric_card",
            title=title,
            y_fields=numeric_cols[:1],
            source=primary_table,
            warnings=warnings,
            data_preview=_serialize_rows(sample_rows),
        )

    # ── 规则 2: line — 有 date 列 ──
    if has_date and date_cols and numeric_cols:
        x_field = date_cols[0]
        return ChartSpec(
            chart_type="line",
            title=title,
            x_field=x_field,
            y_fields=numeric_cols,
            series=_build_series(sample_rows, x_field, numeric_cols, columns),
            source=primary_table,
            warnings=warnings,
            data_preview=_serialize_rows(sample_rows),
        )

    # ── 规则 3: bar — 无 date 但有类别列 + 数值列 ──
    if category_cols and numeric_cols:
        x_field = category_cols[0]
        return ChartSpec(
            chart_type="bar",
            title=title,
            x_field=x_field,
            y_fields=numeric_cols,
            series=_build_series(sample_rows, x_field, numeric_cols, columns),
            source=primary_table,
            warnings=warnings,
            data_preview=_serialize_rows(sample_rows),
        )

    # ── 规则 4: 兜底 — table ──
    return ChartSpec(
        chart_type="table",
        title=title,
        source=primary_table,
        warnings=warnings + (
            ["无法自动判断图表类型，降级为 table"]
            if not warnings or "无法自动判断" not in str(warnings) else []
        ),
        data_preview=_serialize_rows(sample_rows),
    )


def build_chart_spec_from_merged_result(
    merged: MergedResult,
    cross_domain_warning: str | None = None,
) -> ChartSpec:
    """
    从 MergedResult 构建 ChartSpec。

    规则：
        - merge_key=date 且多值列 → line
        - merge_key=date 且单值列 → line（单线图）
        - 其他 → table

    Args:
        merged: MergedResult 实例
        cross_domain_warning: 跨域策略警告（若传入，附加到 warnings）

    Returns:
        ChartSpec 实例
    """
    warnings = list(merged.merge_warnings)

    if cross_domain_warning:
        warnings.append(cross_domain_warning)

    columns = merged.columns
    rows = merged.rows
    row_count = merged.row_count
    merge_key = merged.merge_key
    merge_status = merged.merge_status
    source_summaries = merged.source_summaries

    # ── 构建标题和数据来源 ──
    all_metrics: list[str] = []
    all_tables: list[str] = []
    for s in source_summaries:
        all_metrics.extend(s.metrics)
        if s.primary_table:
            all_tables.append(s.primary_table)

    title = _build_title(all_metrics, None)
    source = ", ".join(all_tables) if all_tables else "多表合并"

    # ── 未合并 → table ──
    if merge_status != MergeStatus.MERGED:
        return ChartSpec(
            chart_type="table",
            title=title,
            source=source,
            warnings=warnings + (
                [f"未执行 date merge: {merged.reason}"]
                if merged.reason else []
            ),
            data_preview=_serialize_rows(rows[:10]),
        )

    # ── 空数据 ──
    if row_count == 0 or not columns:
        return ChartSpec(
            chart_type="table",
            title=f"{title}（空）",
            source=source,
            warnings=warnings,
        )

    # ── 分析列类型 ──
    date_cols = _find_date_columns(columns)
    numeric_cols = _find_numeric_columns(columns, rows)
    other_cols = [
        c for c in columns
        if c not in date_cols and c not in numeric_cols
    ]

    # ── 规则: date merge + 多值列 → line ──
    if merge_key == "date" and date_cols and numeric_cols:
        x_field = date_cols[0]
        return ChartSpec(
            chart_type="line",
            title=title,
            x_field=x_field,
            y_fields=numeric_cols,
            series=_build_series(rows, x_field, numeric_cols, columns),
            source=source,
            warnings=warnings,
            data_preview=_serialize_rows(rows[:10]),
        )

    # ── 有类别列 → bar ──
    if other_cols and numeric_cols:
        x_field = other_cols[0]
        return ChartSpec(
            chart_type="bar",
            title=title,
            x_field=x_field,
            y_fields=numeric_cols,
            series=_build_series(rows, x_field, numeric_cols, columns),
            source=source,
            warnings=warnings,
            data_preview=_serialize_rows(rows[:10]),
        )

    # ── 兜底 → table ──
    return ChartSpec(
        chart_type="table",
        title=title,
        source=source,
        warnings=warnings + ["无法自动判断图表类型，降级为 table"],
        data_preview=_serialize_rows(rows[:10]),
    )


# ═══════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════


def _find_date_columns(columns: list[str]) -> list[str]:
    """从列名列表中找出日期列（按列名匹配）"""
    date_cols: list[str] = []
    for col in columns:
        lower = col.lower()
        if "date" in lower or "time" in lower:
            date_cols.append(col)
    return date_cols


def _find_numeric_columns(
    columns: list[str],
    rows: list[list],
) -> list[str]:
    """
    从列名和数据行中找出数值列。

    策略：
        1. 列名包含数字标识（count、amount、total、avg、sum、num、rate、pct 等）
        2. 回退：检查样本行中该列的值是否为 int/float 类型
    """
    numeric_hints = {
        "count", "amount", "total", "avg", "sum", "num",
        "rate", "pct", "qty", "quantity", "fee", "fare",
        "fine", "mile", "distance", "duration", "price",
        "revenue", "cost", "tax", "tips", "tolls",
    }

    numeric_cols: list[str] = []
    for i, col in enumerate(columns):
        lower = col.lower()
        # 策略 1: 列名包含数值提示词
        if any(hint in lower for hint in numeric_hints):
            numeric_cols.append(col)
            continue
        # 策略 2: 数据行中该列为数值类型
        if _column_has_numeric_values(rows, i):
            numeric_cols.append(col)

    return numeric_cols


def _column_has_numeric_values(rows: list[list], col_idx: int) -> bool:
    """检查某列在样本行中是否包含数值类型"""
    numeric_count = 0
    total = 0
    for row in rows:
        if col_idx >= len(row):
            continue
        val = row[col_idx]
        total += 1
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            numeric_count += 1
    # 至少 50% 的非空值为数值类型
    return total > 0 and numeric_count > 0 and numeric_count / total >= 0.5


def _build_title(metrics: list[str], primary_table: str | None) -> str:
    """根据指标和表名构建中文标题"""
    if not metrics:
        return "数据查询结果"
    # 指标名简单美化
    display_metrics = [m.replace("_", " ") for m in metrics]
    if len(display_metrics) == 1:
        return f"{display_metrics[0]}"
    elif len(display_metrics) <= 3:
        return f"{' / '.join(display_metrics)}"
    else:
        return f"{', '.join(display_metrics[:3])} 等 {len(display_metrics)} 项指标"


def _build_series(
    rows: list[list],
    x_field: str,
    y_fields: list[str],
    columns: list[str],
) -> list[dict]:
    """
    从数据行构建 series 列表。

    Returns:
        [{"name": y_field, "values": [...]}, ...]
        或 line 类型时返回:
        [{"x": [...], "y": [...], "name": y_field}, ...]
    """
    x_idx = columns.index(x_field) if x_field in columns else -1
    series: list[dict] = []

    # 提取 X 轴值
    x_values: list = []
    for row in rows:
        if x_idx >= 0 and x_idx < len(row):
            x_values.append(_serialize_val(row[x_idx]))
        else:
            x_values.append(None)

    for y_field in y_fields:
        y_idx = columns.index(y_field) if y_field in columns else -1
        y_values: list = []
        for row in rows:
            if y_idx >= 0 and y_idx < len(row):
                y_values.append(_serialize_val(row[y_idx]))
            else:
                y_values.append(None)

        series.append({
            "name": y_field,
            "x": list(x_values),
            "y": list(y_values),
        })

    return series


def _extract_value(rows: list[list], row_idx: int, col_idx: int) -> Any:
    """从数据行中提取单个值"""
    if row_idx < len(rows) and col_idx < len(rows[row_idx]):
        return _serialize_val(rows[row_idx][col_idx])
    return None


def _serialize_rows(rows: list[list]) -> list[list]:
    """将数据行序列化为 JSON 可序列化格式"""
    result: list[list] = []
    for row in rows:
        result.append([_serialize_val(v) for v in row])
    return result


def _serialize_val(val: Any) -> Any:
    """将单个值转为 JSON 可序列化格式"""
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        # 日期/时间对象 → ISO 字符串
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        return val
    # datetime/date 对象
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    # 其他类型 → 字符串回退
    return str(val)
