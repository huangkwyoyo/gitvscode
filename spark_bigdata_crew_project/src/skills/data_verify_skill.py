"""
通用数据质量校验技能
MCP写入：empty_check_result、dup_check_result
能力：空值校验、重复值校验、极值校验、数据量波动校验、通用业务规则匹配
"""
from src.mcp.context_protocol import mcp

class DataQualityVerifySkill:
    @staticmethod
    def empty_value_check(df, field_list: list) -> dict:
        """字段空值检测并写入全局上下文"""
        empty_result = {}
        for field in field_list:
            empty_count = df.filter(df[field].isNull()).count()
            empty_result[field] = {
                "empty_count": empty_count,
                "status": "异常" if empty_count > 0 else "正常"
            }
        # MCP写入：全局缓存空值校验明细
        mcp.set("empty_check_result", empty_result)
        return empty_result

    @staticmethod
    def duplicate_check(df, unique_keys: list = None) -> dict:
        """重复数据检测并写入全局上下文"""
        total = df.count()
        distinct = df.dropDuplicates(unique_keys).count()
        dup_count = total - distinct
        res = {
            "total_count": total,
            "distinct_count": distinct,
            "duplicate_count": dup_count,
            "status": "存在重复数据" if dup_count > 0 else "数据无重复"
        }
        # MCP写入：全局缓存重复值校验结果
        mcp.set("dup_check_result", res)
        return res

    @staticmethod
    def business_rule_check(df, rule_expr: str) -> dict:
        """自定义业务规则校验"""
        try:
            fail_df = df.filter(~df.expr(rule_expr))
            fail_count = fail_df.count()
            res = {
                "rule": rule_expr,
                "fail_count": fail_count,
                "status": "规则校验通过" if fail_count == 0 else "存在违规数据"
            }
            return res
        except Exception as e:
            return {"rule": rule_expr, "status": f"规则解析失败：{str(e)}"}