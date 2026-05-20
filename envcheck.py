# main.py
from dotenv import load_dotenv
import os

# 加载 .env 文件中的环境变量
load_dotenv()

# 读取 API Key
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("错误：未找到 OPENAI_API_KEY 环境变量")
    print("请创建 .env 文件并设置 API Key")
else:
    print("API Key 已加载！")
    # 注意：不要打印完整的 API Key，只显示前几位
    print(f"Key 前缀: {api_key[:10]}...")pyt