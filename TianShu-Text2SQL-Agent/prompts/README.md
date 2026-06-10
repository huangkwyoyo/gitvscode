# LLM 提示词模板

> 四个提示词文件对应三层 IR 架构的每个环节。

## 文件说明

| 文件 | 用途 | 输入 → 输出 | 状态 |
|------|------|------------|------|
| `intent_classifier.md` | 意图分类 | 自然语言 → QuestionIntent JSON | 待编写 |
| `sql_planner.md` | SQL 规划 | QuestionIntent + Schema → SQLPlan JSON | 待编写 |
| `sql_generator.md` | SQL 生成 | SQLPlan → SQL 字符串 | 待编写 |
| `explainer.md` | 结果解释 | SQL 结果 + 原始问题 → 中文回答 | 待编写 |

## 提示词设计原则

1. **结构约束**：要求 LLM 输出 JSON（而非自由文本），便于解析和校验
2. **边界清晰**：提示词中包含"能力边界"和"不能做的事"
3. **Few-shot 示例**：每个模板至少包含 2 个示例
4. **中文为主**：提示词用中文编写，与用户语言一致

## 使用方式

```python
from jinja2 import Template

# 加载模板
with open("prompts/intent_classifier.md") as f:
    template = Template(f.read())

# 渲染（填入 AgentContext）
prompt = template.render(
    metric_definitions=context.available_metrics,
    dimension_catalog=context.available_tables,
    question_policy=question_policy_text,
)
```

## 提示词草稿

参见知识库文档 `Text2SQL数据分析Agent构建方案_20260610_2300.md` 第八章。
