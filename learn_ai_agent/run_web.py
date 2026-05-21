# 导入可视化框架gradio
import gradio as gr
# 导入核心Agent功能函数
from agent_core import execute_single_data_task, execute_multi_batch_task, reset_agent_memory, agent_memory

# 单任务回调函数：接收前端输入，返回执行结果
def web_run_single_task(demand_text):
    result_msg = execute_single_data_task(demand_text)
    # 拼接所有运行日志
    log_text = "\n".join(agent_memory["run_logs"])
    # 返回结果、日志、数据预览
    return result_msg, log_text, str(agent_memory["final_result"])

# 多任务回调函数：批量执行多个需求
def web_run_multi_task(t1,t2,t3):
    # 过滤空任务
    task_arr = [i for i in [t1,t2,t3] if i.strip()]
    batch_res = execute_multi_batch_task(task_arr)
    log_text = "\n".join(agent_memory["run_logs"])
    return "\n".join(batch_res), log_text

# 重置按钮回调
def web_reset_agent():
    reset_agent_memory()
    return "重置完成，可发起新任务","",""

# 搭建前端网页界面
with gr.Blocks(title="新手专属-MySQL AI智能体平台") as web_app:
    gr.Markdown("# 🚀 Windows新手专属 AI数据智能体")
    gr.Markdown("适配MySQL本地数据库｜AI自动写SQL代码｜自动出Excel｜多任务批量调度")

    # 分页标签栏
    with gr.Tabs():
        # 单任务执行页面（新手常用）
        with gr.TabItem("🔹 单任务一键执行"):
            user_demand = gr.Textbox(label="输入自然语言数据需求", placeholder="示例：统计每天的销售总金额")
            run_btn = gr.Button("一键全自动执行", variant="primary")
            reset_btn = gr.Button("重置智能体")
            result_show = gr.Textbox(label="任务执行结果")
            log_show = gr.Textbox(label="实时运行日志", lines=12)
            data_show = gr.Textbox(label="数据结果预览")

        # 多任务调度页面（进阶练习）
        with gr.TabItem("🔸 多任务批量调度"):
            mt1 = gr.Textbox(label="批量任务1")
            mt2 = gr.Textbox(label="批量任务2")
            mt3 = gr.Textbox(label="批量任务3")
            multi_run_btn = gr.Button("批量顺序执行")
            multi_result = gr.Textbox(label="批量任务汇总结果")
            multi_log = gr.Textbox(label="批量执行全局日志", lines=12)

    # 绑定按钮点击事件
    run_btn.click(web_run_single_task, inputs=user_demand, outputs=[result_show,log_show,data_show])
    reset_btn.click(web_reset_agent, outputs=[result_show,log_show,data_show])
    multi_run_btn.click(web_run_multi_task, inputs=[mt1,mt2,mt3], outputs=[multi_result,multi_log])

# 启动网页服务
if __name__ == "__main__":
    # 固定端口，浏览器直接打开
    web_app.launch(server_name="0.0.0.0", server_port=8500, inbrowser=True)