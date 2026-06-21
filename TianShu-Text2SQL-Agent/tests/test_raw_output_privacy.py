"""raw_output 失败记录的隐私安全测试。

验证：
- 默认不保存问题原文
- 文件名不含问题文本
- PII 正确脱敏（手机号、邮箱、身份证、车牌、API Key）
- 写入失败不影响主查询
- opt-in 仅允许脱敏问题
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent import Text2SQLAgent


class TestSafeQuestionId:
    """_safe_question_id 文件名安全性。"""

    def test_filename_contains_no_question_text(self):
        """文件名不应包含问题文本片段。"""
        q = "2026年1月曼哈顿每天有多少行程？"
        qid = Text2SQLAgent._safe_question_id(q)

        # 仅应包含 q_ 前缀 + 16 位 hex
        assert qid.startswith("q_")
        assert len(qid) == 2 + 16  # q_ + 16 hex chars
        # 不应包含问题中的任何中文字符
        for ch in "曼哈顿行程":
            assert ch not in qid

    def test_same_question_produces_same_id(self):
        """同一问题应产生相同 ID。"""
        q = "测试问题"
        assert Text2SQLAgent._safe_question_id(q) == Text2SQLAgent._safe_question_id(q)

    def test_different_questions_produce_different_ids(self):
        """不同问题应产生不同 ID。"""
        q1 = "2026年1月行程"
        q2 = "2026年2月行程"
        assert Text2SQLAgent._safe_question_id(q1) != Text2SQLAgent._safe_question_id(q2)


class TestRedactPII:
    """_redact_pii 脱敏覆盖。"""

    def test_phone_number_redacted(self):
        """中国大陆手机号应被脱敏。"""
        text = "请联系 13812345678 获取详情"
        result = Text2SQLAgent._redact_pii(text)
        assert "13812345678" not in result
        assert "[手机号]" in result

    def test_email_redacted(self):
        """邮箱地址应被脱敏。"""
        text = "发送至 user@example.com 或 admin@test.org"
        result = Text2SQLAgent._redact_pii(text)
        assert "user@example.com" not in result
        assert "admin@test.org" not in result
        assert "[邮箱]" in result

    def test_chinese_id_number_redacted(self):
        """18 位身份证号应被脱敏。"""
        text = "身份证 110101199001011234 需要验证"
        result = Text2SQLAgent._redact_pii(text)
        assert "110101199001011234" not in result
        assert "[身份证号]" in result

    def test_license_plate_redacted(self):
        """车牌号应被脱敏。"""
        text = "车辆 京A12345 和 沪B67890 均违规"
        result = Text2SQLAgent._redact_pii(text)
        assert "京A12345" not in result
        assert "沪B67890" not in result
        assert "[车牌号]" in result

    def test_api_key_redacted(self):
        """OpenAI 格式 API Key 应被脱敏。"""
        text = "使用 sk-abc123def456ghi789jkl 调用"
        result = Text2SQLAgent._redact_pii(text)
        assert "sk-abc123def456xyz789" not in result
        assert "[API_KEY]" in result

    def test_plain_text_unchanged(self):
        """不含 PII 的普通文本应保持不变。"""
        text = "2026年1月每天有多少行程？"
        result = Text2SQLAgent._redact_pii(text)
        assert result == text

    def test_empty_string(self):
        """空字符串应返回空字符串。"""
        assert Text2SQLAgent._redact_pii("") == ""
        assert Text2SQLAgent._redact_pii(None) == ""


class TestRedactSensitiveText:
    """_redact_sensitive_text 综合脱敏。"""

    def test_authorization_header_redacted(self):
        """Authorization header 应被脱敏。"""
        text = "Authorization: Bearer abc123xyz"
        result = Text2SQLAgent._redact_sensitive_text(text)
        assert "abc123xyz" not in result
        assert "[已脱敏]" in result


class TestRedactSensitiveData:
    """_redact_sensitive_data 递归脱敏。"""

    def test_dict_recursive_redaction(self):
        """字典中所有字符串值应被递归脱敏。"""
        data = {
            "user": "test@example.com",
            "nested": {"phone": "13912345678"},
            "list": ["sk-abc123def456", "normal text"],
        }
        result = Text2SQLAgent._redact_sensitive_data(data)
        assert "test@example.com" not in str(result)
        assert "13912345678" not in str(result)
        assert "sk-abc123" not in str(result)
        assert "normal text" in str(result)

    def test_list_recursive_redaction(self):
        """列表中所有元素应被递归脱敏。"""
        data = ["13800001111", "user@test.com"]
        result = Text2SQLAgent._redact_sensitive_data(data)
        for item in result:
            assert "13800001111" not in item
            assert "user@test.com" not in item


class TestSaveRawOutputDefaultPrivacy:
    """默认模式下的隐私保护（include_question: never）。"""

    @pytest.fixture
    def agent(self):
        """创建启用 raw_output 的 Agent 实例。"""
        with patch("src.agent.TianShuResolver"), patch("src.agent.AgentContext"):
            agent = Text2SQLAgent.__new__(Text2SQLAgent)
            agent._raw_output_enabled = True
            agent._agent_config = {"raw_output": {"enabled": True}}
            with tempfile.TemporaryDirectory() as tmpdir:
                agent._raw_output_dir = Path(tmpdir)
                agent._last_intent_raw = ""
                agent._last_plan_raw = ""
                yield agent

    def test_default_does_not_save_full_question(self, agent):
        """默认模式下不应保存完整问题文本。"""
        question = "用户张三的手机号13812345678，2026年1月行程"
        path = agent._save_raw_output_on_failure(
            question=question,
            stage="intent",
            prompt_name="intent_classifier",
            raw_output='{"test": true}',
            parsed_output={},
            parse_success=False,
            validation_success=False,
            error_message="测试错误",
        )
        assert path is not None
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        # question 字段应是字典（结构特征），不是字符串
        assert isinstance(saved["question"], dict)
        assert "length" in saved["question"]
        assert saved["question"]["length"] == len(question)
        # 不应包含原文内容
        assert "张三" not in str(saved["question"])
        assert "13812345678" not in str(saved["question"])

    def test_filename_does_not_contain_question_text(self, agent):
        """文件名不应包含问题文本。"""
        question = "2026年1月曼哈顿行程"
        path = agent._save_raw_output_on_failure(
            question=question,
            stage="intent",
            prompt_name="intent_classifier",
            raw_output="{}",
            parsed_output={},
            parse_success=False,
            validation_success=False,
            error_message=None,
        )
        filename = Path(path).name
        assert "曼哈顿" not in filename
        assert filename.startswith("q_")

    def test_write_failure_does_not_raise(self, agent):
        """写入失败不应抛出异常（不影响主查询）。"""
        with patch("pathlib.Path.write_text", side_effect=OSError("模拟磁盘错误")):
            result = agent._save_raw_output_on_failure(
                question="测试",
                stage="intent",
                prompt_name="test",
                raw_output="{}",
                parsed_output={},
                parse_success=False,
                validation_success=False,
                error_message=None,
            )
        assert result is None  # 失败时返回 None


class TestSaveRawOutputRedactedOptin:
    """显式 opt-in 模式（include_question: redacted）。"""

    @pytest.fixture
    def agent(self):
        with patch("src.agent.TianShuResolver"), patch("src.agent.AgentContext"):
            agent = Text2SQLAgent.__new__(Text2SQLAgent)
            agent._raw_output_enabled = True
            agent._agent_config = {
                "raw_output": {"enabled": True, "include_question": "redacted"}
            }
            with tempfile.TemporaryDirectory() as tmpdir:
                agent._raw_output_dir = Path(tmpdir)
                yield agent

    def test_redacted_mode_saves_redacted_question(self, agent):
        """redacted 模式应保存脱敏后的问题文本。"""
        question = "张三的邮箱是zhangsan@test.com，请查2026年1月行程"
        path = agent._save_raw_output_on_failure(
            question=question,
            stage="intent",
            prompt_name="intent_classifier",
            raw_output="{}",
            parsed_output={},
            parse_success=False,
            validation_success=False,
            error_message=None,
        )
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        question_str = saved["question"]
        assert isinstance(question_str, str)
        # PII 应被脱敏
        assert "zhangsan@test.com" not in question_str
        assert "[邮箱]" in question_str
        # 非敏感内容应保留
        assert "2026年1月" in question_str
        assert "行程" in question_str
