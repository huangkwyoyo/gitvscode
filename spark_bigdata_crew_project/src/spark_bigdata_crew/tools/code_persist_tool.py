from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from src.skills.code_memory_persist_skill import GitCodeVersionSkill

class GitCodeIterateInput(BaseModel):
    code_content: str = Field(description="本轮新生成Spark代码")
    iterate_desc: str = Field(default="Spark生产代码迭代优化", description="迭代版本说明")

class GitCodeVersionTool(BaseTool):
    name: str = "Git代码版本迭代工具"
    description: str = "企业级Git版本管理，实现代码迭代、版本留存、差异比对、多轮重复推理优化"
    args_schema: Type[GitCodeIterateInput] = GitCodeIterateInput

    def _run(self, code_content: str, iterate_desc: str = "Spark生产代码迭代优化"):
        iterate_code = GitCodeVersionSkill.iterate_optimize(code_content)
        commit_res = GitCodeVersionSkill.save_code_to_git(iterate_code, iterate_desc)
        diff_res = GitCodeVersionSkill.get_diff()
        return f"{commit_res}\n【版本差异】\n{diff_res}\n【迭代后最终代码】\n{iterate_code}"