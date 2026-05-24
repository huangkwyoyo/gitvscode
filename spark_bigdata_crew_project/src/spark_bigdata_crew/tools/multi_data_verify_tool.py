from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
from src.skills.multi_data_verify_skill import MultiDataVerifySkill

class MultiDataVerifyInput(BaseModel):
    output_type: Optional[str] = Field(None, description="输出类型：hive_table/file，为空自动读取全局参数")
    table_name: Optional[str] = Field(None, description="结果表/文件名称")
    sample_limit: int = Field(100, description="抽样展示行数")
    check_empty: bool = Field(True, description="是否校验空数据")
    check_duplicate: bool = Field(True, description="是否校验重复数据")

class MultiDataVerifyTool(BaseTool):
    name: str = "多源统一数据校验工具"
    description: str = "生产级全场景校验，适配Spark所有主流输出形态，双层参数兜底，杜绝空执行、幻觉代码"
    args_schema: Type[MultiDataVerifyInput] = MultiDataVerifyInput

    def _run(self, output_type=None, table_name=None, sample_limit=100, check_empty=True, check_duplicate=True):
        return MultiDataVerifySkill.verify_by_output_param(
            input_output_type=output_type,
            input_table_name=table_name,
            sample_limit=sample_limit,
            check_empty=check_empty,
            check_duplicate=check_duplicate
        )