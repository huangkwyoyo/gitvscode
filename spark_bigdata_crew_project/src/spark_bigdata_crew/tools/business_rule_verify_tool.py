from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional
from src.skills.data_verify_skill import DataQualityVerifySkill
from src.mcp.context_protocol import mcp


class RuleVerifyInput(BaseModel):
    rule_expr: str = Field(description="业务校验规则表达式，如 col('amount') > 0")
    df_path: Optional[str] = Field(None, description="数据文件路径/Hive表名，为空时做语法记录")


class BusinessRuleVerifyTool(BaseTool):
    name: str = "业务规则校验工具"
    description: str = "自定义业务规则校验，适配各类业务指标合规性检测，支持仅语法记录模式"
    args_schema: Type[RuleVerifyInput] = RuleVerifyInput

    def _run(self, rule_expr: str, df_path: str = None):
        res = DataQualityVerifySkill.business_rule_check(None, rule_expr)
        mcp.set("business_rule_result", res)
        return f"📊 业务规则校验结果：\n{str(res)}"