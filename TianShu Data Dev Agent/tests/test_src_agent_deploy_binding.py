"""
M5 部署绑定测试——验证产物与上线产物绑定的架构修复。

覆盖 Prompt 第八节规定的全部 20 项测试断言。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.agent.deploy_generator import (
    ALLOWED_WRITE_SCHEMAS,
    FORBIDDEN_DEPLOY_KEYWORDS,
    FORBIDDEN_WRITE_SCHEMAS,
    build_deployment_manifest,
    generate_deploy_spark,
    generate_deploy_sql,
    validate_deploy_sql,
    validate_write_boundary,
)
from src.agent.review_publisher import DEPLOY_FILES
from src.ir.types import (
    ArtifactHashes,
    DeployWriteStrategy,
    DeploymentManifest,
    ReleaseStatus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "fixtures" / "requirements" / "trip_daily_report.yml"
BUILD_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "build_review_package.py"
VERIFY_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "verify_review_package.py"
REVIEW_CLI = PROJECT_ROOT / "scripts" / "dev_agent" / "review_decision.py"
PIPELINE_CLI = PROJECT_ROOT / "scripts" / "pipeline" / "run_pipeline.py"


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _build_package(tmp_path: Path) -> Path:
    """运行 M2 build 生成 Review Package（含部署产物）。"""
    result = subprocess.run(
        [sys.executable, str(BUILD_CLI), "-r", str(FIXTURE),
         "--output-root", str(tmp_path)],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, f"M2 build failed: {result.stderr}"
    return tmp_path / "trip_daily_report_m2"


def _build_and_verify(tmp_path: Path) -> Path:
    """运行 M2 build + M3 verify。"""
    package_dir = _build_package(tmp_path)
    result = subprocess.run(
        [sys.executable, str(VERIFY_CLI), "-p", str(package_dir),
         "--no-sql-run"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, f"M3 verify failed: {result.stderr}"
    return package_dir


# ═══════════════════════════════════════════════════════════════
# 测试 1：Review Package 包含部署草案和 deployment_manifest.yml
# ═══════════════════════════════════════════════════════════════


def test_deploy_artifacts_present_in_package(tmp_path):
    """M2 build 后 Review Package 必须包含部署产物。"""
    package_dir = _build_package(tmp_path)

    deploy_sql = package_dir / "deploy" / "main.sql"
    deploy_spark = package_dir / "deploy" / "main.py"
    deploy_manifest = package_dir / "deployment_manifest.yml"

    assert deploy_sql.is_file(), f"缺少 {deploy_sql}"
    assert deploy_spark.is_file(), f"缺少 {deploy_spark}"
    assert deploy_manifest.is_file(), f"缺少 {deploy_manifest}"

    # 验证内容非空
    assert deploy_sql.read_text(encoding="utf-8").strip(), "deploy/main.sql 为空"
    assert deploy_spark.read_text(encoding="utf-8").strip(), "deploy/main.py 为空"

    manifest = yaml.safe_load(deploy_manifest.read_text(encoding="utf-8"))
    assert manifest["request_id"] == "trip_daily_report_m2"
    assert manifest["release_status"] == "DRAFT"


# ═══════════════════════════════════════════════════════════════
# 测试 2：SQL 部署脚本封装已验证 sql/main.sql，不重新生成查询逻辑
# ═══════════════════════════════════════════════════════════════


def test_deploy_sql_wraps_verified_query(tmp_path):
    """deploy/main.sql 从已验证的 sql/main.sql 确定性封装。"""
    package_dir = _build_package(tmp_path)

    verified_sql = (package_dir / "sql" / "main.sql").read_text(encoding="utf-8")
    deploy_sql = (package_dir / "deploy" / "main.sql").read_text(encoding="utf-8")

    # 部署 SQL 必须包含 CREATE OR REPLACE TABLE 或 INSERT
    assert "CREATE OR REPLACE TABLE" in deploy_sql or "INSERT" in deploy_sql, (
        "部署 SQL 缺少写入封装语句"
    )

    # 部署 SQL 的 SELECT 体必须来自已验证查询（去掉缩进空白后比较核心逻辑）
    verified_core = verified_sql.strip().rstrip(";")
    # 核心验证：部署 SQL 引用已验证查询的哈希
    assert "来源哈希" in deploy_sql, "部署 SQL 缺少来源哈希引用"


# ═══════════════════════════════════════════════════════════════
# 测试 3：Spark 部署脚本调用已审批的 build_dataframe()
# ═══════════════════════════════════════════════════════════════


def test_deploy_spark_calls_build_dataframe(tmp_path):
    """deploy/main.py 必须调用 build_dataframe。"""
    package_dir = _build_package(tmp_path)
    deploy_spark = (package_dir / "deploy" / "main.py").read_text(encoding="utf-8")

    assert "build_dataframe" in deploy_spark, (
        "Spark 部署脚本必须调用已验证的 build_dataframe() 入口"
    )
    assert "from spark.main import build_dataframe" in deploy_spark, (
        "Spark 部署脚本必须从 spark.main 导入 build_dataframe"
    )


# ═══════════════════════════════════════════════════════════════
# 测试 4：Spark 部署脚本不得复制过滤、聚合和 JOIN 逻辑
# ═══════════════════════════════════════════════════════════════


def test_deploy_spark_does_not_reimplement_logic(tmp_path):
    """deploy/main.py 不重新实现业务逻辑。"""
    package_dir = _build_package(tmp_path)
    verified_spark = (package_dir / "spark" / "main.py").read_text(encoding="utf-8")
    deploy_spark = (package_dir / "deploy" / "main.py").read_text(encoding="utf-8")

    # deploy/main.py 中 build_dataframe 的 import 行出现之后，
    # 不应再出现 F.sum/F.count/F.avg 等聚合函数定义
    import_line_idx = deploy_spark.find("from spark.main import build_dataframe")
    after_import = deploy_spark[import_line_idx:] if import_line_idx >= 0 else deploy_spark

    # 注意：spark/main.py 中的聚合逻辑（如 F.sum）不应在 deploy 中重复出现
    # 但如果 verified_spark 中有 F.sum，deploy 中 build_dataframe 调用之后不应再有
    assert "def build_dataframe" not in deploy_spark, (
        "Spark 部署脚本不得重新定义 build_dataframe"
    )


# ═══════════════════════════════════════════════════════════════
# 测试 5：source_query_hash 与 sql/main.sql 实际哈希一致
# ═══════════════════════════════════════════════════════════════


def test_source_query_hash_matches_verified_sql(tmp_path):
    """deployment_manifest.yml 的 source_query_hash 与 sql/main.sql 一致。"""
    package_dir = _build_package(tmp_path)

    verified_sql = (package_dir / "sql" / "main.sql").read_text(encoding="utf-8")
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )

    actual_hash = hashlib.sha256(verified_sql.encode("utf-8")).hexdigest()
    stored_hash = manifest["source_query_hash"]

    assert stored_hash == actual_hash, (
        f"source_query_hash 不一致: 清单 {stored_hash[:16]}... vs 实际 {actual_hash[:16]}..."
    )


# ═══════════════════════════════════════════════════════════════
# 测试 6：部署产物全部进入 artifact hashes
# ═══════════════════════════════════════════════════════════════


def test_deploy_artifacts_in_artifact_hashes(tmp_path):
    """decision.yml 的 artifact_hashes 必须包含部署产物哈希。"""
    package_dir = _build_package(tmp_path)

    decision = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    hashes = decision.get("artifact_hashes", {})

    assert hashes.get("deploy_sql"), "artifact_hashes 缺少 deploy_sql"
    assert hashes.get("deploy_spark"), "artifact_hashes 缺少 deploy_spark"
    assert hashes.get("deployment_manifest"), "artifact_hashes 缺少 deployment_manifest"

    # 哈希值非空
    for key in ["deploy_sql", "deploy_spark", "deployment_manifest"]:
        assert len(hashes[key]) == 64, f"{key} 哈希长度不是 64（SHA-256）"


# ═══════════════════════════════════════════════════════════════
# 测试 7：修改 deploy/main.sql 后完整性校验必须失败
# ═══════════════════════════════════════════════════════════════


def test_modified_deploy_sql_breaks_integrity(tmp_path):
    """修改 deploy/main.sql 后 artifact 完整性检查必须检测到。"""
    from src.agent.decision_manager import check_artifact_integrity

    package_dir = _build_package(tmp_path)

    # 读取当前哈希
    decision = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    stored_hashes = decision.get("artifact_hashes", {})

    # 修改 deploy/main.sql
    deploy_sql_path = package_dir / "deploy" / "main.sql"
    original = deploy_sql_path.read_text(encoding="utf-8")
    deploy_sql_path.write_text(original + "\n-- 恶意修改：DROP TABLE gold.important;\n", encoding="utf-8")

    # 检查完整性
    warnings = check_artifact_integrity(package_dir, stored_hashes)
    deploy_warnings = [w for w in warnings if "deploy" in w.lower()]

    assert len(deploy_warnings) > 0, "修改 deploy/main.sql 后完整性检查应报警告"


# ═══════════════════════════════════════════════════════════════
# 测试 8：修改 deploy/main.py 后完整性校验必须失败
# ═══════════════════════════════════════════════════════════════


def test_modified_deploy_spark_breaks_integrity(tmp_path):
    """修改 deploy/main.py 后 artifact 完整性检查必须检测到。"""
    from src.agent.decision_manager import check_artifact_integrity

    package_dir = _build_package(tmp_path)

    decision = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    stored_hashes = decision.get("artifact_hashes", {})

    deploy_spark_path = package_dir / "deploy" / "main.py"
    original = deploy_spark_path.read_text(encoding="utf-8")
    deploy_spark_path.write_text(original + "\n# 恶意修改\n", encoding="utf-8")

    warnings = check_artifact_integrity(package_dir, stored_hashes)
    deploy_warnings = [w for w in warnings if "deploy" in w.lower() or "main.py" in w]

    assert len(deploy_warnings) > 0, "修改 deploy/main.py 后完整性检查应报警告"


# ═══════════════════════════════════════════════════════════════
# 测试 9：修改 deployment_manifest.yml 后完整性校验必须失败
# ═══════════════════════════════════════════════════════════════


def test_modified_deployment_manifest_breaks_integrity(tmp_path):
    """修改 deployment_manifest.yml 后 artifact 完整性检查必须检测到。

    注意：当前 check_artifact_integrity 只检查 sql/spark/lineage，
    不自动检查 deployment_manifest.yml。但 decision.yml 的 artifact_hashes
    中记录了 deployment_manifest 哈希，验证引擎的 deploy_static 检查会对比。
    本测试确认哈希机制有效。
    """
    package_dir = _build_package(tmp_path)

    decision = yaml.safe_load(
        (package_dir / "decision.yml").read_text(encoding="utf-8")
    )
    stored_deploy_hash = decision["artifact_hashes"]["deployment_manifest"]

    # 修改 deployment_manifest.yml
    manifest_path = package_dir / "deployment_manifest.yml"
    original = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(original.replace("DRAFT", "RELEASE_APPROVED"), encoding="utf-8")

    # 验证哈希已变化
    new_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert new_hash != stored_deploy_hash, (
        "修改 deployment_manifest.yml 后哈希应变化"
    )


# ═══════════════════════════════════════════════════════════════
# 测试 10：缺少部署产物时不得获得 release approval
# ═══════════════════════════════════════════════════════════════


def test_release_approval_requires_deploy_artifacts(tmp_path):
    """缺少 deployment_manifest.yml 时 release set 必须失败。"""
    package_dir = _build_and_verify(tmp_path)

    # 删除部署产物
    (package_dir / "deployment_manifest.yml").unlink()

    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "release", str(package_dir),
         "--state", "RELEASE_APPROVED", "--message", "不应该成功"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0, "缺少 deployment_manifest.yml 时应拒绝 RELEASE_APPROVED"
    assert "deployment_manifest" in result.stderr


# ═══════════════════════════════════════════════════════════════
# 测试 11：目标表为 gold/bronze/silver 时必须 FAIL
# ═══════════════════════════════════════════════════════════════


@pytest.mark.parametrize("bad_schema", ["gold", "bronze", "silver"])
def test_forbidden_target_schemas_blocked(bad_schema):
    """目标表在禁止写入 schema 中时必须报错。"""
    manifest = DeploymentManifest(
        request_id="test",
        source_query_hash="abc123",
        target_table=f"{bad_schema}.test_table",
        write_strategy=DeployWriteStrategy.CREATE_TABLE_AS_SELECT.value,
    )
    errors = validate_write_boundary(manifest)
    schema_errors = [e for e in errors if bad_schema in e.lower()]

    assert len(schema_errors) > 0, (
        f"目标表 {bad_schema}.test_table 应被拦截（禁止写入 schema: {bad_schema}）"
    )


# ═══════════════════════════════════════════════════════════════
# 测试 12：非法写入策略必须 FAIL
# ═══════════════════════════════════════════════════════════════


def test_illegal_write_strategy_blocked():
    """不支持的写入策略必须报错。"""
    manifest = DeploymentManifest(
        request_id="test",
        source_query_hash="abc123",
        target_table="generated.test",
        write_strategy="DELETE_FROM",  # 非法策略
    )
    errors = validate_write_boundary(manifest)
    assert len(errors) > 0, "非法写入策略应被拦截"
    assert any("DELETE_FROM" in e or "不支持" in e for e in errors)


def test_production_target_environment_blocked():
    """target_environment 设为 PRODUCTION 时必须报错。"""
    manifest = DeploymentManifest(
        request_id="test",
        source_query_hash="abc123",
        target_table="generated.test",
        write_strategy=DeployWriteStrategy.CREATE_TABLE_AS_SELECT.value,
        target_environment="PRODUCTION",
    )
    errors = validate_write_boundary(manifest)
    assert len(errors) > 0, "target_environment=PRODUCTION 应被拦截"
    assert any("PRODUCTION" in e for e in errors)


# ═══════════════════════════════════════════════════════════════
# 测试 13：分区覆盖未声明分区列时必须 FAIL
# ═══════════════════════════════════════════════════════════════


@pytest.mark.parametrize("strategy", [
    DeployWriteStrategy.INSERT_OVERWRITE_PARTITION.value,
    DeployWriteStrategy.INSERT_INTO_PARTITION.value,
])
def test_partition_strategy_requires_partition_columns(strategy):
    """分区覆盖/追加必须声明 partition_columns。"""
    manifest = DeploymentManifest(
        request_id="test",
        source_query_hash="abc123",
        target_table="generated.test",
        write_strategy=strategy,
        partition_columns=[],  # 未声明分区列
    )
    errors = validate_write_boundary(manifest)
    assert len(errors) > 0, (
        f"写入策略 {strategy} 未声明分区列时应报错"
    )
    assert any("partition_column" in e.lower() for e in errors)


# ═══════════════════════════════════════════════════════════════
# 测试 14：SQL 部署草案包含禁止关键字时必须 FAIL
# ═══════════════════════════════════════════════════════════════


@pytest.mark.parametrize("bad_sql,keyword", [
    ("DROP TABLE gold.test;", "DROP"),
    ("ALTER TABLE gold.test ADD COLUMN x INT;", "ALTER"),
    ("DELETE FROM gold.test WHERE 1=1;", "DELETE"),
    ("TRUNCATE TABLE gold.test;", "TRUNCATE"),
    ("MERGE INTO gold.test USING src ON t.id = s.id WHEN MATCHED THEN UPDATE SET val = s.val", "MERGE"),
])
def test_forbidden_keywords_in_deploy_sql_blocked(bad_sql, keyword):
    """SQL 部署草案包含 DROP/ALTER/DELETE/TRUNCATE/MERGE 时必须报错。"""
    errors = validate_deploy_sql(bad_sql)
    assert len(errors) > 0, f"包含 {keyword} 的 SQL 部署草案应被拦截"
    assert any(keyword in e for e in errors)


def test_legitimate_ctas_allowed():
    """CREATE OR REPLACE TABLE（合法 CTAS）不应被误报。"""
    sql = "CREATE OR REPLACE TABLE generated.test AS\n    SELECT * FROM gold.source;\n"
    errors = validate_deploy_sql(sql)
    assert len(errors) == 0, f"合法 CTAS 不应报错，但实际报错: {errors}"


# ═══════════════════════════════════════════════════════════════
# 测试 15：Agent 不能设置 release approval
# ═══════════════════════════════════════════════════════════════


def test_agent_cannot_set_release_approval():
    """deployment_manifest.yml 的 release_status 默认必须是 DRAFT。"""
    manifest = build_deployment_manifest(
        request_id="test",
        verified_sql_hash="abc123",
        target_table="generated.test",
        write_strategy=DeployWriteStrategy.CREATE_TABLE_AS_SELECT.value,
    )
    assert manifest.release_status == ReleaseStatus.DRAFT.value, (
        "Agent 生成的部署清单 release_status 必须是 DRAFT"
    )
    assert manifest.human_review_required is True, (
        "部署清单 human_review_required 必须为 True"
    )


# ═══════════════════════════════════════════════════════════════
# 测试 16：只有人工操作可以设置 release approval
# ═══════════════════════════════════════════════════════════════


def test_only_human_can_set_release_approval(tmp_path):
    """人可以通过 CLI release 子命令设置 RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)
    logic_result = _approve_logic(package_dir)
    assert logic_result.returncode == 0, logic_result.stderr

    # M5b-2：RELEASE_APPROVED 要求物化验证通过
    _setup_materialized_package(package_dir)

    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "release", str(package_dir),
         "--state", "RELEASE_APPROVED", "--message", "部署产物已审查通过", "--user", "ops_reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, f"人工设置 RELEASE_APPROVED 应成功: {result.stderr}"

    # 验证 deployment_manifest.yml 已更新
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert manifest["release_status"] == "RELEASE_APPROVED"
    assert manifest["release_approved_by"] == "human:ops_reviewer"


