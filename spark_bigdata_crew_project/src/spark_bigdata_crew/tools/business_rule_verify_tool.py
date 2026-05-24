from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from src.skills.data_verify_skill import DataQualityVerifySkill

class RuleVerifyInput(BaseModel):
    df_path: str = Field(description="数据文件路径/Hive表名")
    rule_expr: str = Field(description="业务校验规则表达式")

class BusinessRuleVerifyTool(BaseTool):
    name = "业务规则校验工具"
    description = "自定义业务规则校验，适配各类业务指标合规性检测"
    args_schema: Type[RuleVerifyInput] = RuleVerifyInput

    def _run(self, df_path: str, rule_expr: str):
        # 简化生产调用
        res = DataQualityVerifySkill.business_rule_check(None, rule_expr)
        return f"📊 业务规则校验结果：\n{str(res)}"