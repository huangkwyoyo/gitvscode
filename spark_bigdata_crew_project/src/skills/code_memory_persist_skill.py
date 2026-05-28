"""
Git版本迭代&持久化技能【企业终版】
MCP写入：git_latest_version、spark_final_code、git_old_code、git_diff
废弃JSON伪存储，实现真实Git仓库、Commit记录、Diff比对、多轮重复推理优化
"""
import os
import time
import subprocess
from pathlib import Path
from src.mcp.context_protocol import mcp

GIT_REPO_PATH = "./spark_code_git_repo"
CODE_FILE_NAME = "spark_production_task.py"
Path(GIT_REPO_PATH).mkdir(exist_ok=True)

class GitCodeVersionSkill:
    """企业级Git代码版本管理技能：初始化仓库、保存代码、获取版本、比对差异"""

    @staticmethod
    def _exec_git_cmd(cmd: list) -> tuple[bool, str]:
        """执行Git命令，返回(成功标志, 输出/错误信息)"""
        try:
            res = subprocess.run(
                cmd, cwd=GIT_REPO_PATH, capture_output=True, text=True, encoding="utf-8"
            )
            return (True, res.stdout.strip()) if res.returncode == 0 else (False, res.stderr.strip())
        except Exception as e:
            return False, str(e)

    @staticmethod
    def init_git_repo() -> str:
        """初始化本地Git仓库，配置user信息和.gitignore规则"""
        if os.path.exists(os.path.join(GIT_REPO_PATH, ".git")):
            return "Git仓库已就绪"
        GitCodeVersionSkill._exec_git_cmd(["git", "init"])
        GitCodeVersionSkill._exec_git_cmd(["git", "config", "user.name", "SparkAI-Enterprise"])
        GitCodeVersionSkill._exec_git_cmd(["git", "config", "user.email", "spark@enterprise.com"])
        ignore = "__pycache__/\n*.log\n*.tmp\n.DS_Store\noutput/"
        with open(os.path.join(GIT_REPO_PATH, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(ignore)
        return "✅ 企业Git版本仓库初始化完成"

    @staticmethod
    def save_code_to_git(code: str, desc: str = "Spark代码迭代升级") -> str:
        """将代码写入文件并提交到Git仓库，MCP缓存最新代码和版本时间"""
        GitCodeVersionSkill.init_git_repo()
        code_path = os.path.join(GIT_REPO_PATH, CODE_FILE_NAME)
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"[{timestamp}] {desc}"
        GitCodeVersionSkill._exec_git_cmd(["git", "add", "."])
        success, msg = GitCodeVersionSkill._exec_git_cmd(["git", "commit", "-m", commit_msg])

        if success:
            mcp.set("git_latest_version", timestamp)
            mcp.set("spark_final_code", code)
            return f"✅ Git版本提交成功｜版本时间：{timestamp}"
        return f"⚠️ 代码无变更，无需重复提交：{msg}"

    @staticmethod
    def get_latest_code() -> str:
        """从Git仓库读取最新提交的代码内容"""
        code_path = os.path.join(GIT_REPO_PATH, CODE_FILE_NAME)
        if not os.path.exists(code_path):
            return ""
        with open(code_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def get_diff() -> str:
        """比对工作区与HEAD的差异，返回统一的diff文本"""
        _, diff = GitCodeVersionSkill._exec_git_cmd(["git", "diff", "HEAD"])
        return diff if diff else "首次生成，无历史版本差异"

    @staticmethod
    def iterate_optimize(new_code: str) -> str:
        """结合历史稳定版本和新代码的Diff，构造多轮重复推理优化Prompt"""
        old_code = GitCodeVersionSkill.get_latest_code()
        if not old_code:
            return new_code

        diff = GitCodeVersionSkill.get_diff()
        mcp.set("git_old_code", old_code)
        mcp.set("git_diff", diff)

        iterate_prompt = f"""
【Git历史稳定版本代码】
{old_code}

【本轮新生成代码】
{new_code}

【版本差异Diff】
{diff}

请按照企业迭代标准重复推理优化：
1、保留历史版本稳定无BUG的核心逻辑、资源配置、容错处理
2、融合本轮新业务需求逻辑
3、修复语法隐患、性能问题、数据倾斜、空值异常
4、叠加Spark生产最优优化规则
5、输出最终可直接上线的融合迭代代码
"""
        return iterate_prompt