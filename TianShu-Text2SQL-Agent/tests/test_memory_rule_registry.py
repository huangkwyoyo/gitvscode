"""Memory Rule Registry 测试 —— Step 5。

测试 memory_rules.yml 的可解析性、校验逻辑、
generate_rule_index.py 的生成功能，以及 proposed/active/blocking 语义。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 被测试模块
from scripts.generate_rule_index import (
    load_rules,
    validate_rules,
    generate_markdown,
    RULES_YAML_PATH,
    VALID_STATUSES,
    REQUIRED_FIELDS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 1: memory_rules.yml 能被解析
# ═══════════════════════════════════════════════════════════════════════════════


class TestYamlParsing:
    """验证 YAML 文件可解析且结构正确"""

    def test_yaml_file_exists(self):
        """YAML 规则文件必须存在"""
        assert RULES_YAML_PATH.exists(), (
            f"规则文件不存在: {RULES_YAML_PATH}"
        )

    def test_yaml_can_be_parsed(self):
        """YAML 文件能成功解析为规则列表"""
        rules = load_rules(RULES_YAML_PATH)
        assert isinstance(rules, list), "规则必须是列表"
        assert len(rules) > 0, "规则列表不能为空"
        assert len(rules) == 22, f"期望 22 条规则（9 条迁移 + 12 条补齐 + 1 条 JSON-P0），实际: {len(rules)}"

    def test_each_rule_is_dict(self):
        """每条规则必须是字典"""
        rules = load_rules(RULES_YAML_PATH)
        for i, rule in enumerate(rules):
            assert isinstance(rule, dict), (
                f"rules[{i}] 必须是字典，得到: {type(rule).__name__}"
            )

    def test_all_required_fields_present(self):
        """每条规则必须包含所有必填字段"""
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule.get("rule_id", "?")
            for field in REQUIRED_FIELDS:
                assert field in rule, (
                    f"{rid} 缺少必填字段: {field}"
                )
                assert rule[field] is not None, (
                    f"{rid} 的 {field} 不能为 null"
                )

    def test_list_fields_are_lists(self):
        """列表类型字段必须是列表"""
        list_fields = ["risk_ids", "applies_to", "required_checks",
                       "required_tests", "required_evals"]
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule.get("rule_id", "?")
            for field in list_fields:
                assert isinstance(rule.get(field), list), (
                    f"{rid} 的 {field} 必须是列表，得到: {type(rule.get(field)).__name__}"
                )

    def test_blocking_is_bool(self):
        """blocking 字段必须是布尔类型"""
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule.get("rule_id", "?")
            assert isinstance(rule.get("blocking"), bool), (
                f"{rid} 的 blocking 必须是布尔，得到: {type(rule.get('blocking')).__name__}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 2: rule_id 唯一
# ═══════════════════════════════════════════════════════════════════════════════


class TestRuleIdUniqueness:
    """验证 rule_id 唯一性"""

    def test_no_duplicate_rule_ids(self):
        """所有 rule_id 必须唯一"""
        rules = load_rules(RULES_YAML_PATH)
        ids = [r["rule_id"] for r in rules]
        duplicates = [i for i in ids if ids.count(i) > 1]
        assert len(set(duplicates)) == 0, (
            f"发现重复 rule_id: {set(duplicates)}"
        )

    def test_validate_rejects_duplicate_ids(self, tmp_path):
        """validate_rules 必须拒绝重复的 rule_id"""
        import yaml

        yaml_content = """
rules:
  - rule_id: TA-R999
    title: "测试规则 A"
    status: proposed
    blocking: false
    severity: low
    source_memory: "test#A"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
  - rule_id: TA-R999
    title: "测试规则 B"
    status: proposed
    blocking: false
    severity: low
    source_memory: "test#B"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
"""
        yaml_path = tmp_path / "duplicate_rules.yml"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        rules = load_rules(yaml_path)
        with pytest.raises(SystemExit, match="重复"):
            validate_rules(rules)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 3: rule_id 使用 TA-R 前缀
# ═══════════════════════════════════════════════════════════════════════════════


class TestRuleIdPrefix:
    """验证 TA-R 前缀"""

    def test_all_rule_ids_have_ta_r_prefix(self):
        """所有 rule_id 必须以 TA-R 开头"""
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule["rule_id"]
            assert rid.startswith("TA-R"), (
                f"rule_id 必须以 'TA-R' 开头: {rid}"
            )

    def test_rule_ids_are_numeric_after_prefix(self):
        """TA-R 后必须是数字"""
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule["rule_id"]
            suffix = rid[4:]  # 去掉 "TA-R"
            assert suffix.isdigit(), (
                f"rule_id 的 '{suffix}' 部分必须是数字: {rid}"
            )

    def test_validate_rejects_non_ta_r_prefix(self, tmp_path):
        """validate_rules 必须拒绝非 TA-R 前缀的 rule_id"""
        import yaml

        yaml_content = """
