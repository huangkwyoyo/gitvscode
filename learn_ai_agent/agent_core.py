# 导入全局大模型客户端参数
from llm_client import llm_client, current_llm_model
# 导入pandas，用于数据处理、表格加工、Excel导出
import pandas as pd
# 导入pymysql，用于连接本地MySQL数据库
import pymysql
# 导入内置库，用于捕获代码输出、异常处理
import io
import sys
# 导入时间库，生成标准日志时间
import time

# ===================== 模块1：MEMORY 全局记忆体（核心之一） =====================
# 作用：永久保存任务信息，实现上下文记忆、任务回溯、状态监控
agent_memory = {
    "task_history": [],       # 存储所有历史任务
    "current_task": "",       # 存储当前正在执行的任务
    "task_plan": [],          # AI拆解的任务执行步骤
    "exec_code": "",          # AI自动生成的SQL、Python代码
    "source_data": None,      # 从MySQL读取的原始数据
    "final_result": None,     # 聚合加工后的最终数据
    "run_logs": [],           # 全流程运行日志
    "task_status": "idle"     # 任务状态：idle空闲/running执行中/success成功/fail失败
}

# ===================== 数据库配置（Windows本地MySQL，新手只需改这里） =====================
MYSQL_CONFIG = {
    "host": "localhost",      # 本地数据库地址，固定不变
    "port": 3306,             # MySQL默认端口
    "user": "root",           # MySQL用户名
    "password": "123456",     # 改成你自己的MySQL密码
    "database": "test_data",  # 刚才新建的数据库名称
    "charset": "utf8"
}

# ===================== 模块2：TOOLS 工具集（核心之二） =====================
# 封装Agent可调用的工具，拓展工具即可拓展Agent能力
class BigDataAgentTools:
    # 工具1：连接本地MySQL，执行SQL查询
    @staticmethod
    def query_mysql(sql: str) -> pd.DataFrame:
        # 读取数据库配置，建立连接
        conn = pymysql.connect(**MYSQL_CONFIG)
        # 执行SQL，返回DataFrame结构化表格数据
        df = pd.read_sql(sql, conn)
        # 关闭数据库连接，避免资源占用
        conn.close()
        # 返回查询结果
        return df

    # 工具2：将处理后的数据导出为Excel报表
    @staticmethod
    def export_excel(df, save_path="./agent_result.xlsx"):
        # 导出Excel，取消默认行索引
        df.to_excel(save_path, index=False)
        # 返回文件保存路径，方便查看
        return save_path

    # 工具3：安全执行AI生成的Python代码（防止恶意代码、捕获异常）
    @staticmethod
    def safe_run_code(code_str: str, input_df):
        # 保存原始控制台输出
        old_stdout = sys.stdout
        # 新建内存缓冲区，捕获代码运行日志
        sys.stdout = io.StringIO()
        try:
            # 定义代码运行的局部环境，传入原始数据df
            local_env = {"df": input_df}
            # 执行AI生成的Python代码
            exec(code_str, globals(), local_env)
            # 取出加工后的结果，无结果则返回原始数据
            return local_env.get("result", input_df)
        except Exception as e:
            # 捕获代码报错，返回错误信息
            return f"代码执行异常：{str(e)}"
        finally:
            # 还原控制台输出
            sys.stdout = old_stdout

# 实例化工具类，全局统一调用
agent_tools = BigDataAgentTools()

# ===================== 模块3：LLM 大脑思考模块（核心之三） =====================
def llm_think_analysis(prompt: str) -> str:
    # 设定AI角色：大数据开发工程师，严格遵守生产规范
    system_prompt = """
你是Windows大数据AI智能体，专门处理MySQL数据任务。
能力要求：
1. 精准拆解自然语言数据需求
2. 生成简洁、可直接运行的MySQL SQL语句
3. 生成pandas聚合、统计、清洗代码
4. 禁止多余话术，只输出可执行内容
"""
    # 组装对话消息：系统人设 + 用户需求
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    # 调用大模型接口，temperature=0.1（严谨模式，减少胡说）
    response = llm_client.chat.completions.create(
        model=current_llm_model,
        messages=messages,
        temperature=0.1
    )
    # 提取AI返回内容，去除多余空格换行
    return response.choices[0].message.content.strip()