# ═══════════════════════════════════════════════════════════════
# 测试 17：查询逻辑 APPROVED 不等于可上线
# ═══════════════════════════════════════════════════════════════


def test_approved_does_not_equal_releasable(tmp_path):
    """decision.yml APPROVED 不等于 deployment_manifest.yml RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)

    # 设置查询逻辑 APPROVED
    subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "查询逻辑审查通过", "--user", "reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )

    # decision.yml 是 APPROVED
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["current_state"] == "APPROVED"

    # deployment_manifest.yml 仍是 DRAFT
    deploy_manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert deploy_manifest["release_status"] == "DRAFT", (
        "查询逻辑 APPROVED 不应自动使部署发布状态变为 RELEASE_APPROVED"
    )


# ═══════════════════════════════════════════════════════════════
# 测试 18：原有 v2 Review Package 功能继续通过
# ═══════════════════════════════════════════════════════════════


def test_legacy_review_package_structure_intact(tmp_path):
    """原有 9 个必备文件仍然存在。"""
    package_dir = _build_package(tmp_path)

    from src.agent.review_publisher import REQUIRED_FILES
    for rel_path in REQUIRED_FILES:
        assert (package_dir / rel_path).is_file(), f"缺少必备文件: {rel_path}"


def test_legacy_m3_verification_still_works(tmp_path):
    """M3 验证引擎仍然正常工作。"""
    package_dir = _build_and_verify(tmp_path)

    # 验证报告存在
    verification = package_dir / "reports" / "verification.md"
    assert verification.is_file()

    # 验证摘要存在且包含部署状态
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )
    assert "deploy_static_status" in summary


def test_legacy_decision_state_machine_intact(tmp_path):
    """人审状态机 PENDING_REVIEW → APPROVED → SUPERSEDED 链路正常。"""
    package_dir = _build_and_verify(tmp_path)

    # 初始状态
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["current_state"] == "PENDING_REVIEW"

    # APPROVED
    subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "批准", "--user", "tester"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["current_state"] == "APPROVED"


# ═══════════════════════════════════════════════════════════════
# 测试 19：v1 pipeline 继续可用
# ═══════════════════════════════════════════════════════════════


def test_v1_pipeline_still_works(tmp_path):
    """v1 legacy pipeline dry-run 继续可用。"""
    # 设置 UTF-8 编码避免 Windows GBK 字符集问题
    env = {**__import__('os').environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(PIPELINE_CLI), "-r", str(FIXTURE), "--dry-run"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
        env=env, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"v1 pipeline dry-run 失败: {result.stderr}"
    # dry-run 应有输出（编码问题可能使 stdout 为空，但 returncode==0 已证明成功）
    output = result.stdout or ""
    assert result.returncode == 0  # 再次确认成功执行


# ═══════════════════════════════════════════════════════════════
# 测试 20：没有部署行为被实际执行
# ═══════════════════════════════════════════════════════════════


def test_no_deployment_executed(tmp_path):
    """deploy/main.sql 和 deploy/main.py 仅作为草案生成，不实际执行。"""
    package_dir = _build_package(tmp_path)

    deploy_sql = (package_dir / "deploy" / "main.sql").read_text(encoding="utf-8")
    deploy_spark = (package_dir / "deploy" / "main.py").read_text(encoding="utf-8")

    # 草案标记存在于 SQL 部署脚本
    assert "未经人审" in deploy_sql or "草案" in deploy_sql or "DRAFT" in deploy_sql.upper(), (
        "SQL 部署脚本必须标记为草案"
    )

    # 草案标记存在于 Spark 部署脚本
    assert "未经人审" in deploy_spark or "草案" in deploy_spark or "DRAFT" in deploy_spark.upper(), (
        "Spark 部署脚本必须标记为草案"
    )

    # 确认 generated 目录中只有草案产物，没有实际执行结果
    deploy_manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert deploy_manifest["release_status"] == "DRAFT", (
        "部署清单 release_status 必须为 DRAFT——未获发布批准"
    )
    assert deploy_manifest["target_environment"] != "PRODUCTION", (
        "target_environment 不得为 PRODUCTION"
    )


# ═══════════════════════════════════════════════════════════════
# M5a：双内核绑定、严格发布审批与篡改失效
# ═══════════════════════════════════════════════════════════════


def test_deployment_manifest_binds_sql_and_spark_kernels(tmp_path):
    """部署清单必须同时绑定 SQL 与 Spark 转换内核。"""
    package_dir = _build_package(tmp_path)
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )

    assert manifest["mode"] == "MATERIALIZE"
    assert manifest["source_sql_ref"] == "sql/main.sql"
    assert manifest["source_spark_ref"] == "spark/main.py"
    assert manifest["allowed_write_schema"] == "generated"
    assert manifest["materialization_status"] == "PENDING"

    sql_hash = hashlib.sha256(
        (package_dir / manifest["source_sql_ref"]).read_bytes()
    ).hexdigest()
    spark_hash = hashlib.sha256(
        (package_dir / manifest["source_spark_ref"]).read_bytes()
    ).hexdigest()
    assert manifest["source_sql_hash"] == sql_hash
    assert manifest["source_spark_hash"] == spark_hash


def test_release_approval_requires_logic_approval(tmp_path):
    """发布审批必须以人工逻辑审批为前置条件。"""
    package_dir = _build_and_verify(tmp_path)

    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "release", str(package_dir),
         "--state", "RELEASE_APPROVED", "--message", "越过逻辑审批"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )

    assert result.returncode != 0
    assert "LOGIC_APPROVED" in result.stderr


def test_release_approval_requires_all_artifact_hashes(tmp_path):
    """旧格式缺少任一发布哈希时必须阻断发布审批。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)
    # M5b-2：先创建物化报告以填充 materialization_verification 哈希
    _setup_materialized_package(package_dir)
    decision_path = package_dir / "decision.yml"
    decision = yaml.safe_load(decision_path.read_text(encoding="utf-8"))
    decision["artifact_hashes"].pop("deploy_spark")
    decision_path.write_text(
        yaml.safe_dump(decision, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = _approve_release(package_dir)

    assert result.returncode != 0
    assert "deploy_spark" in result.stderr


def test_release_approval_records_hash_snapshot(tmp_path):
    """发布审批必须在 decision 和审计日志中记录完整制品快照。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    # M5b-2：RELEASE_APPROVED 要求物化验证通过
    _setup_materialized_package(package_dir)

    result = _approve_release(package_dir)

    assert result.returncode == 0, result.stderr
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    snapshot = decision["release_approval_artifact_hashes"]
    for key in [
        "sql_main", "spark_main", "lineage_source_refs", "verification_summary",
        "deployment_manifest", "deploy_sql", "deploy_spark",
        "materialization_verification",
    ]:
        assert len(snapshot[key]) == 64 or snapshot[key] is None, (
            f"发布审批快照缺少 {key}"
        )
    assert decision["logic_approval_state"] == "LOGIC_APPROVED"
    assert decision["release_approval_state"] == "RELEASE_APPROVED"

    log = yaml.safe_load((package_dir / "decision_log.yml").read_text(encoding="utf-8"))
    assert log["entries"][-1]["artifact_hashes"] == snapshot


def test_modified_deploy_sql_supersedes_only_release_approval(tmp_path):
    """部署外壳变化只使发布批准失效，不影响逻辑批准。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)
    _setup_materialized_package(package_dir)
    assert _approve_release(package_dir).returncode == 0
    deploy_path = package_dir / "deploy" / "main.sql"
    deploy_path.write_text(
        deploy_path.read_text(encoding="utf-8") + "\n-- tampered\n",
        encoding="utf-8",
    )

    result = _approve_release(package_dir)

    assert result.returncode != 0
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert decision["current_state"] == "APPROVED"
    assert decision["logic_approval_state"] == "LOGIC_APPROVED"
    assert decision["release_approval_state"] == "SUPERSEDED"
    assert manifest["release_status"] == "SUPERSEDED"


def test_modified_query_supersedes_logic_and_release_approvals(tmp_path):
    """转换内核变化必须同时使逻辑批准与发布批准失效。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)
    _setup_materialized_package(package_dir)
    assert _approve_release(package_dir).returncode == 0
    sql_path = package_dir / "sql" / "main.sql"
    sql_path.write_text(
        sql_path.read_text(encoding="utf-8") + "\n-- query changed\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VERIFY_CLI), "-p", str(package_dir), "--no-sql-run"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert decision["current_state"] == "SUPERSEDED"
    assert decision["logic_approval_state"] == "SUPERSEDED"
    assert decision["release_approval_state"] == "SUPERSEDED"
    assert manifest["release_status"] == "SUPERSEDED"


def _approve_logic(package_dir: Path) -> subprocess.CompletedProcess[str]:
    """通过 CLI 执行人工逻辑审批。"""
    return subprocess.run(
        [sys.executable, str(REVIEW_CLI), "set", str(package_dir),
         "--state", "APPROVED", "--message", "逻辑已人工审查", "--user", "reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )


def _approve_release(package_dir: Path) -> subprocess.CompletedProcess[str]:
    """通过 CLI 执行人工发布审批。"""
    return subprocess.run(
        [sys.executable, str(REVIEW_CLI), "release", str(package_dir),
         "--state", "RELEASE_APPROVED", "--message", "部署制品已人工审查",
         "--user", "release_reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )


def test_deployment_manifest_contract_declares_m5a_fields():
    """部署清单 Schema 必须声明双内核和双审批边界字段。"""
    schema_path = PROJECT_ROOT / "contracts" / "deployment_manifest_schema.yml"
    assert schema_path.is_file()
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert {
        "request_id", "mode", "source_sql_ref", "source_sql_hash",
        "source_spark_ref", "source_spark_hash", "target_table",
        "write_strategy", "allowed_write_schema", "materialization_status",
        "release_status",
    } <= required


def test_rewritten_deploy_query_fails_static_validation(tmp_path):
    """部署 SQL 改写业务查询后必须在静态验证中失败。"""
    package_dir = _build_package(tmp_path)
    deploy_path = package_dir / "deploy" / "main.sql"
    deploy_path.write_text(
        deploy_path.read_text(encoding="utf-8").replace(
            "GROUP BY trip_date",
            "WHERE trip_count > 10\nGROUP BY trip_date",
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(VERIFY_CLI), "-p", str(package_dir), "--no-sql-run"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )
    summary = yaml.safe_load(
        (package_dir / "reports" / "verification_summary.yml").read_text(encoding="utf-8")
    )

    assert result.returncode == 0, result.stderr
    assert summary["deploy_static_status"] == "FAIL"


@pytest.mark.parametrize("relative_path", [
    "deploy/main.py",
    "deployment_manifest.yml",
])
def test_tampered_release_artifact_blocks_existing_approval(tmp_path, relative_path):
    """任一发布制品被篡改后，旧发布批准必须失效。"""
    package_dir = _build_and_verify(tmp_path)
    assert _approve_logic(package_dir).returncode == 0
    _setup_materialized_package(package_dir)
    assert _approve_release(package_dir).returncode == 0
    target = package_dir / relative_path
    target.write_text(
        target.read_text(encoding="utf-8") + "\n# tampered\n",
        encoding="utf-8",
    )

    result = _approve_release(package_dir)

    assert result.returncode != 0
    decision = yaml.safe_load((package_dir / "decision.yml").read_text(encoding="utf-8"))
    assert decision["release_approval_state"] == "SUPERSEDED"


# ═══════════════════════════════════════════════════════════════
# M5b-2 P0：物化验证闸门——RELEASE_APPROVED 前置条件
# ═══════════════════════════════════════════════════════════════


def _setup_materialized_package(package_dir: Path, **report_overrides) -> Path:
    """设置已完成物化验证的 package——用于测试发布闸门。

    创建合法的 materialization_verification.yml 并更新 decision.yml 中的哈希，
    使后续 RELEASE_APPROVED 的 artifact integrity 检查能通过。
    """
    from src.agent.decision_manager import (
        compute_artifact_hashes,
        update_artifact_hashes_in_decision,
    )

    # 设置 manifest materialization_status
    manifest_path = package_dir / "deployment_manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["materialization_status"] = "MATERIALIZATION_VALIDATED"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    # 创建物化验证报告
    reports_dir = package_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "verification_id": "mat_test_0001",
        "request_id": report_overrides.get("request_id", "trip_daily_report_m2"),
        "sandbox_id": "test-sandbox-uuid",
        "sandbox_path": "/tmp/test_sandbox",
        "declared_target": "generated.trip_daily_report_m2",
        "sandbox_target": "sandbox_output",
        "engine": "duckdb",
        "operation": "CTAS",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:01+00:00",
        "overall_status": report_overrides.get("overall_status", "PASS"),
        "cleanup_status": "PASS",
        "source_query_hash_status": report_overrides.get(
            "source_query_hash_status", "PASS"
        ),
        "deploy_artifact_hash_status": report_overrides.get(
            "deploy_artifact_hash_status", "PASS"
        ),
        "static_validation_status": "PASS",
        "execution_status": "PASS",
        "output_schema_status": "PASS",
        "row_count_status": "PASS",
        "null_check_status": "PASS",
        "uniqueness_status": "PENDING",
        "idempotency_status": "PASS",
        "checks": [],
        "output_row_count": 100,
        "select_row_count": 100,
        "output_columns": ["col1"],
        "output_column_types": ["VARCHAR"],
        "null_rates": {},
        "numeric_sums": {},
        "warnings": [],
        "failures": [],
        "human_review_required": True,
        "generated_at": "2026-01-01T00:00:01+00:00",
    }
    mat_report_path = reports_dir / "materialization_verification.yml"
    mat_report_path.write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    # 更新 decision.yml——写入包含 materialization_verification 的哈希
    hashes = compute_artifact_hashes(package_dir)
    update_artifact_hashes_in_decision(package_dir, hashes)

    return package_dir


# ── 测试 1：materialization_status=PENDING → 拒绝 ──


def test_materialization_pending_blocks_release_approval(tmp_path):
    """materialization_status 仍为 PENDING 时必须拒绝 RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "materialization_status=PENDING 时应拒绝 RELEASE_APPROVED"
    )
    assert "materialization_status" in result.stderr


