# test_env.py
"""
环境配置验证脚本
运行此脚本检查所有依赖是否正确安装
"""
from openai import OpenAI
from dotenv import load_dotenv
import os
import sys


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    if version.major == 3 and version.minor >= 10:
        print("  ✓ Python 版本符合要求 (>= 3.10)")
        return True
    else:
        print("  ✗ Python 版本过低，需要 3.10+")
        return False


def check_dotenv():
    """检查 .env 文件和 API Key"""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key and api_key.startswith("sk-"):
        print(f"  ✓ OpenAI API Key 已配置 ({api_key[:10]}...)")
        return True
    elif api_key == "ollama":
        print("  ✓ 使用 Ollama 本地模式")
        return True
    else:
        print("  ✗ 未找到有效的 OPENAI_API_KEY")
        print("    提示：创建 .env 文件并设置 OPENAI_API_KEY=sk-...")
        return False


def check_openai_sdk():
    """检查 OpenAI SDK 是否可用"""
    try:
        from openai import OpenAI
        print("  ✓ OpenAI SDK 已安装")
        return True
    except ImportError:
        print("  ✗ OpenAI SDK 未安装")
        print("    运行: uv add openai")
        return False


def check_ollama():
    """检查 Ollama 是否可用"""
    import urllib.request
    try:
        response = urllib.request.urlopen("http://localhost:11434")
        if response.status == 200:
            print("  ✓ Ollama 服务正在运行 (localhost:11434)")
            return True
    except Exception:
        print("  ⚠ Ollama 服务未运行（如果使用本地模型，请启动它）")
        print("    运行: ollama serve")
        return False
    return False


def test_api_connection():
    """测试 API 连接"""
    from openai import OpenAI

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    # 判断使用 OpenAI 还是 Ollama
    if api_key == "ollama":
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )
        model = "qwen2.5:7b"
    else:
        client = OpenAI(api_key=api_key)
        model = "gpt-4o-mini"

    print(f"\n正在测试连接 (模型: {model})...")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "你好，请回复'连接成功'"}],
            max_tokens=20,
        )
        reply = response.choices[0].message.content.strip()
        print(f"  ✓ 连接成功！模型回复: {reply}")
        return True
    except Exception as e:
        print(f"  ✗ 连接失败: {e}")
        return False


def main():
    print("=" * 50)
    print("AI Agent 实战营 — 环境配置验证")
    print("=" * 50)
    print()

    results = []

    print("[1/4] 检查 Python 版本")
    results.append(check_python_version())
    print()

    print("[2/4] 检查 .env 配置")
    results.append(check_dotenv())
    print()

    print("[3/4] 检查 OpenAI SDK")
    results.append(check_openai_sdk())
    print()

    print("[4/4] 检查 Ollama（可选）")
    check_ollama()  # 可选，不影响结果
    print()

    # 如果前面都通过了，测试 API 连接
    if all(results):
        print("[测试] API 连接测试")
        test_api_connection()
        print()

    # 总结
    print("=" * 50)
    if all(results):
        print("✓ 所有检查通过！环境配置完成！")
    else:
        print("✗ 部分检查未通过，请查看上面的提示并修复")
    print("=" * 50)


if __name__ == "__main__":
    main()