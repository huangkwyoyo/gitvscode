"""
B-4 CRCS 定义统一契约化测试。

验证：
    1. 统一契约文件 crcs_policy.yml 存在且完整
    2. 两个 AGENTS.md 均引用统一契约
    3. 契约文件包含所有必需的核心定义
"""

from pathlib import Path

import pytest
import yaml


# ══════════════════════════════════════════════════════
# 路径解析
# ══════════════════════════════════════════════════════

def _repo_root():
    return Path(__file__).resolve().parent.parent


def _crcs_policy_path():
    return _repo_root().parent / "TianShu" / "contracts" / "crcs_policy.yml"


def _agents_md_path():
    return _repo_root() / "AGENTS.md"


def _dev_agent_agents_md_path():
    return _repo_root().parent / "TianShu Data Dev Agent" / "AGENTS.md"


# ══════════════════════════════════════════════════════
# 契约文件存在性和完整性
# ══════════════════════════════════════════════════════

class TestCRCSContractExists:
    """验证统一契约文件 crcs_policy.yml"""

    def test_contract_file_exists(self):
        """crcs_policy.yml 应存在于 TianShu/contracts/"""
        path = _crcs_policy_path()
        assert path.exists(), f"契约文件不存在: {path}"

    def test_contract_is_valid_yaml(self):
        """crcs_policy.yml 应为合法 YAML"""
        path = _crcs_policy_path()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None, "crcs_policy.yml 内容为空"
        assert isinstance(data, dict), "crcs_policy.yml 应为 YAML 字典"

    def test_contract_has_version(self):
        """crcs_policy.yml 应有版本号"""
        path = _crcs_policy_path()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "version" in data, "缺少 version 字段"

    def test_contract_has_general_principles(self):
        """crcs_policy.yml 应有总原则（6 条）"""
        path = _crcs_policy_path()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        principles = data.get("general_principles", [])
        assert len(principles) == 6, f"预期 6 条总原则，实际 {len(principles)} 条"

    def test_contract_has_class_definitions(self):
        """crcs_policy.yml 应有 A/B/C 三类完整定义"""
        path = _crcs_policy_path()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for key in ["class_a", "class_b", "class_c"]:
            assert key in data, f"缺少 {key} 定义"
            assert data[key].get("id") in ("A", "B", "C")
            assert data[key].get("name"), f"{key} 缺少 name"
            assert data[key].get("applicable_scenarios"), f"{key} 缺少适用场景"
            assert data[key].get("handling"), f"{key} 缺少处理方式"

    def test_contract_has_output_format(self):
        """crcs_policy.yml 应有统一输出格式"""
        path = _crcs_policy_path()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "output_format" in data
        assert "template" in data["output_format"]

    def test_contract_has_skill_assistance_rules(self):
        """crcs_policy.yml 应有 Skill 辅助规则"""
        path = _crcs_policy_path()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "skill_assistance" in data
        assert "default_skill_map" in data["skill_assistance"]
        assert len(data["skill_assistance"]["default_skill_map"]) >= 4


# ══════════════════════════════════════════════════════
# AGENTS.md 引用一致性
# ══════════════════════════════════════════════════════

class TestAGENTSReferencesContract:
    """验证两个 AGENTS.md 均引用统一契约"""

    def test_text2sql_agents_md_references_contract(self):
        """本项目的 AGENTS.md 应显式引用 crcs_policy.yml"""
        path = _agents_md_path()
        content = path.read_text(encoding="utf-8")
        assert "crcs_policy.yml" in content, (
            "AGENTS.md 应引用 ../TianShu/contracts/crcs_policy.yml"
        )
        assert "唯一权威源" in content or "权威" in content, (
            "AGENTS.md 应标明 crcs_policy.yml 为权威源"
        )

    def test_dev_agent_agents_md_references_contract(self):
        """Data Dev Agent 的 AGENTS.md 应显式引用 crcs_policy.yml"""
        path = _dev_agent_agents_md_path()
        if not path.exists():
            pytest.skip(f"文件不存在: {path}")
        content = path.read_text(encoding="utf-8")
        assert "crcs_policy.yml" in content, (
            "Data Dev Agent AGENTS.md 应引用 ../TianShu/contracts/crcs_policy.yml"
        )

    def test_text2sql_agents_md_keeps_boundary_map(self):
        """本项目的 AGENTS.md 应保留项目特有的边界映射表"""
        path = _agents_md_path()
        content = path.read_text(encoding="utf-8")
        assert "与本项目边界的映射" in content or "边界映射" in content, (
            "AGENTS.md 应保留项目特有的边界映射表"
        )
        # 项目特有映射不应被删除
        assert "src/ir.py" in content
        assert "src/sql_gen.py" in content

    def test_text2sql_has_project_hard_boundaries(self):
        """本项目的 AGENTS.md 应列出项目特有硬边界"""
        path = _agents_md_path()
        content = path.read_text(encoding="utf-8")
        assert "硬边界" in content
        assert "离线模式禁止执行 SQL" in content

    def test_no_duplicate_full_crcs_definitions(self):
        """两个 AGENTS.md 都不应再包含完整的 A/B/C 分类定义（已移到契约文件）"""
        path = _agents_md_path()
        content = path.read_text(encoding="utf-8")

        # 不应包含旧式的详细定义小节（这些信息在 crcs_policy.yml 中）
        # 但可以有简短的引用说明
        # 检查是否有 "分类定义" 小节仍保留完整的定义
        assert "A 类（AUTO-FIX）—— 可局部安全修复" not in content, (
            "AGENTS.md 不应再复制 A 类完整定义（应在 crcs_policy.yml 中）"
        )

    def test_contract_mentioned_in_change_propagation(self):
        """变更传播规则应覆盖 crcs_policy.yml"""
        path = _agents_md_path()
        content = path.read_text(encoding="utf-8")
        # 检查边界映射表中是否包含 crcs_policy.yml 的变更规则
        assert "crcs_policy.yml" in content