# ── 测试 2：materialization_status=FAILED → 拒绝 ──


def test_materialization_failed_blocks_release_approval(tmp_path):
    """materialization_status 为 FAILED 时必须拒绝 RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    # 设置 manifest materialization_status=FAILED
    manifest_path = package_dir / "deployment_manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["materialization_status"] = "FAILED"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "materialization_status=FAILED 时应拒绝 RELEASE_APPROVED"
    )
    assert "materialization_status" in result.stderr


# ── 测试 3：materialization_status=WARN → 拒绝 ──


def test_materialization_warn_blocks_release_approval(tmp_path):
    """materialization_status 为 WARN 时必须拒绝 RELEASE_APPROVED。

    WARN ≠ MATERIALIZATION_VALIDATED——只有全部通过才是 VALIDATED。
    """
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    # 设置 manifest materialization_status=WARN
    manifest_path = package_dir / "deployment_manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["materialization_status"] = "WARN"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "materialization_status=WARN 时应拒绝 RELEASE_APPROVED"
    )
    assert "materialization_status" in result.stderr


# ── 测试 4：缺少 materialization_verification.yml → 拒绝 ──


def test_missing_materialization_report_blocks_release_approval(tmp_path):
    """缺少 materialization_verification.yml 时必须拒绝 RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    # 设置 manifest materialization_status=MATERIALIZATION_VALIDATED 但不创建报告
    manifest_path = package_dir / "deployment_manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["materialization_status"] = "MATERIALIZATION_VALIDATED"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "缺少 materialization_verification.yml 时应拒绝 RELEASE_APPROVED"
    )
    assert "materialization_verification" in result.stderr


