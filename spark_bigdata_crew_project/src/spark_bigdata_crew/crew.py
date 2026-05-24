import logging
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from src.spark_bigdata_crew.tools import *
from config.llm_client import get_llm, get_llm_info

logger = logging.getLogger(__name__)


@CrewBase
class SparkBigDataEnterpriseCrew:
    """
    企业终版Spark大数据多智能体调度核心
    规范：yaml配置驱动 | 装饰器注册 | 全局LLM绑定 | 顺序流水线 | 全工具白名单调用
    一套代码通吃：GPT / DeepSeek / Qwen / GLM / Kimi / Ollama / 自定义中转API
    """
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        self.llm = get_llm()
        info = get_llm_info()
        logger.info("Crew LLM绑定: %s (%s) -> %s", info["provider_name"], info["provider"], info["model"])

    # ============================================================
    # 1. 需求解析智能体：PRD解析、字段抽取、业务规则校验
    # ============================================================
    @agent
    def requirement_analyst_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[DemandFieldAnalyzeTool(), BusinessRuleVerifyTool()]
        )

    # ============================================================
    # 2. 数据建模智能体：多源库连接、表结构拉取、元数据同步
    # ============================================================
    @agent
    def data_modeling_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[DBConnectionTool(), TableSchemaTool()]
        )

    # ============================================================
    # 3. 架构优化智能体：Spark代码规范、性能预优化、规避数据倾斜
    # ============================================================
    @agent
    def spark_architect_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[CodeOptimizeTool()]
        )

    # ============================================================
    # 4. 代码开发智能体：动态代码生成、版本比对、历史代码记忆、版本迭代
    # ============================================================
    @agent
    def spark_developer_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[SparkCodeGenerateTool(), GitCodeCompareTool(), CodeMemoryTool(), GitCodeVersionTool()]
        )

    # ============================================================
    # 5. 单元测试智能体：语法校验、逻辑自检、故障自愈修复
    # ============================================================
    @agent
    def unit_test_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[CodeVerifyTool(), CodeSelfHealTool()]
        )

    # ============================================================
    # 6. 任务提交智能体：任务封装、参数兜底、环境适配、预检校验
    # ============================================================
    @agent
    def job_submit_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[CodeVerifyTool(), MySQLQueryTool()]
        )

    # ============================================================
    # 7. 数据校验智能体：多源数据查询、多源统一数据校验
    # ============================================================
    @agent
    def data_validator_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[MySQLQueryTool(), MultiDataVerifyTool()]
        )

    # ============================================================
    # 8. 数据巡检智能体：质量复盘、异常汇总、抽样核验
    # ============================================================
    @agent
    def data_inspection_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[MultiDataVerifyTool()]
        )

    # ============================================================
    # 9. 运维SRE智能体：巡检报告、DevOps交付、生产适配、故障自愈
    # ============================================================
    @agent
    def devops_sre_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[CodeSelfHealTool()]
        )

    # ============================================================
    # 10. 文档交付智能体：全自动汇总全链路MCP上下文生成交付文档
    # ============================================================
    @agent
    def document_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[DemandFieldAnalyzeTool(), MultiDataVerifyTool(), GitCodeCompareTool()]
        )

    # ============================================================
    # 任务流水线：11步全链路闭环
    # ============================================================
    @task
    def task_1_source_parse(self): return Task()
    @task
    def task_2_requirement_analysis(self): return Task()
    @task
    def task_3_data_modeling(self): return Task()
    @task
    def task_4_spark_architecture(self): return Task()
    @task
    def task_5_spark_development(self): return Task()
    @task
    def task_6_unit_test(self): return Task()
    @task
    def task_7_job_submit(self): return Task()
    @task
    def task_8_data_validation(self): return Task()
    @task
    def task_9_data_inspection(self): return Task()
    @task
    def task_10_devops_monitor(self): return Task()
    @task
    def task_11_document_generate(self): return Task()

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )
