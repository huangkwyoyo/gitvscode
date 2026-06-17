"""
从 memory_rules.yml 自动生成 docs/memory/规则来源索引.md。

用法：
    python scripts/generate_rule_index.py
    python scripts/generate_rule_index.py --check-only   # 仅校验不生成

校验规则：
    1. YAML 格式必须正确可解析。
    2. rule_id 必须唯一。
    3. rule_id 必须以 TA-R 开头。
    4. status 值必须在允许范围内。
    5. 必填字段不得缺失。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# YAML 是可选的依赖 —— 如果未安装则给出明确提示
try:
    import yaml
except ImportError:
    sys.exit(
        "错误: 需要 PyYAML 库。请执行: pip install pyyaml\n"
        "  或者: pip install -r requirements.txt"
    )


# ── 项目根目录 ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── 路径常量 ──────────────────────────────────────────────────────────────────
RULES_YAML_PATH = PROJECT_ROOT / "docs" / "memory" / "memory_rules.yml"
OUTPUT_MD_PATH = PROJECT_ROOT / "docs" / "memory" / "规则来源索引.md"

# ── 合法状态值 ────────────────────────────────────────────────────────────────
VALID_STATUSES = {"proposed", "active", "deprecated", "superseded"}

# ── 必填字段 ──────────────────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "rule_id",
    "title",
    "status",
    "blocking",
    "severity",
    "source_memory",
    "risk_ids",
    "applies_to",
    "required_checks",
    "required_tests",
    "required_evals",
    "notes",
]


def load_rules(yaml_path: Path) -> list[dict[str, Any]]:
    """加载并解析 YAML 规则文件。

    Args:
        yaml_path: YAML 文件路径

    Returns:
        规则列表

    Raises:
        SystemExit: YAML 解析失败或文件不存在
    """
    if not yaml_path.exists():
        sys.exit(f"错误: 规则文件不存在: {yaml_path}")

    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        sys.exit(f"错误: YAML 解析失败 ({yaml_path}):\n{exc}")

    if data is None:
        sys.exit(f"错误: YAML 文件为空或仅有注释: {yaml_path}")

    if "rules" not in data:
        sys.exit(f"错误: YAML 缺少顶层 'rules' 键: {yaml_path}")

    rules = data["rules"]
    if not isinstance(rules, list):
        sys.exit(f"错误: 'rules' 必须是列表: {yaml_path}")

    if len(rules) == 0:
        _safe_print("[WARN] rules 列表为空，将生成空索引。")

    return rules


def validate_rules(rules: list[dict[str, Any]]) -> list[str]:
    """校验规则列表，返回警告信息列表。

    校验项：
        - rule_id 唯一
        - rule_id 以 TA-R 开头
        - status 在合法值范围内
        - 必填字段完整
        - blocking 与 status 一致性 (active + blocking=true 时警告)

    Args:
        rules: 规则列表

    Returns:
        警告/错误信息列表（致命错误通过 sys.exit 直接退出）
    """
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for i, rule in enumerate(rules):
        # 确保是字典
        if not isinstance(rule, dict):
            sys.exit(
                f"错误: rules[{i}] 不是字典类型，得到: {type(rule).__name__}"
            )

        rule_id = rule.get("rule_id")

        # ── rule_id 必填 ──────────────────────────────────────────────────
        if not rule_id:
            sys.exit(f"错误: rules[{i}] 缺少 rule_id")

        # ── rule_id 唯一性 ────────────────────────────────────────────────
        if rule_id in seen_ids:
            sys.exit(f"错误: rule_id 重复: {rule_id}")
        seen_ids.add(rule_id)

        # ── rule_id 前缀 ──────────────────────────────────────────────────
        if not str(rule_id).startswith("TA-R"):
            sys.exit(
                f"错误: rule_id 必须以 'TA-R' 开头: {rule_id} (rules[{i}])"
            )

        # ── 必填字段完整性 ────────────────────────────────────────────────
        missing_fields = [
            f for f in REQUIRED_FIELDS if f not in rule or rule[f] is None
        ]
        if missing_fields:
            sys.exit(
                f"错误: {rule_id} 缺少必填字段: {', '.join(missing_fields)}"
            )

        # ── status 合法性 ─────────────────────────────────────────────────
        status = rule.get("status")
        if status not in VALID_STATUSES:
            sys.exit(
                f"错误: {rule_id} 的 status 值非法: '{status}'，"
                f"合法值: {', '.join(sorted(VALID_STATUSES))}"
            )

        # ── 列表字段类型检查 ──────────────────────────────────────────────
        list_fields = ["risk_ids", "applies_to", "required_checks",
                       "required_tests", "required_evals"]
        for field in list_fields:
            if not isinstance(rule.get(field), list):
                sys.exit(
                    f"错误: {rule_id} 的 '{field}' 必须是列表类型，"
                    f"得到: {type(rule[field]).__name__}"
                )

        # ── blocking 类型检查 ──────────────────────────────────────────────
        blocking = rule.get("blocking")
        if not isinstance(blocking, bool):
            sys.exit(
                f"错误: {rule_id} 的 'blocking' 必须是布尔类型，"
                f"得到: {type(blocking).__name__}"
            )

        # ── proposed 规则不应为 blocking=true ─────────────────────────────
        if status == "proposed" and blocking is True:
            warnings.append(
                f"[WARN] {rule_id}: status=proposed 但 blocking=true，"
                f"建议先晋升为 active 再启用阻断"
            )

        # ── active + blocking=true 提示 ───────────────────────────────────
        if status == "active" and blocking is True:
            warnings.append(
                f"[INFO] {rule_id}: 已是 active + blocking=true 规则，"
                f"确认已通过完整晋升流程"
            )

    return warnings


def build_field_cell(values: list[str], default: str = "-") -> str:
    """将列表字段转换为 Markdown 表格单元格。

    Args:
        values: 字符串列表
        default: 列表为空时的占位符

    Returns:
        Markdown 格式的单元格内容（多值用 <br> 分隔）
    """
    if not values:
        return default
    return "<br>".join(f"`{v}`" for v in values)


def generate_markdown(rules: list[dict[str, Any]]) -> str:
    """根据规则列表生成 Markdown 索引。

    Args:
        rules: 校验过的规则列表

    Returns:
        完整的 Markdown 文档字符串
    """
    lines: list[str] = []

    # ── 文件头 ────────────────────────────────────────────────────────────
    lines.append("# 规则来源索引")
    lines.append("")
    lines.append(
        "> ⚠️ **本文件由 `memory_rules.yml` 自动生成，请勿手动编辑。**"
    )
    lines.append(
        "> 如需修改规则，请编辑 `docs/memory/memory_rules.yml` 后运行："
    )
    lines.append("> ```bash")
    lines.append("> python scripts/generate_rule_index.py")
    lines.append("> ```")
    lines.append("")

    # ── 统计概览 ──────────────────────────────────────────────────────────
    status_counts: dict[str, int] = {}
    blocking_count = 0
    for rule in rules:
        s = rule.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
        if rule.get("blocking"):
            blocking_count += 1

    lines.append("## 统计概览")
    lines.append("")
    lines.append(f"- **规则总数**: {len(rules)}")
    lines.append(f"- **阻断规则**: {blocking_count}")
    lines.append(f"- **观察规则**: {len(rules) - blocking_count}")
    for status_name in ["active", "proposed", "deprecated", "superseded"]:
        if status_name in status_counts:
            lines.append(
                f"- **{status_name}**: {status_counts[status_name]}"
            )
    lines.append("")

    # ── proposed → active 晋升标准 ────────────────────────────────────────
    lines.append("## proposed → active 晋升标准")
    lines.append("")
    lines.append("规则从 `proposed` 晋升为 `active` 至少需要满足以下条件：")
    lines.append("")
    lines.append(
        "1. 对应 check 已接入 fast gate warn 模式并稳定运行"
        "（连续 ≥3 次 fast gate 运行中该 check 未出现基础设施故障）。"
    )
    lines.append(
        "2. 对应 pytest 至少覆盖正例和负例"
        "（即至少 1 个「应通过」和 1 个「应失败」用例）。"
    )
    lines.append(
        "3. 对应 eval case 已存在并包含明确断言，"
        "或经团队评审确认不需要 eval"
        "（需在 `notes` 字段中注明原因和评审结论）。"
    )
    lines.append(
        "4. 至少一次完整 fast gate 通过"
        "（所有步骤 PASS，warn checks 无 infra_fail）。"
    )
    lines.append(
        "5. 人工审查确认无明显假阳性"
        "（审查记录需在 `notes` 中注明审查人和日期）。"
    )
    lines.append("")

    # ── 规则索引表 ────────────────────────────────────────────────────────
    lines.append("## 规则索引")
    lines.append("")

    # 表头
    headers = [
        "rule_id",
        "title",
        "status",
        "blocking",
        "severity",
        "risk_ids",
        "applies_to",
        "required_checks",
        "required_tests",
        "required_evals",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    # 表体
    for rule in rules:
        row = [
            f"**{rule['rule_id']}**",
            rule["title"],
            f"`{rule['status']}`",
            "🔴 阻断" if rule["blocking"] else "🟡 观察",
            f"`{rule['severity']}`",
            build_field_cell(rule.get("risk_ids", [])),
            build_field_cell(rule.get("applies_to", [])),
            build_field_cell(rule.get("required_checks", [])),
            build_field_cell(rule.get("required_tests", [])),
            build_field_cell(rule.get("required_evals", [])),
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # ── 规则详情 ──────────────────────────────────────────────────────────
    lines.append("## 规则详情")
    lines.append("")

    for rule in rules:
        rid = rule["rule_id"]
        lines.append(f"### {rid} — {rule['title']}")
        lines.append("")
        lines.append(f"- **状态**: `{rule['status']}`")
        lines.append(
            f"- **阻断**: {'是' if rule['blocking'] else '否'}"
        )
        lines.append(f"- **严重性**: `{rule['severity']}`")
        lines.append(f"- **经验来源**: {rule['source_memory']}")
        lines.append(
            f"- **关联风险**: {build_field_cell(rule.get('risk_ids', []))}"
        )
        lines.append("")
        if rule.get("notes"):
            lines.append(f"> {rule['notes']}")
            lines.append("")

    # ── 覆盖缺口汇总 ──────────────────────────────────────────────────────
    lines.append("## 覆盖缺口")
    lines.append("")
    lines.append("以下规则存在检查/测试/eval 覆盖缺口：")
    lines.append("")

    gap_headers = ["rule_id", "title", "缺口类型", "说明"]
    lines.append("| " + " | ".join(gap_headers) + " |")
    lines.append("| " + " | ".join("---" for _ in gap_headers) + " |")

    has_gaps = False
    for rule in rules:
        rid = rule["rule_id"]
        title = rule["title"]

        if not rule.get("required_checks"):
            lines.append(
                f"| **{rid}** | {title} | 检查脚本 | 缺少 harness check |"
            )
            has_gaps = True
        if not rule.get("required_tests"):
            lines.append(
                f"| **{rid}** | {title} | 测试 | 缺少 pytest 测试 |"
            )
            has_gaps = True
        if not rule.get("required_evals"):
            lines.append(
                f"| **{rid}** | {title} | Eval | 缺少 E2E eval 用例 |"
            )
            has_gaps = True

    if not has_gaps:
        lines.append("| - | 所有规则均已完整覆盖 | - | - |")

    lines.append("")

    # ── 文件尾 ────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append(
        f"*索引生成时间: 请查看 git 提交记录或文件修改时间*"
    )
    lines.append("")

    return "\n".join(lines)


def _safe_print(msg: str) -> None:
    """安全打印，处理 Windows GBK 编码问题。

    Args:
        msg: 要打印的消息
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        # 回退：用 ASCII 字符替换不可编码字符
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def main() -> None:
    """主入口：加载 → 校验 → 生成。"""
    # 在 Windows 上尝试启用 UTF-8 输出
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="从 memory_rules.yml 生成 规则来源索引.md"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="仅校验 YAML 文件，不生成 Markdown",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件路径（默认: docs/memory/规则来源索引.md）",
    )
    args = parser.parse_args()

    # 1. 加载
    _safe_print(f"[LOAD] 加载规则文件: {RULES_YAML_PATH}")
    rules = load_rules(RULES_YAML_PATH)
    _safe_print(f"   已加载 {len(rules)} 条规则")

    # 2. 校验
    _safe_print("[CHECK] 校验规则...")
    warnings = validate_rules(rules)

    if warnings:
        for w in warnings:
            _safe_print(w)

    _safe_print(f"   校验通过 [OK] ({len(rules)} 条规则)")

    if args.check_only:
        _safe_print("\n[OK] 仅校验模式，跳过 Markdown 生成。")
        return

    # 3. 生成 Markdown
    output_path = Path(args.output) if args.output else OUTPUT_MD_PATH
    _safe_print(f"[GEN] 生成 Markdown: {output_path}")

    markdown = generate_markdown(rules)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)

    _safe_print(f"[OK] 完成！输出: {output_path}")
    _safe_print(f"   规则数: {len(rules)}")
    _safe_print(f"   proposed: {sum(1 for r in rules if r.get('status') == 'proposed')}")
    _safe_print(f"   active:   {sum(1 for r in rules if r.get('status') == 'active')}")
    _safe_print(f"   blocking: {sum(1 for r in rules if r.get('blocking'))}")


if __name__ == "__main__":
    main()
