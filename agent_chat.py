# 模型统一连接（万能切换）
from openai import OpenAI
import json

# ===================== 全局对话记忆容器 =====================
# 用来存放完整对话历史，实现上下文连贯聊天
chat_history = []

# ===================== 读取模型配置文件 =====================
def load_llm_config():
    """读取JSON配置文件，统一管理所有大模型密钥与地址"""
    with open("llm_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# 加载配置并初始化客户端
config_data = load_llm_config()
select_model = config_data["use_model"]
model_info = config_data[select_model]

# 初始化统一调用客户端
client = OpenAI(
    api_key=model_info["api_key"],
    base_url=model_info.get("base_url")
)
# 获取当前使用的模型名称
current_model = model_info["model"]


# ===================== 带记忆增强对话函数（Agent专用） =====================
def agent_chat(
    user_input: str,
    system_prompt: str = "你是全能AI智能体，具备思考、分析、总结能力，逻辑清晰回答问题",
    temp: float = 0.7
) -> str:
    """
    AI Agent专用带记忆对话函数
    :param user_input: 用户当前输入提问
    :param system_prompt: 智能体全局人设/行为规则
    :param temp: 创造力温度
    :return: AI整理后的回答内容
    """
    # 1. 将用户最新提问加入历史对话列表
    chat_history.append({"role": "user", "content": user_input})

    # 2. 组装完整请求消息：系统人设 + 全部历史对话
    full_messages = [{"role": "system", "content": system_prompt}] + chat_history

    # 3. 调用大模型生成回答
    resp = client.chat.completions.create(
        model=current_model,
        messages=full_messages,
        temperature=temp
    )

    # 4. 提取AI回复文本并清理多余空白字符
    ai_reply = resp.choices[0].message.content.strip()

    # 5. 将AI回答也存入对话记忆，实现上下文接续
    chat_history.append({"role": "assistant", "content": ai_reply})

    # 6. 返回最终回答
    return ai_reply


# ===================== 辅助工具函数 =====================
def clear_chat_memory():
    """清空历史对话记忆，开启全新一轮对话"""
    chat_history.clear()
    print("✅ 已清空全部对话记忆")


# ===================== 测试运行 =====================
if __name__ == "__main__":
    print(f"🤖 当前启用智能体模型：{select_model} - {current_model}")
    print("输入 quit 退出对话，输入 clear 清空记忆\n")

    while True:
        user_text = input("👤 你：")
        # 退出对话
        if user_text.lower() == "quit":
            print("🤖 AI智能体：对话结束")
            break
        # 清空记忆
        if user_text.lower() == "clear":
            clear_chat_memory()
            continue
        # 调用Agent对话
        res = agent_chat(user_text)
        print(f"🤖 AI智能体：{res}\n")