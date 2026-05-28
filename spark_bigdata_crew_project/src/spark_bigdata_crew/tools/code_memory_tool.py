from crewai.tools import BaseTool
from src.skills.code_memory_persist_skill import GitCodeVersionSkill

class CodeMemoryTool(BaseTool):
    name = "代码版本记忆工具"
    description = "读取Git仓库最新稳定版本代码，用于迭代参考与回滚"

    def _run(self):
        """返回Git仓库中最新的稳定版本代码（首次生成为空则提示）"""
        latest_code = GitCodeVersionSkill.get_latest_code()
        if not latest_code:
            return "暂无历史版本代码，为首次生成"
        return f"✅ 读取历史稳定版本代码成功：\n{latest_code}"