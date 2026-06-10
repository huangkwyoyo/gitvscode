"""
TianShu Text2SQL Agent —— 中文问数分析 Agent。

三层 IR 架构：
    QuestionIntent → SQLPlan → SQL → 执行 → 中文解释

用法：
    from src.agent import Text2SQLAgent
    agent = Text2SQLAgent(config_path="config/agent_config.yml")
    answer = agent.ask("2026年Q1曼哈顿每天多少行程？")
"""
