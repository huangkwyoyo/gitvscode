from src.spark_bigdata_crew.crew import SparkBigDataEnterpriseCrew
from src.mcp.context_protocol import mcp

def run(user_prd: str = ""):
    """
    全局流水线统一调度入口
    核心保障：每次任务强制清空MCP上下文，杜绝多轮任务数据污染、参数残留
    """
    mcp.clear()
    print("=" * 80)
    print("🚀 Spark多源多智能体企业级研发流水线启动（MCP全局调度）")
    print("✅ 四数据源适配 | 多模态PRD解析 | 无幻觉落地 | Skills能力复用")
    print("=" * 80)
    crew = SparkBigDataEnterpriseCrew().crew()
    result = crew.kickoff(inputs={"user_prd": user_prd})
    return result

if __name__ == "__main__":
    run()