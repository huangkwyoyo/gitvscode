import sys
from src.logger import logger
from src.resilience import retry, load_checkpoint, clear_checkpoint, save_checkpoint
from src.spark_bigdata_crew.crew import SparkBigDataEnterpriseCrew
from src.mcp.context_protocol import mcp


def run(user_prd: str = "", resume: bool = False):
    """
    全局流水线统一调度入口

    Args:
        user_prd: 用户PRD需求文档内容
        resume: 是否从上次检查点恢复（断点续跑）
    """
    if resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            logger.info("从检查点恢复: task_%d (%s)", checkpoint["task_index"], checkpoint["task_name"])
            mcp.set("_resume_checkpoint", checkpoint)
        else:
            logger.warning("未找到检查点，将从头开始执行")

    mcp.clear()
    logger.info("=" * 60)
    logger.info("Spark全链路多智能体企业级研发流水线启动")
    logger.info("四数据源适配 | 多模态PRD解析 | MCP全局调度 | 11步闭环")
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
        result = _kickoff()
        logger.info("流水线执行完成")
        clear_checkpoint()
        return result
    except Exception as e:
        save_checkpoint(task_index=0, task_name="pipeline_entry")
        logger.error("流水线执行失败: %s", str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
