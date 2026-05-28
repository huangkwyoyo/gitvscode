import logging
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from src.spark_bigdata_crew.tools import *
from config.llm_client import get_llm, get_llm_info

logger = logging.getLogger(__name__)


@CrewBase
class SparkBigDataEnterpriseCrew:
    """
    生产级Spark大数据多智能体调度核心
    6 Agent | 8 Task + 3 Gate | LangGraph流程编排 | Hive/HDFS数据源
    一套代码通吃：GPT / DeepSeek / Qwen / GLM / Kimi / Ollama / 自定义中转API
    """
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self):
        self.llm = get_llm()
        info = get_llm_info()
        logger.info("Crew LLM绑定: %s (%s) -> %s", info["provider_name"], info["provider"], info["model"])

    # ============================================================
    # 1. 需求分析智能体：PRD解析、需求澄清、指标口径、验收条件
    # ============================================================
    @agent
    def requirement_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[DemandFieldAnalyzeTool(), BusinessRuleVerifyTool()]
        )

    # ============================================================
    # 2. 元数据管理智能体：Hive Metastore/HDFS元数据读取、字段校验、血缘约束
    # ============================================================
    @agent
    def metadata_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[HiveMetastoreTool(), HDFSTool()]
        )

    # ============================================================
    # 3. 数仓建模智能体：ODS/DWD/DWS/ADS建模、字段映射、分区和存储设计
    # ============================================================
    @agent
    def modeling_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[TableSchemaTool(), HiveMetastoreTool()]
        )

    # ============================================================
    # 4. Spark工程智能体：PySpark代码生成、参数化、性能建议、提交脚本
    # ============================================================
    @agent
    def spark_engineer_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[SparkCodeGenerateTool(), CodeOptimizeTool(), GitCodeVersionTool()]
        )

    # ============================================================
    # 5. 质量保障智能体：静态检查、单元测试、数据质量规则、运行前校验
    # ============================================================
    @agent
    def quality_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[CodeVerifyTool(), DataQualityTool()]
        )

    # ============================================================
    # 6. 交付归档智能体：文档、版本记录、运行报告、交付物汇总
    # ============================================================
    @agent
    def delivery_agent(self) -> Agent:
        return Agent(
            llm=self.llm,
            tools=[DemandFieldAnalyzeTool(), DataQualityTool(), GitCodeVersionTool()]
        )

    # ============================================================
    # 任务流水线：8任务 + 3审批Gate
    # ============================================================
    @task
    def task_1_requirement_analysis(self): return Task()

    @task
    def task_2_metadata_validation(self): return Task()

    @task
    def gate_1_requirement_data_confirm(self): return Task()

    @task
    def task_3_field_mapping(self): return Task()

    @task
    def task_4_data_modeling(self): return Task()

    @task
    def gate_2_model_confirm(self): return Task()

    @task
    def task_5_spark_development(self): return Task()

    @task
    def task_6_code_quality_check(self): return Task()

    @task
    def gate_3_code_approval(self): return Task()

    @task
    def task_7_quality_report(self): return Task()

    @task
    def task_8_delivery_archive(self): return Task()

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )


def build_langgraph_workflow():
    """
    基于LangGraph构建生产级工作流状态机。
    在CrewAI任务链之上增加：
      - 状态持久化（run_id + state manifest + artifact store）
      - 3道人工审批Gate（条件路由）
      - 校验失败阻断与回滚路径
      - 断点续跑支持
    """
    try:
        from src.workflow.graph import create_workflow_graph
        from src.workflow.state import PipelineState
        return create_workflow_graph()
    except ImportError:
        logger.warning("LangGraph未安装，回退到CrewAI原生顺序流程。安装: pip install langgraph")
        return None
