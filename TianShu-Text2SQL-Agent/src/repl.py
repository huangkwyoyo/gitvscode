"""
TianShu Text2SQL Agent 交互式 REPL。

提供命令行交互循环，处理完整的"问 → 反问 → 澄清 → 答"闭环。

用法：
    python -m src.repl
"""

from __future__ import annotations

import sys
from datetime import datetime

from .agent import Text2SQLAgent
from .ir import AgentResponse
from .utils import setup_console_encoding


def _print_banner(agent: Text2SQLAgent):
    """打印启动横幅"""
    print("=" * 60)
    print("  TianShu 中文问数 Agent — 交互式 REPL")
    print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if agent.is_ready:
        print("  DuckDB: ✅ 已连接")
    else:
        print("  DuckDB: ⚠️ 离线模式（契约文件可用）")
    print()
    print("  输入问题开始查询，输入 'quit' 或 'exit' 退出")
    print("=" * 60)
    print()


def _format_answer(response: AgentResponse) -> str:
    """格式化最终回答（含 Phase 6A 结构化产物提示）"""
    lines: list[str] = []

    if response.chinese_answer:
        lines.append(f"\n📊 {response.chinese_answer}")

    # ── Phase 6A：结构化产物提示 ──
    if response.warnings:
        for w in response.warnings[:3]:  # 最多展示前 3 条警告
            lines.append(f"   ⚠️  {w}")

    if response.chart_spec:
        chart_type = response.chart_spec.get("chart_type", "") if isinstance(response.chart_spec, dict) else ""
        if chart_type:
            type_labels = {"line": "📈 折线图", "bar": "📊 柱状图", "table": "📋 表格", "metric_card": "🔢 指标卡"}
            lines.append(f"   {type_labels.get(chart_type, chart_type)} 可用")

    # 补充元信息
    if response.result:
        if response.result.source_table:
            lines.append(f"   数据来源: {response.result.source_table}")
        if response.result.execution_time_ms:
            lines.append(f"   耗时: {response.result.execution_time_ms}ms")
        if response.result.row_count > 0:
            lines.append(f"   行数: {response.result.row_count}")

    return "\n".join(lines)


def _print_trace(response: AgentResponse, verbose: bool = False):
    """打印执行追踪日志（verbose 模式）"""
    if not verbose:
        return
    print("\n--- trace ---")
    for line in response.trace:
        print(f"  {line}")
    print("--- trace ---\n")


def run_repl(
    agent_config_path: str = "config/agent_config.yml",
    tianshu_config_path: str = "config/tianshu_target.yml",
    verbose: bool = False,
):
    """
    Agent 交互主循环。

    处理三种 AgentResponse 状态：
        - clarification_needed=True → 打印反问，等待用户澄清后重新问
        - refusal=True              → 打印拒绝原因，回到输入状态
        - 正常                       → 打印中文解释 + 元信息
    """
    # 初始化 Agent
    setup_console_encoding()
    agent = Text2SQLAgent(
        agent_config_path=agent_config_path,
        tianshu_config_path=tianshu_config_path,
    )
    _print_banner(agent)

    # ── REPL 主循环 ──
    while True:
        try:
            user_input = input("🔍 请输入问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        # ── 调用 Agent ──
        response = agent.ask(user_input)
        _print_trace(response, verbose)

        # ── 处理反问 ──
        if response.clarification_needed:
            print(f"\n⚠️  {response.clarification_message}")
            print()
            # 反问循环：直到用户给出足够明确的问题
            while True:
                try:
                    clarified = input("✏️  请澄清您的问题 > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not clarified:
                    continue

                if clarified.lower() in ("quit", "exit", "q", "cancel"):
                    print("已取消本次查询。")
                    break

                # 用澄清后的问题再次调用 Agent
                response = agent.ask(clarified)
                _print_trace(response, verbose)

                # 如果仍然需要反问，继续循环
                if response.clarification_needed:
                    print(f"\n⚠️  {response.clarification_message}")
                    print()
                    continue

                # 如果被拒绝了
                if response.refusal:
                    print(f"\n🚫 {response.refusal_reason}")
                    break

                # 正常回答
                print(_format_answer(response))
                break
            continue  # 回到主输入循环

        # ── 处理拒绝 ──
        if response.refusal:
            print(f"\n🚫 {response.refusal_reason}")
            continue

        # ── 正常回答 ──
        print(_format_answer(response))
        print()

    agent.close()


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    run_repl(verbose=verbose)
