"""
检查 Silver 层高缺失字段和异常占位值。

支持预期稀疏基线：通过 --baseline 参数传入 YAML 文件，
声明每个字段的预期 NULL 率。字段实际 NULL 率超出基线 10% 时标记为"超出预期"。

用法：
    python scripts/quality/check_silver_null.py
    python scripts/quality/check_silver_null.py --baseline harness/config/silver_sparsity_baseline.yml
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import yaml


DEFAULT_DB_PATH = Path(r"D:\ProgramData\Datawarehouse\纽约市城市交通\nyc_transport.duckdb")
BASELINE_MARGIN = 0.10  # 超出基线 10 个百分点视为异常


def quote_ident(name: str) -> str:
    """生成 DuckDB 标识符，避免字段名包含特殊字符时 SQL 失败"""
    return '"' + name.replace('"', '""') + '"'


def resolve_db_path(raw_path: str | None) -> Path:
    """优先使用显式路径，其次使用项目约定路径"""
    if raw_path:
        return Path(raw_path)
    return DEFAULT_DB_PATH


def load_baseline(path: Path | None) -> dict[str, float]:
    """从 YAML 文件加载预期稀疏基线，返回 {table.column: expected_null_rate}"""
    if not path or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    baselines: dict[str, float] = {}
    for entry in data.get("baselines", []):
        key = entry.get("field", "")
        rate = entry.get("expected_null_rate")
        if key and isinstance(rate, (int, float)):
            baselines[key] = float(rate)
    return baselines


def load_silver_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """读取 Silver 层表清单"""
    rows = con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'silver'
        ORDER BY table_name
        """
    ).fetchall()
    return [row[0] for row in rows]


def load_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[tuple[str, str]]:
    """读取指定 Silver 表字段清单"""
    return con.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()


def analyze_table(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    null_threshold: float,
    baseline: dict[str, float],
) -> tuple[list[tuple[str, str, list[str], str]], int]:
    """
    聚合检查单表字段缺失率和异常占位值。

    返回 (issues, row_count)，每条 issue 含 (column_name, data_type, markers, severity)。
    severity: 'unexpected' | 'expected_sparse' | 'warning'
    """
    columns = load_columns(con, table_name)
    expressions = ["count(*) AS row_count"]
    aliases: list[tuple[str, str, str, str, str]] = []

    for column_name, data_type in columns:
        col = quote_ident(column_name)
        null_alias = f"{column_name}__nulls"
        empty_array_alias = f"{column_name}__empty_array"
        empty_string_alias = f"{column_name}__empty_string"
        expressions.append(f"sum(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS {quote_ident(null_alias)}")
        expressions.append(
            f"sum(CASE WHEN CAST({col} AS VARCHAR) = '[]' THEN 1 ELSE 0 END) AS {quote_ident(empty_array_alias)}"
        )
        expressions.append(
            f"sum(CASE WHEN CAST({col} AS VARCHAR) = '' THEN 1 ELSE 0 END) AS {quote_ident(empty_string_alias)}"
        )
        aliases.append((column_name, data_type, null_alias, empty_array_alias, empty_string_alias))

    sql = f"SELECT {', '.join(expressions)} FROM silver.{quote_ident(table_name)}"
    row = con.execute(sql).fetchone()
    result = dict(zip([item[0] for item in con.description], row))
    row_count = result["row_count"] or 0

    issues: list[tuple[str, str, list[str], str]] = []
    for column_name, data_type, null_alias, array_alias, string_alias in aliases:
        null_count = result[null_alias] or 0
        empty_array_count = result[array_alias] or 0
        empty_string_count = result[string_alias] or 0

        if row_count == 0:
            continue

        null_rate = null_count / row_count
        markers: list[str] = []
        severity = "warning"  # 默认：需关注

        # 全 NULL：先检查基线中是否预期为 100%
        if null_count == row_count:
            baseline_key = f"{table_name}.{column_name}"
            expected_rate = baseline.get(baseline_key)
            if expected_rate is not None and expected_rate >= 0.99:
                markers.append(f"全 NULL（预期 {expected_rate:.0%}，在容忍范围内）")
                severity = "expected_sparse"
            else:
                markers.append("全 NULL")
                severity = "unexpected"
        elif null_rate >= null_threshold:
            baseline_key = f"{table_name}.{column_name}"
            expected_rate = baseline.get(baseline_key)

            if expected_rate is not None:
                # 有基线：比较实际值和预期值
                if null_rate <= expected_rate + BASELINE_MARGIN:
                    markers.append(f"NULL 占比 {null_rate:.1%}（预期 {expected_rate:.0%}，在容忍范围内）")
                    severity = "expected_sparse"
                else:
                    markers.append(f"NULL 占比 {null_rate:.1%}（超出预期基线 {expected_rate:.0%}）")
                    severity = "unexpected"
            else:
                # 无基线：按通用阈值报告
                markers.append(f"NULL 占比 {null_rate:.1%}（无预期基线，需人工判断）")
                severity = "warning"

        # 字面量 [] 检查
        if row_count and empty_array_count == row_count:
            markers.append("全为字面量 []")
            severity = "unexpected"
        elif empty_array_count:
            markers.append(f"字面量 [] 数量 {empty_array_count:,}")
            severity = "unexpected"

        # 全空字符串检查
        if row_count and empty_string_count == row_count:
            markers.append("全为空字符串")
            severity = "unexpected"
        elif row_count and empty_string_count / row_count >= null_threshold:
            markers.append(f"空字符串占比 {empty_string_count / row_count:.1%}")
            severity = max(severity, "warning")  # type: ignore[assignment]

        if markers:
            issues.append((column_name, data_type, markers, severity))

    return issues, row_count


