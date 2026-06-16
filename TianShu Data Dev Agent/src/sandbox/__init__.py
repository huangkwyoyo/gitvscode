"""
开发环境只读执行器——数据执行边界（边界 2）的唯一入口。

双执行通道：
  - executor.py: DuckDB SQL 执行（已实现）
  - spark_executor.py: PySpark DSL 执行（Phase 3 实现，当前为桩）

安全约束：
  - 所有执行必须 read_only=True
  - 单次查询超时 30s（SQL）/ 60s（Spark）
  - 只有通过防线 2 验证的代码才能进入此模块
"""

from .executor import execute_sql
from .spark_executor import execute_spark_dsl

__all__ = ["execute_sql", "execute_spark_dsl"]
