from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from src.skills.data_source_skill import DataSourceSkill

class DBConnInput(BaseModel):
    ds_type: str = Field(description="数据源类型：hive/mysql/sqlserver/oracle")

class DBConnectionTool(BaseTool):
    name = "多源数据库连接工具"
    description = "统一适配四大数据源，完成连接初始化与配置加载"
    args_schema: Type[DBConnInput] = DBConnInput

    def _run(self, ds_type: str):
        """加载指定数据源配置并脱敏返回（隐藏密码等敏感字段）"""
        try:
            config = DataSourceSkill.get_ds_config(ds_type)
            safe_config = {k: ("****" if k in ("password", "service") else v) for k, v in config.items()}
            return f"✅ {ds_type} 数据源配置加载成功，配置信息：{str(safe_config)}"
        except Exception as e:
            return f"❌ 数据源连接失败：{str(e)}"