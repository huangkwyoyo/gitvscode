#!/usr/bin/env python3
"""
Data Dev Agent 管道自检脚本

检查项：
  1. Python 依赖可用性（duckdb, pandas, pyarrow, pyyaml）
  2. TianShu DuckDB 文件存在且可读
  3. ColumnBindingTable 完整性（10个指标 + 维度绑定）
  4. 合约文件完整性（4个 YAML 契约）
  5. Fixture 文件完整性（3个示例需求）
  6. 目录结构完整性

用法：
  python scripts/quality/check_pipeline.py
  python scripts/quality/check_pipeline.py --verbose
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def check_python_deps() -> tuple[bool, list[str]]:
    """检查 Python 依赖"""
    missing: list[str] = []
    for lib in ["duckdb", "pandas", "pyarrow", "yaml"]:
        try:
            if lib == "yaml":
                import yaml
            else:
                __import__(lib)
        except ImportError:
            missing.append(lib)
    return len(missing) == 0, missing


def check_duckdb_accessible(config: dict) -> tuple[bool, str]:
    """检查 DuckDB 文件是否可访问（只读尝试）"""
    duckdb_path = config.get("tianShu", {}).get("duckdb_path", "")
    if not duckdb_path or not Path(duckdb_path).exists():
        return False, f"DuckDB 文件不存在: {duckdb_path}"
    try:
        import duckdb
        conn = duckdb.connect(duckdb_path, read_only=True)
        conn.execute("SELECT 1")
        conn.close()
        return True, duckdb_path
    except Exception as e:
        return False, f"无法连接 DuckDB ({duckdb_path}): {e}"


def check_column_binding_completeness() -> tuple[bool, list[str]]:
    """检查 ColumnBindingTable 中是否覆盖了所有 10 个已注册指标"""
    from scripts.pipeline.column_binding import METRIC_BINDINGS, DIMENSION_BINDINGS

    metrics = [e.metric_name for e in METRIC_BINDINGS]
    expected_count = 10  # 来自 metric_contract.yml 的 10 个指标

    issues: list[str] = []

    if len(metrics) != expected_count:
        issues.append(
            f"指标数量: {len(metrics)}（预期 {expected_count}）"
        )

    # 检查每个指标的必填字段
    for binding in METRIC_BINDINGS:
        if binding.g3_available and binding.g3 is None:
            issues.append(f"指标 '{binding.metric_name}' 标记 g3_available=True 但 g3 列为 None")
        if not binding.g3_available and binding.g2_expression is None:
            issues.append(f"指标 '{binding.metric_name}' 无 G3 且无 G2 表达式")

    # 检查维度绑定
    if len(DIMENSION_BINDINGS) < 1:
        issues.append("维度绑定表为空（至少需要 'date' 维度）")

    return len(issues) == 0, issues


def check_contracts() -> tuple[bool, list[str]]:
    """检查合约文件完整性"""
    contracts_dir = PROJECT_ROOT / "contracts"
    required = [
        "requirement_schema.yml",
        "sqlplan_schema.yml",
        "result_schema.yml",
        "validation_schema.yml",
    ]
    missing = [f for f in required if not (contracts_dir / f).exists()]
    return len(missing) == 0, missing


def check_fixtures() -> tuple[bool, list[str]]:
    """检查 fixture 文件完整性"""
    fixtures_dir = PROJECT_ROOT / "fixtures" / "requirements"
    # 3 个预置需求
    if not fixtures_dir.exists():
        return False, ["fixtures/requirements/ 目录不存在"]

    yml_files = list(fixtures_dir.glob("*.yml"))
    if len(yml_files) < 3:
        return False, [f"需求 fixture 数量不足: {len(yml_files)}，预期至少 3"]

    return True, [str(f.relative_to(PROJECT_ROOT)) for f in yml_files]


def check_directory_structure() -> tuple[bool, list[str]]:
    """检查目录结构完整性"""
    required_dirs = [
        "contracts",
        "fixtures/requirements",
        "evals",
        "harness/config",
        "harness/reports",
        "scripts/pipeline",
        "scripts/quality",
        "generated/results",
        "generated/reports",
        "generated/tasks",
        "tests",
    ]
    missing = [d for d in required_dirs if not (PROJECT_ROOT / d).exists()]
    return len(missing) == 0, missing


# ═══════════════════════════════════════════════════════════
# P2 扩展检查——覆盖 G2 降级安全、JOIN 白名单、合约结构、SQL 编译
# ═══════════════════════════════════════════════════════════


def check_g2_dim_date_coverage() -> tuple[bool, list[str]]:
    """
    检查所有 G2 事实表是否都有到 gold.dim_date 的白名单 JOIN 路径

    P0-1 安全门禁：G2 层日期过滤必须通过 dim_date。如果某个 G2 fact 表
    在白名单中缺少 dim_date JOIN 路径，则 G2 降级不可用——这是安全硬限制。
    """
    from scripts.pipeline.column_binding import METRIC_BINDINGS, JOIN_WHITELIST

    issues: list[str] = []

    # 收集所有 G2 事实表（排除维表——dim_* 表不需要自身 JOIN dim_date）
    g2_tables: set[str] = set()
    for entry in METRIC_BINDINGS:
        if entry.g2_table and not entry.g2_table.startswith("gold.dim_"):
            g2_tables.add(entry.g2_table)

    # 检查每个 G2 表是否有到 dim_date 的 JOIN 路径
    for g2_table in sorted(g2_tables):
        has_dim_date = False
        for path in JOIN_WHITELIST:
            if ((path.left_table == g2_table and path.right_table == "gold.dim_date") or
                    (path.right_table == g2_table and path.left_table == "gold.dim_date")):
                has_dim_date = True
                break

        if not has_dim_date:
            issues.append(
                f"G2 表 '{g2_table}' 在白名单中无到 gold.dim_date 的 JOIN 路径"
            )

    return len(issues) == 0, issues


def check_join_whitelist_integrity() -> tuple[bool, list[str]]:
    """
    检查 JOIN 白名单完整性：双向 key 匹配、无重复路径、方向一致性

    P0-2 安全门禁：跨域 JOIN 的 left_key/right_key 必须匹配正确的表方向。
    """
    from scripts.pipeline.column_binding import JOIN_WHITELIST

    issues: list[str] = []

    seen_pairs: set[tuple[str, str]] = set()
    for path in JOIN_WHITELIST:
        # 检查必填字段
        if not path.left_table or not path.right_table:
            issues.append(f"JOIN 路径缺少 left_table 或 right_table: {path.constraint_ref}")
        if not path.left_key or not path.right_key:
            issues.append(f"JOIN 路径 '{path.left_table} ↔ {path.right_table}' 缺少 JOIN key")

        # 检查重复路径
        pair = tuple(sorted([path.left_table, path.right_table]))
        if pair in seen_pairs:
            issues.append(f"JOIN 路径重复: {path.left_table} ↔ {path.right_table}")
        seen_pairs.add(pair)

        # 检查自引用
        if path.left_table == path.right_table:
            issues.append(f"JOIN 路径自引用: {path.left_table} ↔ {path.right_table}")

    return len(issues) == 0, issues


def check_contract_structure() -> tuple[bool, list[str]]:
    """
    检查合约文件的结构有效性（不仅是文件存在）

    验证 YAML 可解析且包含最小必需字段。
    """
    import yaml

    contracts_dir = PROJECT_ROOT / "contracts"
    issues: list[str] = []

    # 每个合约的最小必需顶层 key（匹配实际合约文件结构）
    contract_requirements = {
        "requirement_schema.yml": ["metrics", "dimensions", "filters"],
        "sqlplan_schema.yml": ["sqlplan"],
        "result_schema.yml": ["result"],
        "validation_schema.yml": ["sql_validation"],
    }

    for filename, required_keys in contract_requirements.items():
        filepath = contracts_dir / filename
        if not filepath.exists():
            issues.append(f"合约文件缺失: {filename}")
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append(f"合约文件 '{filename}' YAML 解析失败: {e}")
            continue

        if content is None:
            issues.append(f"合约文件 '{filename}' 内容为空")
            continue

        for key in required_keys:
            if key not in content:
                issues.append(f"合约文件 '{filename}' 缺少必需字段: '{key}'")

    return len(issues) == 0, issues


def check_sql_compilation_integrity() -> tuple[bool, list[str]]:
    """
    检查 SQL 编译器基本可用性——对所有 fixture 需求执行 dry-run 编译

    验证：需求→Intent→SQLPlan→SQL 编译链路不崩溃，SQL 包含基本结构。
    """
    import yaml
    from pathlib import Path

    try:
        from scripts.pipeline.layer1_requirement import parse_requirement
        from scripts.pipeline.layer2_intent import build_intent
        from scripts.pipeline.layer3_plan import construct_sqlplan
        from scripts.pipeline.layer4_generate import compile_sql
    except ImportError as e:
        return False, [f"编译器模块导入失败: {e}"]

    fixtures_dir = PROJECT_ROOT / "fixtures" / "requirements"
    issues: list[str] = []

    for yml_file in sorted(fixtures_dir.glob("*.yml")):
        try:
            # Layer 1
            requirement = parse_requirement(str(yml_file))
            if not requirement.is_valid:
                issues.append(f"'{yml_file.name}': 需求解析失败")
                continue

            # Layer 2
            intent = build_intent(requirement)
            if not intent.is_valid:
                issues.append(f"'{yml_file.name}': 意图解析失败 — {intent.block_reason}")
                continue

            # Layer 3
            sqlplan = construct_sqlplan(intent)
            if not sqlplan.is_valid:
                issues.append(f"'{yml_file.name}': SQLPlan 构造失败 — {sqlplan.block_reason}")
                continue

            # Layer 4
            try:
                sql_text, sql_params = compile_sql(sqlplan)
            except Exception as e:
                issues.append(f"'{yml_file.name}': SQL 编译异常 — {e}")
                continue

            # 基本 SQL 结构检查
            sql_upper = sql_text.upper()
            if "SELECT" not in sql_upper:
                issues.append(f"'{yml_file.name}': 编译 SQL 缺少 SELECT")
            if "FROM" not in sql_upper:
                issues.append(f"'{yml_file.name}': 编译 SQL 缺少 FROM")

        except Exception as e:
            issues.append(f"'{yml_file.name}': 管道执行异常 — {type(e).__name__}: {e}")

    return len(issues) == 0, issues


def check_column_binding_load_status() -> tuple[bool, list[str]]:
    """
    P1-1 补充：检查事实源加载状态，诊断漂移风险

    如果 TianShu 加载未尝试或回退到静态绑定，管道可能使用过时的指标定义。
    """
    from scripts.pipeline.column_binding import get_load_status

    status = get_load_status()
    source = status["source"]
    attempted = status["attempted"]
    metric_count = status["metric_count"]

    if source == "not_attempted":
        # quality check 独立运行时不会触发 TianShu 加载——这是正常的
        return True, [
            f"事实源加载未尝试（{metric_count} 个静态指标可用）。"
            f"运行 run_pipeline.py 时会自动从 TianShu 加载已审批指标。"
        ]
    elif source == "static_fallback":
        return False, [
            f"事实源加载回退到静态硬编码——TianShu 加载失败或返回空数据。"
            f"当前使用 {metric_count} 个静态指标，可能已过时。"
        ]
    elif source == "tianShu":
        return True, [f"事实源来自 TianShu——已加载 {metric_count} 个已审批指标"]
    else:
        return False, [f"未知加载状态: {source}"]


def main():
    verbose = "--verbose" in sys.argv

    print("=" * 60)
    print("Data Dev Agent 管道自检")
    print("=" * 60)

    all_passed = True

    # 1. Python 依赖
    ok, details = check_python_deps()
    _print_result("Python 依赖", ok, details, verbose)
    all_passed = all_passed and ok

    # 2. 配置加载
    import yaml
    config_path = PROJECT_ROOT / "harness" / "config" / "agent_targets.yml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        _print_result("配置加载", True, str(config_path), verbose)
    except Exception as e:
        _print_result("配置加载", False, str(e), verbose)
        all_passed = False
        config = {}

    # 3. DuckDB 可访问
    if config:
        ok, detail = check_duckdb_accessible(config)
        _print_result("DuckDB 连接", ok, detail, verbose)
    else:
        _print_result("DuckDB 连接", False, "配置未加载，跳过", verbose)

    # 4. ColumnBindingTable 完整性
    ok, details = check_column_binding_completeness()
    _print_result("ColumnBinding", ok, details, verbose)
    all_passed = all_passed and ok

    # 5. 合约文件
    ok, details = check_contracts()
    _print_result("合约文件", ok, details, verbose)
    all_passed = all_passed and ok

    # 6. Fixture 文件
    ok, details = check_fixtures()
    _print_result("Fixture 文件", ok, details, verbose)
    all_passed = all_passed and ok

    # 7. 目录结构
    ok, details = check_directory_structure()
    _print_result("目录结构", ok, details, verbose)
    all_passed = all_passed and ok

    # ── P2 扩展检查 ──
    # 8. G2 dim_date JOIN 覆盖（P0-1 安全门禁）
    ok, details = check_g2_dim_date_coverage()
    _print_result("G2 dim_date 覆盖", ok, details, verbose)
    all_passed = all_passed and ok

    # 9. JOIN 白名单完整性（P0-2 安全门禁）
    ok, details = check_join_whitelist_integrity()
    _print_result("JOIN 白名单完整性", ok, details, verbose)
    all_passed = all_passed and ok

    # 10. 合约结构有效性
    ok, details = check_contract_structure()
    _print_result("合约结构验证", ok, details, verbose)
    all_passed = all_passed and ok

    # 11. SQL 编译完整性（dry-run 全链路）
    ok, details = check_sql_compilation_integrity()
    _print_result("SQL 编译完整性", ok, details, verbose)
    all_passed = all_passed and ok

    # 12. ColumnBinding 加载状态（P1-1 漂移诊断）
    ok, details = check_column_binding_load_status()
    _print_result("事实源加载状态", ok, details, verbose)
    all_passed = all_passed and ok

    # 总结
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] 所有检查通过")
    else:
        print("[FAIL] 存在未通过的检查")
    print("=" * 60)

    return 0 if all_passed else 1


def _print_result(name: str, ok: bool, detail, verbose: bool):
    icon = "[OK]" if ok else "[FAIL]"
    print(f"  {icon} {name}")
    if verbose or not ok:
        if isinstance(detail, list):
            for d in detail:
                print(f"      {'  ->' if ok else '  !'} {d}")
        else:
            print(f"      {'  ->' if ok else '  !'} {detail}")


if __name__ == "__main__":
    sys.exit(main())
