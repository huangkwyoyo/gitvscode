from crewai.tools import BaseTool
from src.skills.code_memory_persist_skill import GitCodeVersionSkill

class GitCodeCompareTool(BaseTool):
    name = "Git版本差异比对工具"
    description = "比对当前代码与历史版本差异，输出变更明细"

    def _run(self):
        """执行git diff HEAD获取工作区相对于最新提交的变更"""
        diff = GitCodeVersionSkill.get_diff()
        return f"📝 版本差异比对结果：\n{diff}"