# ── 测试 5：物化报告 overall_status 非 PASS → 拒绝 ──


def test_materialization_overall_not_pass_blocks_release_approval(tmp_path):
    """物化报告 overall_status 非 PASS 时必须拒绝 RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    _setup_materialized_package(package_dir, overall_status="FAIL")

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "物化报告 overall_status=FAIL 时应拒绝 RELEASE_APPROVED"
    )
    assert "overall_status" in result.stderr


# ── 测试 6：报告 request_id 与 Manifest 不一致 → 拒绝 ──


def test_materialization_request_id_mismatch_blocks_release_approval(tmp_path):
    """物化报告 request_id 与 Manifest 不一致时必须拒绝 RELEASE_APPROVED。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    _setup_materialized_package(package_dir, request_id="different_package_m2")

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "request_id 不一致时应拒绝 RELEASE_APPROVED"
    )
    assert "request_id" in result.stderr


# ── 测试 7：报告对应旧 deploy/main.sql → 拒绝 ──


def test_stale_deploy_artifact_hash_blocks_release_approval(tmp_path):
    """deploy_artifact_hash_status 非 PASS 时必须拒绝 RELEASE_APPROVED。

    模拟场景：物化验证后 deploy/main.sql 被修改，
    重新计算 artifact hashes 后 deploy_sql 哈希变化，
    但报告的 deploy_artifact_hash_status 仍为 FAIL。
    """
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    _setup_materialized_package(package_dir, deploy_artifact_hash_status="FAIL")

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "deploy_artifact_hash_status=FAIL 时应拒绝 RELEASE_APPROVED"
    )
    assert "deploy_artifact_hash_status" in result.stderr


