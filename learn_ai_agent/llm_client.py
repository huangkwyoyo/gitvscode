# 导入OpenAI官方SDK，兼容所有大模型接口
from openai import OpenAI
# 导入json库，用于读取本地配置文件
import json

# 定义函数：读取json配置文件
def load_config():
    # 以只读模式、utf-8编码打开配置文件
    with open("llm_config.json", "r", encoding="utf-8") as f:
        # 将json文件转为Python字典，方便代码读取
        return json.load(f)

# 定义函数：初始化大模型客户端
def init_llm():
    # 加载配置信息
    cfg = load_config()
    # 获取当前启用的模型名称
    use_tag = cfg["use_model"]
    # 获取当前模型的详细参数（密钥、地址、模型名）
    model_info = cfg[use_tag]

    # 初始化客户端基础参数（必填：密钥）
    client_args = {"api_key": model_info["api_key"]}
    # 如果存在自定义接口地址，追加参数
    if model_info.get("base_url"):
        client_args["base_url"] = model_info["base_url"]

    # 生成大模型客户端
    client = OpenAI(**client_args)
    # 返回客户端、模型标签、模型名称
    return client, use_tag, model_info["model"]

# 全局一次性初始化，整个项目共用，避免重复创建客户端
llm_client, model_tag, current_llm_model = init_llm()