def main() -> int:
    """运行 Silver 缺失率检查"""
    parser = argparse.ArgumentParser(description="检查 Silver 层高缺失字段和异常占位值")
    parser.add_argument("--db", default=None, help="DuckDB 文件路径")
    parser.add_argument("--null-threshold", type=float, default=0.5, help="缺失率提示阈值，默认 0.5")
    parser.add_argument("--baseline", default=None, help="预期稀疏基线 YAML 文件路径")
    args = parser.parse_args()

    db_path = resolve_db_path(args.db)
    if not db_path.exists():
        print(f"[FAIL] DuckDB 文件不存在: {db_path}")
        return 1

    baseline_path = Path(args.baseline) if args.baseline else None
    baseline = load_baseline(baseline_path)
    if baseline:
        print(f"已加载 {len(baseline)} 条预期稀疏基线")

    total_issues = 0
    unexpected_count = 0
    sparse_count = 0
    warning_count = 0

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = load_silver_tables(con)
        print(f"Silver 表数量: {len(tables)}")
        for table_name in tables:
            row_count = con.execute(
                f"SELECT count(*) FROM silver.{quote_ident(table_name)}"
            ).fetchone()[0]
            issues, _ = analyze_table(con, table_name, args.null_threshold, baseline)

            print(f"\n--- silver.{table_name}，行数 {row_count:,} ---")
            if not issues:
                print("未发现高缺失率或 [] 占位值字段")
                continue

            for column_name, data_type, markers, severity in issues:
                prefix = {"unexpected": "[!]", "warning": "[?]", "expected_sparse": "[~]"}.get(severity, "  ")
                print(f"{prefix} {column_name} ({data_type}): {'；'.join(markers)}")
                if severity == "unexpected":
                    unexpected_count += 1
                elif severity == "expected_sparse":
                    sparse_count += 1
                else:
                    warning_count += 1
            total_issues += len(issues)
    finally:
        con.close()

    print(f"\n检查完成，共 {total_issues} 个需关注字段。")
    print(f"  [!] 超出预期/全NULL: {unexpected_count}")
    print(f"  [~] 预期稀疏（在容忍范围内）: {sparse_count}")
    print(f"  [?] 无基线需人工判断: {warning_count}")
    return 0 if unexpected_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
