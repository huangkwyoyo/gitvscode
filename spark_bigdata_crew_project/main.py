#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spark全链路多智能体企业级研发流水线 — 全局统一调度入口

功能：
  - 从用户PRD需求生成端到端研发成果
  - 支持检查点断点续跑（resume模式）
  - 自动完成启动校验 → LLM绑定 → CrewAI执行的全流程
  - 失败时自动保存检查点，避免重复劳动

调用方式：
    from main import run
    result = run(user_prd="读取某张表并按XX维度统计")
"""
import sys
from src.logger import logger
from src.resilience import retry, load_checkpoint, clear_checkpoint, save_checkpoint
from src.spark_bigdata_crew.crew import SparkBigDataEnterpriseCrew, build_langgraph_workflow


def run(user_prd: str = "", resume: bool = False):
    """
    生产级流水线统一调度入口

    架构: AI负责生成与推理 + 工具负责校验与执行 + 状态机负责流程 + 人负责关键审批

    Args:
        user_prd: 用户PRD需求文档内容
        resume: 是否从上次检查点恢复（断点续跑）
    """
    if resume:
        # 尝试加载上次失败的检查点，实现断点续跑
        checkpoint = load_checkpoint()
        if checkpoint:
            logger.info("从检查点恢复: task_%d (%s)", checkpoint["task_index"], checkpoint["task_name"])
        else:
            logger.warning("未找到检查点，将从头开始执行")

    logger.info("=" * 60)
    logger.info("Spark大数据生产级多智能体研发流水线启动")
    logger.info("6 Agent | 8 Task + 3 Gate | Hive/HDFS | LangGraph编排")
    logger.info("=" * 60)

    from src.config_validator import run_startup_validation
    run_startup_validation()

    from config.llm_client import get_llm_info
    llm_info = get_llm_info()
    logger.info("LLM配置: %s | 模型: %s | API: %s",
                llm_info["provider_name"], llm_info["model"], llm_info["base_url"])

    @retry(max_attempts=2, delay_seconds=3)
    def _kickoff():
        crew = SparkBigDataEnterpriseCrew().crew()
        return crew.kickoff(inputs={"user_prd": user_prd})

    try:
        # 尝试构建LangGraph工作流（可选增强）
        workflow = build_langgraph_workflow()
        if workflow:
            logger.info("LangGraph工作流已加载，Gate审批模式已启用")
        else:
            logger.info("使用CrewAI原生顺序流程")
        result = _kickoff()
        logger.info("流水线执行完成")
        clear_checkpoint()
        return result
    except Exception as e:
        # 流水线异常时保存检查点，便于后续断点续跑
        save_checkpoint(task_index=0, task_name="pipeline_entry")
        logger.error("流水线执行失败: %s", str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
