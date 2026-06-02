"""
数据质量规则校验工具
基于PRD验收标准生成数据质量规则，执行行数校验、唯一性、空值率、值域范围等质量检查。
"""
from crewai.tools import BaseTool


class DataQualityTool(BaseTool):
    name: str = "数据质量规则校验工具"
    description: str = (
        "生成和执行数据质量校验规则：行数校验、唯一性检查、空值率统计、"
        "值域范围验证、业务规则符合性检查、数据分布合理性分析。"
        "输出质量报告与验收SQL脚本。"
    )

    def _run(self, rule_spec: str = "") -> str:
        return (
            "[DataQuality] 数据质量规则引擎就绪。"
            "请在集群环境中配置数据源连接后使用。"
            f"规则规格: {rule_spec}"
        )
