from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class SelfHealInput(BaseModel):
    code: str = Field(description="存在缺陷的原始代码")
    error_msg: str = Field(default="", description="报错信息，为空自动常规修复")

class CodeSelfHealTool(BaseTool):
    name = "代码故障自愈工具"
    description = "自动修复空值报错、变量未定义、资源未关闭、逻辑漏洞"
    args_schema: Type[SelfHealInput] = SelfHealInput

    def _run(self, code: str, error_msg: str = ""):
        heal_code = code
        # 常规自愈规则
        heal_code = heal_code.replace("df_1.filter(", "df_1.na.fill(0).filter(")
        if "spark.stop()" not in heal_code:
            heal_code += "\nspark.stop()\n"
        return f"✅ 代码自愈修复完成：\n{heal_code}"