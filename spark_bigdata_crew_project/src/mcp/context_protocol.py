"""
MCP(Model Context Protocol) 企业级模型上下文协议
全局唯一单例 | 预设上下文KEY防丢失 | 读取带默认值 | 全链路状态穿透
解决：多Agent上下文割裂、重复推理、参数丢失、空值报错、断点续跑
"""
from typing import Dict, Any, Optional


class MCPContext:
    """单例 + 预设上下文 + 安全获取 + 全局共享"""
    _instance: Optional["MCPContext"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_default_context()
        return cls._instance

    def _init_default_context(self):
        """初始化全流程标准上下文（避免key不存在报错）"""
        self._context: Dict[str, Any] = {
            "user_prd": "",
            "data_source_type": "mysql",
            "table_list": [],
            "table_schema_info": "",
            "field_analysis_result": "",
            "spark_code_raw": "",
            "spark_code_optimized": "",
            "test_report": "",
            "data_verify_result": "",
            "inspection_report": "",
            "devops_report": "",
            "final_doc": ""
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


# 全局唯一单例（整个项目共用这一个）
mcp = MCPContext()