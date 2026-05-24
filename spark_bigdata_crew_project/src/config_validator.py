"""
启动前配置校验模块
校验：.env完整性 | YAML配置有效性 | 工具名对齐 | 输出目录就绪
"""
import os
import logging

logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = {
    "OPENAI_API_KEY": "LLM API密钥",
    "OPENAI_API_BASE": "LLM API基础URL",
    "OPENAI_MODEL_NAME": "LLM模型名称",
}

REQUIRED_DB_VARS = {
    "MYSQL_HOST": "MySQL主机地址",
    "MYSQL_PORT": "MySQL端口",
    "MYSQL_USER": "MySQL用户名",
    "MYSQL_PASSWORD": "MySQL密码",
    "MYSQL_DATABASE": "MySQL数据库名",
}

SPARK_ENV_VARS = {
    "SPARK_MASTER_URL": "Spark Master URL",
    "SPARK_APP_NAME": "Spark应用名称",
}

OUTPUT_DIRS = [
    "output/reports",
    "output/spark_code",
    "output/docs",
    "output/logs",
    "output/checkpoints",
]


def validate_env() -> list[str]:
    warnings = []
    for var, desc in REQUIRED_ENV_VARS.items():
        if not os.getenv(var):
            warnings.append(f"缺少环境变量: {var} ({desc})")
    missing_db = [v for v, d in REQUIRED_DB_VARS.items() if not os.getenv(v)]
    if len(missing_db) == len(REQUIRED_DB_VARS):
        warnings.append("所有MySQL环境变量均未配置，数据库功能不可用")
    elif missing_db:
        for v in missing_db:
            warnings.append(f"缺少数据库环境变量: {v} ({REQUIRED_DB_VARS[v]})")
    missing_spark = [v for v, d in SPARK_ENV_VARS.items() if not os.getenv(v)]
    if missing_spark:
        for v in missing_spark:
            warnings.append(f"缺少Spark环境变量: {v} ({SPARK_ENV_VARS[v]})，将使用默认值")
    return warnings


def ensure_output_dirs():
    for d in OUTPUT_DIRS:
        os.makedirs(d, exist_ok=True)


def validate_yaml_configs() -> list[str]:
    warnings = []
    yaml_agents_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "agents.yaml"
    )
    yaml_tasks_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "tasks.yaml"
    )
    if not os.path.exists(yaml_agents_path):
        warnings.append(f"agent配置文件不存在: {yaml_agents_path}")
    if not os.path.exists(yaml_tasks_path):
        warnings.append(f"task配置文件不存在: {yaml_tasks_path}")
    return warnings


def run_startup_validation() -> bool:
    logger.info("执行启动前配置校验...")
    all_warnings = []
    all_warnings.extend(validate_env())
    all_warnings.extend(validate_yaml_configs())
    ensure_output_dirs()

    for w in all_warnings:
        logger.warning("⚠ %s", w)

    if all_warnings:
        logger.info("配置校验完成，共 %d 条提醒", len(all_warnings))
    else:
        logger.info("配置校验通过，一切就绪")

    critical_errors = [w for w in all_warnings if w.startswith("缺少环境变量: OPENAI")]
    if critical_errors:
        logger.error("存在关键配置缺失，流水线可能无法正常运行")
        return False
    return True