rules:
  - rule_id: R001
    title: "错误前缀测试"
    status: proposed
    blocking: false
    severity: low
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
"""
        yaml_path = tmp_path / "bad_prefix_rules.yml"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        rules = load_rules(yaml_path)
        with pytest.raises(SystemExit, match="TA-R"):
            validate_rules(rules)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 4: generate_rule_index.py 能生成 Markdown
# ═══════════════════════════════════════════════════════════════════════════════


class TestMarkdownGeneration:
    """验证 Markdown 生成功能"""

    def test_generate_markdown_returns_string(self):
        """generate_markdown 返回非空字符串"""
        rules = load_rules(RULES_YAML_PATH)
        md = generate_markdown(rules)
        assert isinstance(md, str), "必须返回字符串"
        assert len(md) > 500, f"生成的 Markdown 太短: {len(md)} 字符"

    def test_generate_markdown_with_empty_rules(self):
        """空规则列表应能生成有效的 Markdown"""
        md = generate_markdown([])
        assert "# 规则来源索引" in md
        assert "**规则总数**: 0" in md

    def test_generated_md_starts_with_header(self):
        """生成的 Markdown 应以标题开始"""
        rules = load_rules(RULES_YAML_PATH)
        md = generate_markdown(rules)
        assert md.startswith("# 规则来源索引"), (
            f"Markdown 应以 '# 规则来源索引' 开头:\n{md[:100]}"
        )

    def test_generated_md_contains_auto_gen_warning(self):
        """生成的 Markdown 必须包含自动生成警告"""
        rules = load_rules(RULES_YAML_PATH)
        md = generate_markdown(rules)
        assert "自动生成" in md, "Markdown 必须包含「自动生成」警告"
        assert "请勿手动编辑" in md or "请勿手改" in md, (
            "Markdown 必须禁止手动编辑"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 5: 生成的 Markdown 包含核心字段
# ═══════════════════════════════════════════════════════════════════════════════


class TestMarkdownCoreFields:
    """验证生成的 Markdown 包含所有核心字段"""

    @pytest.fixture(scope="class")
    def md_content(self) -> str:
        """加载生成的 Markdown"""
        rules = load_rules(RULES_YAML_PATH)
        return generate_markdown(rules)

    def test_md_contains_all_rule_ids(self, md_content):
        """每个 rule_id 都在 Markdown 中出现"""
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule["rule_id"]
            assert rid in md_content, (
                f"Markdown 中缺少 rule_id: {rid}"
            )

    def test_md_contains_required_column_headers(self, md_content):
        """Markdown 表格必须包含所有核心列"""
        required_cols = [
            "rule_id", "title", "status", "blocking",
            "risk_ids", "applies_to", "required_checks",
            "required_tests", "required_evals",
        ]
        for col in required_cols:
            assert col in md_content, (
                f"Markdown 表格缺少列: {col}"
            )

    def test_md_contains_promotion_criteria(self, md_content):
        """Markdown 必须包含晋升标准"""
        assert "晋升标准" in md_content, "缺少晋升标准章节"
        assert "fast gate" in md_content.lower(), (
            "晋升标准中缺少 fast gate 条件"
        )
        assert "正例" in md_content and "负例" in md_content, (
            "晋升标准中缺少正例/负例覆盖条件"
        )

    def test_md_contains_coverage_gaps(self, md_content):
        """Markdown 必须包含覆盖缺口章节"""
        assert "覆盖缺口" in md_content, "缺少覆盖缺口章节"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 6: proposed 规则不会被当作 blocking active 规则
# ═══════════════════════════════════════════════════════════════════════════════


class TestProposedNotBlocking:
    """验证 proposed/active/blocking 语义正确"""

    def test_all_rules_are_proposed_not_active(self):
        """除已晋升的 TA-R018/TA-R019/TA-R020/TA-R023 外，其余规则必须为 proposed"""
        rules = load_rules(RULES_YAML_PATH)
        active_rules = {"TA-R018", "TA-R019", "TA-R020", "TA-R023"}  # Step 8b/26/26b/26c 已晋升为 active
        for rule in rules:
            rid = rule["rule_id"]
            if rid in active_rules:
                assert rule["status"] == "active", (
                    f"{rid}: 已晋升规则应为 active，实际: {rule['status']}"
                )
            else:
                assert rule["status"] == "proposed", (
                    f"{rid}: 未晋升规则应为 proposed，实际: {rule['status']}"
                )

    def test_no_rule_is_blocking(self):
        """除已晋升的 TA-R018/TA-R019/TA-R020/TA-R023 外，其余规则 blocking 必须为 false"""
        rules = load_rules(RULES_YAML_PATH)
        blocking_rules = {"TA-R018", "TA-R019", "TA-R020", "TA-R023"}  # Step 8b/26/26b/26c 已晋升为 blocking=true
        for rule in rules:
            rid = rule["rule_id"]
            if rid in blocking_rules:
                assert rule["blocking"] is True, (
                    f"{rid}: 已晋升规则 blocking 应为 true，实际: {rule['blocking']}"
                )
            else:
                assert rule["blocking"] is False, (
                    f"{rid}: 未晋升规则 blocking 应为 false，实际: {rule['blocking']}"
                )

    def test_proposed_with_blocking_true_warns(self, tmp_path):
        """proposed + blocking=true 应产生警告"""
        import yaml

        yaml_content = """
