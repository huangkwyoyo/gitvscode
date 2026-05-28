"""
启动前配置校验模块
校验：.env完整性 | YAML配置有效性 | Hive/Spark环境就绪 | 输出目录就绪
"""
import os
import logging

logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = {
    "OPENAI_API_KEY": "LLM API密钥",
}

OPTIONAL_ENV_VARS = {
    "OPENAI_API_BASE": "LLM API基础URL",
    "MODEL_NAME": "LLM模型名称",
}

HIVE_ENV_VARS = {
    "HIVE_HOST": "Hive Metastore主机地址",
    "HIVE_PORT": "Hive Metastore端口",
    "HIVE_USER": "Hive用户名",
}

HDFS_ENV_VARS = {
    "HDFS_NAMENODE": "HDFS NameNode地址",
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
    "artifacts",
]


def validate_env() -> list[str]:
    warnings = []
    for var, desc in REQUIRED_ENV_VARS.items():
        if not os.getenv(var):
            warnings.append(f"缺少环境变量: {var} ({desc})")

    missing_hive = [v for v, d in HIVE_ENV_VARS.items() if not os.getenv(v)]
    if len(missing_hive) == len(HIVE_ENV_VARS):
        warnings.append("所有Hive环境变量均未配置，元数据校验功能需配置后使用")
    elif missing_hive:
        for v in missing_hive:
            warnings.append(f"缺少Hive环境变量: {v} ({HIVE_ENV_VARS[v]})")

    missing_hdfs = [v for v, d in HDFS_ENV_VARS.items() if not os.getenv(v)]
    if missing_hdfs:
        for v in missing_hdfs:
            warnings.append(f"缺少HDFS环境变量: {v} ({HDFS_ENV_VARS[v]})")

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
    base_dir = os.path.dirname(os.path.dirname(__file__))
    required_yamls = [
        "config/agents.yaml",
        "config/tasks.yaml",
        "config/workflow.yaml",
        "config/hive.yaml",
        "config/spark.yaml",
    ]
    for yaml_path in required_yamls:
        full_path = os.path.join(base_dir, yaml_path)
        if not os.path.exists(full_path):
            warnings.append(f"配置文件不存在: {yaml_path}")
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

    critical_errors = [w for w in all_warnings if "OPENAI_API_KEY" in w]
    if critical_errors:
        logger.error("存在关键配置缺失，流水线可能无法正常运行")
        return False
    return True
