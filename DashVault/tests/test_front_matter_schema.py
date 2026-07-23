# tests/test_front_matter_schema.py
"""Front Matter JSON Schema 校验测试"""
import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "front-matter.schema.json"


def load_schema():
    """加载 JSON Schema 文件"""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


# 26 位有效 ULID（Crockford base32，不含 I L O U）
VALID_ULID = "01J3R7XKABCDEFGHJKMNPQRS78"  # 正好 26 位
VALID_ULID_2 = "01J5A9YZNMPQRSTVWXYZ012345"


def make_valid_fm(**overrides) -> dict:
    """构造一个合法的最小 Front Matter"""
    data = {
        "doc_id": "datadev.current-state",
        "doc_type": "current_state",
        "project_ids": ["datadev-v3"],
        "revision_id": VALID_ULID,
        "revision": 1,
        "previous_revision_id": None,
        "content_hash": "sha256:" + "a" * 64,
        "review_status": "draft",
        "publication_status": "unpublished",
        "role_status": None,
        "provenance": "derived",
        "authority": "canonical_view",
        "evidence_level": "supported",
        "spec_id": "dashvault.spec.front-matter",
        "spec_version": "1.0.0",
        "spec_content_hash": "sha256:" + "b" * 64,
        "prompt_id": "prompt-current-state",
        "prompt_version": "1.0.0",
        "prompt_content_hash": "sha256:" + "c" * 64,
        "source_snapshots": [{
            "project_id": "datadev-v3",
            "git_commit": "a" * 40,
            "git_root": "D:\\Projects\\datadev",
            "git_pathspec": ".",
            "worktree_state": "clean",
            "evidence_manifest": "_evidence/manifest-01J3R7XK.json",
            "worktree_hash": None
        }],
        "title": "DataDev Agent v3 当前状态",
        "generated_at": "2026-07-23T15:30:00+08:00",
        "dashvault_version": "0.1.0",
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "model_revision": "20250701",
        "run_id": "run-01J3R7XKAB",
        "last_generated_commit": "a" * 40,
        "last_published_commit": None,
        "supersedes": None,
        "superseded_by": None,
        "corrected_by": None,
        "references": [],
        "tags": [],
        "reviewed_at": None,
        "reviewed_by": None
    }
    data.update(overrides)
    return data


class TestFrontMatterSchema:
    """Front Matter Schema 校验测试集"""

    def test_valid_minimal(self):
        """合法最小文档通过校验"""
        schema = load_schema()
        validate(instance=make_valid_fm(), schema=schema)

    def test_doc_id_rejects_invalid(self):
        """doc_id 格式校验"""
        schema = load_schema()
        validate(instance=make_valid_fm(doc_id="datadev.current-state"), schema=schema)
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(doc_id="INVALID"), schema=schema)

    def test_published_requires_approved(self):
        """published 要求 review_status == approved"""
        schema = load_schema()
        validate(instance=make_valid_fm(
            publication_status="published", review_status="approved"
        ), schema=schema)
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(
                publication_status="published", review_status="draft"
            ), schema=schema)

    def test_revision_gt_1_requires_previous(self):
        """revision > 1 要求 previous_revision_id 为有效 ULID"""
        schema = load_schema()
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(revision=2, previous_revision_id=None), schema=schema)
        validate(instance=make_valid_fm(
            revision=2, previous_revision_id=VALID_ULID_2
        ), schema=schema)

    def test_multi_project_requires_synthesis(self):
        """多项目要求 provenance == synthesis"""
        schema = load_schema()
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(
                project_ids=["datadev-v3", "tianshu"], provenance="derived"
            ), schema=schema)
        validate(instance=make_valid_fm(
            project_ids=["datadev-v3", "tianshu"],
            provenance="synthesis", authority="reference"
        ), schema=schema)

    def test_inferred_cannot_be_source_of_truth(self):
        """推导文档禁止 authority:source_of_truth"""
        schema = load_schema()
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(
                provenance="inferred", authority="source_of_truth"
            ), schema=schema)

    def test_derived_cannot_be_source_of_truth(self):
        """派生文档禁止 authority:source_of_truth"""
        schema = load_schema()
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(
                provenance="derived", authority="source_of_truth"
            ), schema=schema)

    def test_source_cannot_be_speculative(self):
        """source 文档禁止 evidence_level:speculative"""
        schema = load_schema()
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(
                provenance="source", evidence_level="speculative"
            ), schema=schema)

    def test_git_commit_accepts_40_hex_or_non_git(self):
        """git_commit 接受 40 位 hex 或 non_git"""
        schema = load_schema()
        # 40 位 hex → 合法
        validate(instance=make_valid_fm(), schema=schema)
        # non_git → 合法
        data = make_valid_fm()
        data["source_snapshots"][0]["git_commit"] = "non_git"
        data["source_snapshots"][0]["worktree_state"] = "non_git"
        data["last_generated_commit"] = "non_git"
        validate(instance=data, schema=schema)
        # 短 SHA → 非法
        data["last_generated_commit"] = "abc123"
        with pytest.raises(ValidationError):
            validate(instance=data, schema=schema)

    def test_revision_id_must_be_26_chars(self):
        """revision_id 必须是 26 位 ULID"""
        schema = load_schema()
        with pytest.raises(ValidationError):
            validate(instance=make_valid_fm(revision_id="too-short"), schema=schema)
        validate(instance=make_valid_fm(revision_id=VALID_ULID), schema=schema)
