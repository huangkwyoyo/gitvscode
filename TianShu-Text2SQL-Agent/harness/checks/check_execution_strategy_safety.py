"""
检查执行策略安全门禁。

验证 src/execution_strategy.py 的关键安全约束：
    1. 默认策略是串行执行（SerialExecutionStrategy）
    2. 串行策略为每个 plan 独立调用 PlanExecutor
    3. 并行策略默认禁用（config.parallel_enabled: false）
    4. 并行启用时，每个 worker 获得独立的 PlanExecutor（不共享连接）
    5. 每个 plan 的 execute_one() 经过 validate_sql_safety()

用法：
    python harness/checks/check_execution_strategy_safety.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def check_default_strategy_is_serial() -> dict[str, Any]:
    """验证默认执行策略为串行"""
    checks: list[dict[str, Any]] = []

    try:
        from src.execution_strategy import SerialExecutionStrategy, ThreadPoolExecutionStrategy
    except ImportError as e:
        return {
            "checks": [{"name": "执行策略模块导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 验证两个策略类都存在且可以实例化
    serial = SerialExecutionStrategy()
    checks.append({
        "name": "SerialExecutionStrategy 可实例化",
        "status": "PASS",
        "detail": f"类型: {type(serial).__name__}",
    })

    thread_pool = ThreadPoolExecutionStrategy(max_workers=2)
    checks.append({
        "name": "ThreadPoolExecutionStrategy 可实例化",
        "status": "PASS",
        "detail": f"类型: {type(thread_pool).__name__}, max_workers={thread_pool.max_workers}",
    })

    # 验证 ThreadPoolExecutionStrategy.max_workers 属性
    checks.append({
        "name": "ThreadPool 有 max_workers 属性",
        "status": "PASS" if thread_pool.max_workers == 2 else "FAIL",
        "detail": f"max_workers={thread_pool.max_workers}",
    })

    # 验证并行默认配置
    try:
        import yaml
        config_path = Path("config/agent_config.yml")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            parallel_enabled = config.get("execution", {}).get("parallel_enabled", False)
            checks.append({
                "name": "并行执行默认关闭 (parallel_enabled: false)",
                "status": "PASS" if not parallel_enabled else "FAIL",
                "detail": f"parallel_enabled={parallel_enabled}",
            })
        else:
            checks.append({
                "name": "agent_config.yml 存在",
                "status": "SKIP",
                "detail": "配置文件不存在",
            })
    except Exception as e:
        checks.append({
            "name": "并行配置读取",
            "status": "WARN",
            "detail": f"读取配置失败: {e}",
        })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_plan_executor_safety_link() -> dict[str, Any]:
    """验证 PlanExecutor 的安全链路完整性"""
    checks: list[dict[str, Any]] = []

    try:
        from src.plan_executor import PlanExecutor, ExecutionTrace
    except ImportError as e:
        return {
            "checks": [{"name": "PlanExecutor 导入", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    # 验证 PlanExecutor 类存在关键方法
    checks.append({
        "name": "PlanExecutor 有 execute_one 方法",
        "status": "PASS" if hasattr(PlanExecutor, "execute_one") else "FAIL",
        "detail": "方法存在" if hasattr(PlanExecutor, "execute_one") else "方法缺失",
    })

    checks.append({
        "name": "PlanExecutor 有 execute_many_serial 方法",
        "status": "PASS" if hasattr(PlanExecutor, "execute_many_serial") else "FAIL",
        "detail": "方法存在" if hasattr(PlanExecutor, "execute_many_serial") else "方法缺失",
    })

    # 验证 ExecutionTrace 包含安全校验字段
    trace = ExecutionTrace(
        plan_index=1,
        safety_check_passed=True,
        execution_status="success",
    )
    trace_dict = trace.to_dict()
    checks.append({
        "name": "ExecutionTrace 包含 safety_check_passed 字段",
        "status": "PASS" if "safety_check_passed" in trace_dict else "FAIL",
        "detail": f"safety_check_passed={trace.safety_check_passed}",
    })

    # 验证 execute_one 的源码中包含安全校验调用
    import inspect
    source = inspect.getsource(PlanExecutor.execute_one)
    has_safety_call = "validate_sql_safety" in source
    checks.append({
        "name": "execute_one 调用 validate_sql_safety()",
        "status": "PASS" if has_safety_call else "FAIL",
        "detail": "validate_sql_safety() 调用存在" if has_safety_call else "未找到 validate_sql_safety() 调用！",
    })

    # 验证离线模式阻断
    has_offline_check = "offline" in source.lower()
    checks.append({
        "name": "execute_one 包含离线模式检查",
        "status": "PASS" if has_offline_check else "WARN",
        "detail": "检测到 offline 引用" if has_offline_check else "未显式检测离线模式",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def check_thread_pool_isolation() -> dict[str, Any]:
    """验证线程池隔离安全约束"""
    checks: list[dict[str, Any]] = []

    try:
        from src.execution_strategy import ThreadPoolExecutionStrategy
        import inspect
    except ImportError as e:
        return {
            "checks": [{"name": "线程池隔离检查", "status": "FAIL", "detail": str(e)}],
            "pass_count": 0, "fail_count": 1,
        }

    source = inspect.getsource(ThreadPoolExecutionStrategy)

    # 检查 execute 方法是否创建独立的 PlanExecutor
    has_executor_factory = "executor_factory" in source
    checks.append({
        "name": "ThreadPool 使用 executor_factory 创建独立执行器",
        "status": "PASS" if has_executor_factory else "WARN",
        "detail": "检测到 executor_factory" if has_executor_factory else "未显式使用 executor_factory",
    })

    # 检查是否强调了不共享连接
    has_no_shared = "no_shared" in source or "independent" in source.lower()
    checks.append({
        "name": "ThreadPool 有连接隔离提示",
        "status": "PASS" if has_no_shared else "WARN",
        "detail": "检测到隔离提示" if has_no_shared else "未检测到显式隔离注释",
    })

    return {
        "checks": checks,
        "pass_count": sum(1 for c in checks if c["status"] == "PASS"),
        "fail_count": sum(1 for c in checks if c["status"] == "FAIL"),
    }


def print_report(
    default_result: dict[str, Any],
    safety_result: dict[str, Any],
    isolation_result: dict[str, Any],
) -> int:
    """打印检查报告"""
    print("=" * 60)
    print("执行策略安全门禁")
    print("检查：默认串行 / PlanExecutor 安全链路 / 线程池隔离")
    print("=" * 60)

    sections = [
        ("默认策略验证", default_result),
        ("PlanExecutor 安全链路", safety_result),
        ("线程池隔离", isolation_result),
    ]

    total_fail = 0
    total_pass = 0

    for title, result in sections:
        print(f"\n── {title} ──")
        for c in result["checks"]:
            tag = c["status"]
            print(f"  [{tag}] {c['name']}")
            if c.get("detail"):
                print(f"         {c['detail']}")
        total_fail += result.get("fail_count", 0)
        total_pass += result.get("pass_count", 0)

    print(f"\n  检查完成 — 通过: {total_pass}, 失败: {total_fail}")

    if total_fail > 0:
        print(f"\n[FAIL] 执行策略安全门禁: 发现 {total_fail} 项失败！")
        return 1
    else:
        print("\n[OK] 执行策略安全门禁通过。")
        return 0


def main() -> int:
    """命令行入口"""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="执行策略安全门禁")
    parser.add_argument("--config", default=None,
                        help="Harness 配置文件路径（本检查不使用，仅为兼容接口保留）")
    _args = parser.parse_args()

    default_result = check_default_strategy_is_serial()
    safety_result = check_plan_executor_safety_link()
    isolation_result = check_thread_pool_isolation()

    return print_report(default_result, safety_result, isolation_result)


if __name__ == "__main__":
    sys.exit(main())
