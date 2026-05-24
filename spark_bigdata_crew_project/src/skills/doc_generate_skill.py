"""
全自动文档交付可复用技能
汇总全链路MCP上下文生成完整交付文档
MCP写入：final_doc、final_doc_path
能力：无参全自动渲染，读取全链路MCP全局上下文，生成标准化完整项目交付文档
"""
import os
from datetime import datetime
from src.mcp.context_protocol import mcp

OUTPUT_DOC_PATH = "./output/docs"
os.makedirs(OUTPUT_DOC_PATH, exist_ok=True)

class DocGenerateSkill:
    @staticmethod
    def generate_full_doc() -> str:
        """无参全自动生成全链路交付文档，全部读取MCP全局上下文，无需手动传参"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 全自动读取全链路MCP全局上下文，实现零传参生成文档
        doc = f"""
# Spark多智能体全自动研发项目交付文档
## 文档生成时间：{timestamp}

## 一、数据源信息
数据源类型：{mcp.get('data_source_type', '未识别')}
业务数据表：{mcp.get('table_list', '无')}
数据源完整配置：{mcp.get('current_ds_config', '无数据源配置')}

## 二、业务需求说明
{mcp.get('user_prd', '无需求文档内容')}

## 三、表结构元数据信息
{mcp.get('table_schema_info', '未拉取表结构')}

## 四、Spark研发产出代码
### 原始生成代码
{mcp.get('spark_code_raw', '未生成原始Spark代码')}

### 迭代后最终上线代码
{mcp.get('spark_final_code', '无迭代优化代码')}

### Git版本迭代差异
{mcp.get('git_diff', '首次生成，无版本差异')}

### 最新版本迭代时间
{mcp.get('git_latest_version', '无版本记录')}

## 五、测试与优化报告
{mcp.get('test_report', '未生成测试报告')}

## 六、全维度数据质量校验结果
### 整体校验结论
{mcp.get('data_verify_result', '未执行数据校验')}

### 字段空值校验明细
{mcp.get('empty_check_result', '未执行空值校验')}

### 数据重复校验结果
{mcp.get('dup_check_result', '未执行重复值校验')}

## 七、运维巡检与DevOps报告
运维巡检报告：
{mcp.get('inspection_report', '无运维巡检报告')}

DevOps自动化报告：
{mcp.get('devops_report', '无DevOps交付报告')}

## 八、交付总结
1. 本文档由系统全自动读取MCP全局上下文生成，数据全链路可追溯、无人工干预
2. 涵盖数据源、表结构、代码、版本迭代、数据校验、运维巡检全流程产出
3. 所有研发成果已持久化留存，支持迭代复盘、交付归档、问题溯源
"""
        # 去除首尾空白，优化文档格式
        doc_content = doc.strip()
        # 落地保存交付文档
        doc_path = os.path.join(OUTPUT_DOC_PATH, f"spark_full_delivery_doc_{timestamp}.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(doc_content)

        # 双MCP全局上下文写入：缓存完整文档内容+文档存储路径
        mcp.set("final_doc", doc_content)
        mcp.set("final_doc_path", doc_path)

        return f"✅ 全自动交付文档生成成功｜文档路径：{doc_path}"