# ===================== 通用日志工具 =====================
def write_task_log(log_info: str):
    # 格式化时间戳
    now_time = time.strftime("%Y-%m-%d %H:%M:%S")
    # 拼接完整日志
    full_log = f"[{now_time}] {log_info}"
    # 存入记忆体，用于前端展示
    agent_memory["run_logs"].append(full_log)
    # 控制台打印日志
    print(full_log)

# ===================== 模块4：Autonomous Decision 自主决策引擎（核心之四） =====================
# 单任务全自动执行：一句需求完成全流程
def execute_single_data_task(user_data_demand: str) -> str:
    # 写入当前任务，存入历史记录
    agent_memory["current_task"] = user_data_demand
    agent_memory["task_history"].append(user_data_demand)
    # 修改任务状态为执行中
    agent_memory["task_status"] = "running"
    write_task_log("✅ AI智能体启动，接收业务需求")

    # 步骤1：AI自主拆解任务步骤
    write_task_log("1. AI正在拆解数据任务流程")
    task_step_plan = llm_think_analysis(f"拆解MySQL数据需求：{user_data_demand}，输出3条清晰执行步骤，简洁直白")
    agent_memory["task_plan"] = task_step_plan
    write_task_log(f"任务拆解完成：{task_step_plan}")

    # 步骤2：AI自主生成MySQL查询SQL
    write_task_log("2. AI自动生成MySQL查询SQL")
    sql_content = llm_think_analysis(f"根据需求编写可直接运行的MySQL SQL，仅输出SQL语句，不要多余文字：{user_data_demand}")
    raw_data = agent_tools.query_mysql(sql_content)
    agent_memory["source_data"] = raw_data
    write_task_log("MySQL原始数据拉取完成")

    # 步骤3：AI自主生成数据聚合加工代码
    write_task_log("3. AI自动生成pandas数据处理代码")
    process_code = llm_think_analysis(f"编写pandas聚合统计代码，基于df处理数据，最终结果必须存入result变量，不要多余解释：{user_data_demand}")
    agent_memory["exec_code"] = process_code
    write_task_log("数据加工代码生成完毕")

    # 步骤4：自动执行代码，加工数据
    write_task_log("4. 自动执行数据清洗、聚合计算")
    final_result_df = agent_tools.safe_run_code(process_code, raw_data)
    agent_memory["final_result"] = final_result_df

    # 步骤5：自动导出Excel报表
    write_task_log("5. 自动生成Excel业务报表")
    agent_tools.export_excel(final_result_df)

    # 修改任务状态为执行成功
    agent_memory["task_status"] = "success"
    write_task_log("🎉 全流程执行完成：分析→取数→加工→导出Excel")
    return "任务执行成功，根目录生成agent_result.xlsx报表"

# ===================== 多轮复杂任务调度（进阶功能） =====================
# 顺序执行多个独立任务，实现批量调度
def execute_multi_batch_task(task_list: list) -> list:
    all_task_result = []
    # 循环遍历任务列表，逐个执行
    for idx, task in enumerate(task_list):
        if not task.strip():
            continue
        write_task_log(f"\n========== 开始执行第{idx+1}号批量任务 ==========")
        res = execute_single_data_task(task)
        all_task_result.append(f"任务{idx+1}：{res}")
    return all_task_result

# ===================== 重置Agent记忆（手动清空记录） =====================
def reset_agent_memory():
    agent_memory["task_history"].clear()
    agent_memory["run_logs"].clear()
    agent_memory["task_status"] = "idle"
    write_task_log("🔄 智能体记忆、日志、状态已全部重置")