"""
MCP(Model Context Protocol) 可选辅助上下文协议
注意：MCP作为可选辅助模块，不作为项目核心状态中心。
生产中的核心状态管理由 src/workflow/state.py + src/workflow/checkpoints.py 负责。
"""
from typing import Dict, Any, Optional


class MCPContext:
    """可选单例上下文（辅助用途，非核心状态中心）"""
    _instance: Optional["MCPContext"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_default_context()
        return cls._instance

    def _init_default_context(self):
        self._context: Dict[str, Any] = {
            "user_prd": "",
            "hive_database": "default",
            "table_list": [],
            "table_schema_info": "",
            "field_analysis_result": "",
            "spark_code_raw": "",
            "spark_code_optimized": "",
            "test_report": "",
            "quality_report": "",
            "final_doc": "",
        }

    def set(self, key: str, value: Any):
        """写入全局上下文（自动支持新增key，无需预定义）"""
        self._context[key] = value

    def get(self, key: str, default: Any = "") -> Any:
        """读取上下文，带默认值以防止空值和KeyError异常"""
        return self._context.get(key, default)

    def clear(self):
        """清空并重置为默认上下文（每次新任务开始前调用以实现隔离）"""
        self._init_default_context()


# 全局单例（可选使用）
mcp = MCPContext()
