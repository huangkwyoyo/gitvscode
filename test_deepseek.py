import os
from openai import OpenAI
from dotenv import load_dotenv

def test_deepseek_chat():
    """初始化 DeepSeek 客户端并发送一条测试消息"""
    
    # 1. 获取 API Key (建议提前在终端设置好环境变量 DEEPSEEK_API_KEY)

    # 加载 .env 文件中的环境变量
    load_dotenv()

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 错误：未找到环境变量 DEEPSEEK_API_KEY")
        print("   请先在终端运行: $env:DEEPSEEK_API_KEY=\"你的真实密钥\" (PowerShell)")
        return False

    try:
        # 2. 初始化 DeepSeek 客户端
        # 注意：这里复用了 openai 库，但通过 base_url 指向了 DeepSeek 的服务器
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        print("✅ DeepSeek 客户端初始化成功！\n正在向 AI 提问...\n---")

        # 3. 发送对话请求
        response = client.chat.completions.create(
            model="deepseek-chat",  # 指定使用 DeepSeek 的对话模型
            messages=[
                {"role": "system", "content": "你是一个友好的AI助手。"},
                {"role": "user", "content": "你好！请用一句话简单介绍一下你自己。"}
            ],
            stream=True  # 开启流式输出，实现打字机效果
        )

        # 4. 实时打印 AI 的回复（已修复 choices[0] 的索引问题）
        for chunk in response:
            # 增加安全检查：确保 choices 存在且不为空
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                # 确保 content 不是 None 再打印
                if delta.content is not None:
                    print(delta.content, end="", flush=True)
        
        print("\n\n---\n✨ 测试完成！")
        return True

    except Exception as e:
        print(f"\n❌ 调用 DeepSeek API 失败: {e}")
        return False

if __name__ == "__main__":
    test_deepseek_chat()