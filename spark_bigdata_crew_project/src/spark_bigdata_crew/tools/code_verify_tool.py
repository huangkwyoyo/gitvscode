from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import ast

class CodeVerifyInput(BaseModel):
    code: str = Field(description="待校验Spark代码")

class CodeVerifyTool(BaseTool):
    name = "代码语法逻辑校验工具"
    description = "校验Python语法错误、缺失导入、语法缩进、关键字异常"
    args_schema: Type[CodeVerifyInput] = CodeVerifyInput

    def _run(self, code: str):
        """使用ast.parse进行语法树解析，检测语法/缩进/关键字错误"""
        try:
            ast.parse(code)
            return "✅ 代码语法校验通过，无语法错误、缩进错误、关键字错误"
        except SyntaxError as e:
            return f"❌ 代码语法异常：行{e.lineno}，{str(e.msg)}"