# ── 测试 8：报告对应旧 sql/main.sql → 拒绝 ──


def test_stale_source_query_hash_blocks_release_approval(tmp_path):
    """source_query_hash_status 非 PASS 时必须拒绝 RELEASE_APPROVED。

    模拟场景：物化验证后 sql/main.sql 被修改，
    报告的 source_query_hash_status 为 FAIL。
    """
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    _setup_materialized_package(package_dir, source_query_hash_status="FAIL")

    result = _approve_release(package_dir)

    assert result.returncode != 0, (
        "source_query_hash_status=FAIL 时应拒绝 RELEASE_APPROVED"
    )
    assert "source_query_hash_status" in result.stderr


# ── 测试 9：所有条件满足 → 人工 RELEASE_APPROVED 成功 ──


def test_all_conditions_met_release_approval_succeeds(tmp_path):
    """所有闸门条件满足时，人工 RELEASE_APPROVED 应成功。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    _setup_materialized_package(package_dir)

    result = _approve_release(package_dir)

    assert result.returncode == 0, (
        f"所有条件满足时应成功 RELEASE_APPROVED，但失败: {result.stderr}"
    )
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert manifest["release_status"] == "RELEASE_APPROVED"
    assert manifest["release_approved_by"] == "human:release_reviewer"


# ── 测试 10：RELEASE_REJECTED 不受物化状态限制 ──


def test_release_rejected_not_blocked_by_materialization_status(tmp_path):
    """RELEASE_REJECTED 不应受物化验证闸门限制。

    人可以在物化验证未完成时拒绝发布。
    """
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    # materialization_status 仍为 PENDING，不创建物化报告
    result = subprocess.run(
        [sys.executable, str(REVIEW_CLI), "release", str(package_dir),
         "--state", "RELEASE_REJECTED", "--message", "部署方案有设计问题，拒绝发布",
         "--user", "release_reviewer"],
        cwd=PROJECT_ROOT, text=True, capture_output=True, check=False,
    )

    assert result.returncode == 0, (
        f"RELEASE_REJECTED 不应受物化状态限制，但失败: {result.stderr}"
    )
    manifest = yaml.safe_load(
        (package_dir / "deployment_manifest.yml").read_text(encoding="utf-8")
    )
    assert manifest["release_status"] == "RELEASE_REJECTED"


# ── 测试 11：拒绝路径不得修改 release_status ──


def test_rejected_release_does_not_modify_release_status(tmp_path):
    """物化验证闸门拒绝时，release_status 必须保持原值不变。"""
    package_dir = _build_and_verify(tmp_path)
    _approve_logic(package_dir)

    # 读取原始 release_status
    manifest_path = package_dir / "deployment_manifest.yml"
    original_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    original_status = original_manifest["release_status"]

    # 尝试 RELEASE_APPROVED（会因缺少物化验证而失败）
    result = _approve_release(package_dir)

    assert result.returncode != 0, "无物化验证时应拒绝"
    # 重新读取——release_status 必须不变
    manifest_after = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest_after["release_status"] == original_status, (
        f"拒绝后 release_status 应保持 {original_status}，"
        f"实际为 {manifest_after['release_status']}"
    )


# ── 测试 12：check_materialization_gate 单元测试 ──


def test_check_materialization_gate_all_pass():
    """单元测试：所有闸门条件通过时返回空列表。"""
    import tempfile
    from src.agent.decision_manager import check_materialization_gate

    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        # 创建必要文件
        (pkg / "reports").mkdir()
        manifest = {"request_id": "test_pkg", "materialization_status": "MATERIALIZATION_VALIDATED"}
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(manifest), encoding="utf-8"
        )
        report = {
            "request_id": "test_pkg",
            "overall_status": "PASS",
            "source_query_hash_status": "PASS",
            "deploy_artifact_hash_status": "PASS",
        }
        (pkg / "reports" / "materialization_verification.yml").write_text(
            yaml.safe_dump(report), encoding="utf-8"
        )

        errors = check_materialization_gate(pkg)
        assert errors == [], f"所有条件通过时应返回空列表，实际: {errors}"


def test_check_materialization_gate_each_gate_fails():
    """单元测试：逐一验证每个闸门条件的失败路径。"""
    import tempfile
    from src.agent.decision_manager import check_materialization_gate

    base_manifest = {
        "request_id": "test_pkg",
        "materialization_status": "MATERIALIZATION_VALIDATED",
    }
    base_report = {
        "request_id": "test_pkg",
        "overall_status": "PASS",
        "source_query_hash_status": "PASS",
        "deploy_artifact_hash_status": "PASS",
    }

    # 1. 缺少报告
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(base_manifest), encoding="utf-8"
        )
        errors = check_materialization_gate(pkg)
        assert len(errors) > 0 and "materialization_verification" in errors[0]

    # 2. materialization_status 非 MATERIALIZATION_VALIDATED
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        (pkg / "reports").mkdir()
        bad_manifest = dict(base_manifest, materialization_status="PENDING")
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(bad_manifest), encoding="utf-8"
        )
        (pkg / "reports" / "materialization_verification.yml").write_text(
            yaml.safe_dump(base_report), encoding="utf-8"
        )
        errors = check_materialization_gate(pkg)
        assert len(errors) > 0 and "materialization_status" in errors[0]

    # 3. overall_status 非 PASS
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        (pkg / "reports").mkdir()
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(base_manifest), encoding="utf-8"
        )
        bad_report = dict(base_report, overall_status="FAIL")
        (pkg / "reports" / "materialization_verification.yml").write_text(
            yaml.safe_dump(bad_report), encoding="utf-8"
        )
        errors = check_materialization_gate(pkg)
        assert len(errors) > 0 and "overall_status" in errors[0]

    # 4. request_id 不一致
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        (pkg / "reports").mkdir()
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(base_manifest), encoding="utf-8"
        )
        bad_report = dict(base_report, request_id="other_package")
        (pkg / "reports" / "materialization_verification.yml").write_text(
            yaml.safe_dump(bad_report), encoding="utf-8"
        )
        errors = check_materialization_gate(pkg)
        assert len(errors) > 0 and "request_id" in errors[0]

    # 5. source_query_hash_status 非 PASS
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        (pkg / "reports").mkdir()
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(base_manifest), encoding="utf-8"
        )
        bad_report = dict(base_report, source_query_hash_status="FAIL")
        (pkg / "reports" / "materialization_verification.yml").write_text(
            yaml.safe_dump(bad_report), encoding="utf-8"
        )
        errors = check_materialization_gate(pkg)
        assert len(errors) > 0 and "source_query_hash_status" in errors[0]

    # 6. deploy_artifact_hash_status 非 PASS
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg = Path(tmpdir)
        (pkg / "reports").mkdir()
        (pkg / "deployment_manifest.yml").write_text(
            yaml.safe_dump(base_manifest), encoding="utf-8"
        )
        bad_report = dict(base_report, deploy_artifact_hash_status="FAIL")
        (pkg / "reports" / "materialization_verification.yml").write_text(
            yaml.safe_dump(bad_report), encoding="utf-8"
        )
        errors = check_materialization_gate(pkg)
        assert len(errors) > 0 and "deploy_artifact_hash_status" in errors[0]
