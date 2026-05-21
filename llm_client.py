# 模型统一连接（万能切换）

from openai import OpenAI
import os
from dotenv import load_dotenv

# ===================== 【只改这里！切换模型】=====================
# 可选填写：openai / deepseek / qwen / ollama
SELECT_MODEL_TYPE = "deepseek"  
# =================================================================


# 加载 .env 文件中的环境变量
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
qwen_api_key = os.getenv("QWEN_API_KEY")


# 1. 统一配置字典
MODEL_CONFIG = {
    "openai": {
        "api_key": openai_api_key,
        "base_url": None,
        "model_name": "gpt-4o-mini"
    },
    "deepseek": {
        "api_key": deepseek_api_key,
        "base_url": "https://api.deepseek.com",
        "model_name": "deepseek-chat"
    },
    "qwen": {
        "api_key": qwen_api_key,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-turbo"
    },
    "ollama": {
        "api_key": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model_name": "qwen2.5:14b"  # 换成你本地ollama模型名
    }
}

# 2. 自动读取配置
cfg = MODEL_CONFIG[SELECT_MODEL_TYPE]

# 3. 统一初始化客户端
client_kwargs = {"api_key": cfg["api_key"]}
if cfg["base_url"]:
    client_kwargs["base_url"] = cfg["base_url"]

client = OpenAI(**client_kwargs)
current_model = cfg["model_name"]

# 4. 通用对话函数（所有模型通用）
# 定义聊天函数，prompt用户提问内容，system_content设定AI角色人设，默认返回字符串类型
def llm_chat(prompt: str, system_content: str = "你是专业智能助手，回答简洁易懂") -> str:
    # 调用大模型接口，发起对话请求，接收模型返回的完整响应数据
    response = client.chat.completions.create(
        # 指定当前要调用的大模型名称，从全局配置读取
        model=current_model,
        # 组装对话消息列表，固定对话格式
        messages=[
            # system角色：给AI设定身份、规则、行为准则
            {"role": "system", "content": system_content},
            # user角色：传入用户实际提出的问题/指令
            {"role": "user", "content": prompt}
        ],
        # 温度参数，控制AI创造力 0严谨精准 0.7均衡 1脑洞大
        temperature=0.7
    )
    # 取出第一条回答内容，去除首尾空格换行，精简后返回结果
    return response.choices[0].message.content.strip()

# ===================== 测试运行 =====================
if __name__ == "__main__":
    print(f"✅ 当前调用模型：{SELECT_MODEL_TYPE} | {current_model}")
    res = llm_chat("简单解释什么是AI Agent")
    print("\n🤖 模型回复：")
    print(res)