rules:
  - rule_id: TA-R900
    title: "测试 proposed+blocking"
    status: proposed
    blocking: true
    severity: high
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
"""
        yaml_file = tmp_path / "proposed_blocking.yml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        rules = load_rules(yaml_file)
        warnings = validate_rules(rules)
        assert len(warnings) >= 1, (
            "proposed + blocking=true 必须产生警告"
        )
        assert any("blocking=true" in w for w in warnings), (
            f"警告应提及 blocking=true: {warnings}"
        )

    def test_active_with_blocking_true_info(self, tmp_path):
        """active + blocking=true 应产生提示信息"""
        import yaml

        yaml_content = """
rules:
  - rule_id: TA-R901
    title: "测试 active+blocking"
    status: active
    blocking: true
    severity: high
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
"""
        yaml_file = tmp_path / "active_blocking.yml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        rules = load_rules(yaml_file)
        warnings = validate_rules(rules)
        assert len(warnings) >= 1, (
            "active + blocking=true 必须产生提示"
        )

    def test_status_valid_values(self):
        """所有规则的 status 必须在合法值范围内"""
        rules = load_rules(RULES_YAML_PATH)
        for rule in rules:
            rid = rule["rule_id"]
            assert rule["status"] in VALID_STATUSES, (
                f"{rid}: status 值非法 '{rule['status']}'，"
                f"合法值: {sorted(VALID_STATUSES)}"
            )

    def test_validate_rejects_invalid_status(self, tmp_path):
        """validate_rules 必须拒绝非法 status 值"""
        import yaml

        yaml_content = """
rules:
  - rule_id: TA-R902
    title: "非法 status 测试"
    status: invalid_status
    blocking: false
    severity: low
    source_memory: "test"
    risk_ids: []
    applies_to: []
    required_checks: []
    required_tests: []
    required_evals: []
    notes: ""
"""
        yaml_path = tmp_path / "invalid_status.yml"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        rules = load_rules(yaml_path)
        with pytest.raises(SystemExit, match="非法"):
            validate_rules(rules)


# ═══════════════════════════════════════════════════════════════════════════════
# 测试 7: 端到端 —— 脚本命令行
# ═══════════════════════════════════════════════════════════════════════════════


class TestScriptEndToEnd:
    """验证脚本命令行接口"""

    def test_check_only_mode(self):
        """--check-only 模式应正常退出"""
        import subprocess

        result = subprocess.run(
            [sys.executable, "scripts/generate_rule_index.py", "--check-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0, (
            f"--check-only 应返回 0:\nstderr:\n{result.stderr}"
        )
        assert "仅校验模式" in result.stdout, (
            f"应提及仅校验模式:\n{result.stdout}"
        )

    def test_full_generation_succeeds(self):
        """完整生成流程应正常退出"""
        import subprocess

        result = subprocess.run(
            [sys.executable, "scripts/generate_rule_index.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0, (
            f"生成脚本应返回 0:\nstderr:\n{result.stderr}"
        )
        assert "完成" in result.stdout, (
            f"应输出完成信息:\n{result.stdout}"
        )

    def test_generated_md_file_exists(self):
        """运行脚本后输出文件必须存在"""
        output_path = PROJECT_ROOT / "docs" / "memory" / "规则来源索引.md"
        assert output_path.exists(), (
            f"输出文件不存在: {output_path}"
        )

    def test_generated_md_is_valid_utf8(self):
        """生成的 Markdown 文件必须是合法 UTF-8"""
        output_path = PROJECT_ROOT / "docs" / "memory" / "规则来源索引.md"
        with open(output_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        # 尝试编码回 UTF-8 验证无非法字节
        try:
            content.encode("utf-8")
        except UnicodeEncodeError as exc:
            pytest.fail(f"Markdown 文件包含非法 UTF-8 序列: {exc}")
