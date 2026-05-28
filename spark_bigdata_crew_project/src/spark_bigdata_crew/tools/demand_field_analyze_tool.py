from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import re

class DemandAnalyzeInput(BaseModel):
    prd_content: str = Field(description="业务PRD需求文档内容")

class DemandFieldAnalyzeTool(BaseTool):
    name = "PRD需求字段解析工具"
    description = "从PRD自动提取数据源表、计算字段、业务统计逻辑"
    args_schema: Type[DemandAnalyzeInput] = DemandAnalyzeInput

    def _run(self, prd_content: str):
        """通过正则从PRD提取表名列表、字段列表和业务逻辑描述"""
        # 提取表名（匹配数仓分层前缀或t_前缀的表名）
        table_list = re.findall(r"(ods|dwd|dws|ads)_\w+|t_\w+", prd_content)
        # 提取字段名（支持中英文冒号）
        field_list = re.findall(r"字段[:：]\s*([\u4e00-\u9fa5a-zA-Z0-9,_]+)", prd_content)
        # 提取业务逻辑
        logic_list = re.findall(r"逻辑[:：]\s*([^\n]+)", prd_content)

        res = {
            "table_list": list(set(table_list)),
            "field_list": field_list,
            "business_logic": logic_list[0] if logic_list else "常规统计聚合计算"
        }
        return f"✅ PRD解析完成：\n{str(res)}"