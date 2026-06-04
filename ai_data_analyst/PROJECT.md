# AI Data Analyst — 项目架构文档

> 可扩展的数据分析工具 MVP — 上传 CSV/Excel/SQLite，输入分析需求，自动生成 HTML 分析报告。

---

## 目录

1. [项目总览](#1-项目总览)
2. [工程目录结构](#2-工程目录结构)
3. [技术栈选型](#3-技术栈选型)
4. [系统架构](#4-系统架构)
5. [核心模块详解](#5-核心模块详解)
6. [API 端点总览](#6-api-端点总览)
7. [数据分析工作流](#7-数据分析工作流)
8. [金融指标计算框架](#8-金融指标计算框架)
9. [前端架构](#9-前端架构)
10. [安全机制](#10-安全机制)
11. [测试覆盖](#11-测试覆盖)
12. [配置管理](#12-配置管理)
13. [项目演进历程](#13-项目演进历程)
14. [未来规划](#14-未来规划)

---

## 1. 项目总览

### 1.1 项目定位

AI Data Analyst 是一个**端到端的数据分析工具**，面向非技术用户（业务分析师、投资经理、数据研究员）。用户上传数据文件并输入分析需求，系统在数秒内自动完成数据加载、清洗、探索分析、可视化、洞察提取和 HTML 报告生成。

### 1.2 核心价值

| 维度 | 说明 |
|------|------|
| **零配置** | 无需安装 pandas/numpy，浏览器上传即可使用 |
| **全链路** | 从原始数据到可交付报告，一步到位 |
| **可扩展** | 确定性工作流内核，后续可直接替换为 LangGraph |
| **金融专精** | 内置私募基金产品分析框架，覆盖 13+ 项金融指标 |
| **LLM 可选** | 无 LLM 时仍可使用全部规则分析能力 |

### 1.3 关键指标

- **支持格式**: CSV、XLSX、XLS、SQLite（.db/.sqlite/.sqlite3）
- **上传限制**: 50MB（可通过环境变量配置）
- **分析耗时**: 通常在 5-30 秒内完成（取决于数据规模）
- **并发能力**: 最多 50 个任务同时驻留内存
- **测试覆盖**: 26 个单元测试（金融指标核心计算）

---

## 2. 工程目录结构

```
ai_data_analyst/
│
├── app/                          # 后端应用核心
│   ├── __init__.py
│   ├── main.py                   # FastAPI 入口，定义全部 API 端点
│   ├── models.py                 # AnalysisState 数据模型
│   ├── settings.py               # 集中配置管理（环境变量 + 默认值）
│   ├── workflow.py               # 确定性图工作流编排器
│   └── services/                 # 业务能力层
│       ├── __init__.py
│       ├── utils.py              # 共享工具函数（normalize/safe_float）
│       ├── loader.py             # 数据加载（Adapter 模式）
│       ├── cleaning.py           # 数据清洗流水线
│       ├── exploration.py        # 探索性数据分析（EDA）
│       ├── finance_metrics.py    # 金融指标计算（423行，最大单一文件）
│       ├── visualization.py      # 图表规格构建（SVG data specs）
│       ├── insights.py           # 洞察提取（规则 + LLM 增强）
│       ├── reporting.py          # HTML 报告生成（Jinja2）
│       └── adapters/             # 数据源适配器
│           ├── __init__.py
│           ├── base.py           # 抽象基类（DataSourceAdapter）
│           ├── file_adapter.py   # CSV/XLSX/XLS 文件适配器
│           └── sqlite_adapter.py # SQLite 数据库适配器
│
├── frontend/                     # 前端（零构建工具，纯原生）
│   ├── index.html                # 单页面应用主结构
│   ├── styles.css                # 自定义 CSS 变量 + Grid 布局
│   └── app.js                    # 原生 JS + 手动 SVG 图表渲染
│
├── templates/
│   └── report.html               # Jinja2 HTML 报告模板
│
├── tests/                        # 单元测试
│   ├── __init__.py
│   └── test_finance_metrics.py   # 金融指标测试（26用例，12个测试类）
│
├── samples/                      # 示例数据
│   ├── pe_fund_sample.csv        # 私募净值示例数据
│   ├── sales_sample.csv          # 销售示例数据
│   └── sales_sample.sqlite       # SQLite 示例数据库
│
├── data/                         # 运行时数据目录（git 忽略）
│   ├── uploads/                  # 上传文件暂存
│   └── outputs/                  # 生成的报告输出
│
├── docs/
│   └── architecture.md           # 架构设计文档
│
├── requirements.txt              # Python 依赖清单（8个包）
└── README.md                     # 项目说明文档
```

---

## 3. 技术栈选型

### 3.1 后端技术栈

| 技术 | 版本 | 选型理由 |
|------|------|----------|
| **FastAPI** | >=0.110 | 异步高性能、自动 OpenAPI 文档、类型安全、生态成熟 |
| **Uvicorn** | >=0.27 | ASGI 标准服务器，FastAPI 官方推荐 |
| **pandas** | >=2.0 | 数据处理事实标准，支持 CSV/Excel/SQLite 多格式 |
| **numpy** | >=1.24 | 数值计算基础库，金融指标计算依赖 |
| **openpyxl** | >=3.1 | Excel (.xlsx) 读写引擎，pandas 后端 |
| **Jinja2** | >=3.1 | 模板引擎，HTML 报告生成，支持 autoescape |
| **python-multipart** | >=0.0.9 | 文件上传 multipart 解析 |
| **openai** | >=1.0 | OpenAI 兼容 SDK，支持任意兼容 API（Ollama/DeepSeek 等） |

### 3.2 前端技术栈

| 技术 | 说明 | 选型理由 |
|------|------|----------|
| **原生 JavaScript** | 零框架依赖 | MVP 阶段保持简单，无构建工具链 |
| **原生 CSS** | CSS Custom Properties + Grid | 响应式设计，860px 断点 |
| **手动 SVG 渲染** | 折线图/面积图/热力条/柱状图 | 轻量替代 D3.js，满足当前图表需求 |

### 3.3 架构模式

- **Adapter 模式**: 数据源加载通过 `DataSourceAdapter` 抽象层解耦，新增数据源只需实现 `can_load()` + `load()` 两个方法
- **Pipeline 模式**: 数据清洗按严格顺序执行（去重 → 类型标准化 → 缺失值填充 → 异常值检测）
- **确定性图工作流**: 每个分析步骤是独立节点，状态沿统一 `AnalysisState` 流转，节点间通过依赖字段定义 DAG 关系
- **Strategy 模式**: 洞察提取采用"规则优先 + LLM 增强"的双层策略

### 3.4 为什么不用 CrewAI / LangGraph？

当前阶段选择了**确定性工作流内核**而非 Agent 编排框架，原因：

1. **可控性与可复现性**: 数据分析需要确定性输出，LLM 的不确定性不适合核心计算环节
2. **性能**: 纯 pandas/numpy 计算比 LLM 调用快 3 个数量级
3. **渐进式演进**: 当前架构已为 LangGraph 预留接口 — 每个服务节点可直接映射为 LangGraph 节点
4. **LLM 只在边缘使用**: 仅用于解释与总结，不参与数据计算

---

## 4. 系统架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                        浏览器端                           │
│  ┌──────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │index.html│  │ styles.css  │  │     app.js         │  │
│  │ 表单/导航  │  │ CSS Grid    │  │ Fetch API + SVG渲染 │  │
│  └────┬─────┘  └─────────────┘  └─────────┬──────────┘  │
│       │                                    │             │
│       └────────────── HTTP ────────────────┘             │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                    FastAPI 应用层                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │                  main.py                          │   │
│  │  POST /api/analyze  │  GET /api/jobs              │   │
│  │  GET /api/jobs/{id} │  GET /api/report/{id}       │   │
│  └──────────────────────┬───────────────────────────┘   │
│                          │                              │
│  ┌───────────────────────▼───────────────────────────┐  │
│  │              AnalysisWorkflow                      │  │
│  │  ┌─────┐  ┌──────┐  ┌────────┐  ┌─────────┐     │  │
│  │  │load │→│clean │→│explore │→│visualize│     │  │
│  │  └─────┘  └──────┘  └───┬────┘  └────┬────┘     │  │
│  │                          │            │          │  │
│  │                    ┌─────▼────┐  ┌────▼─────┐   │  │
│  │                    │insights  │  │finance   │   │  │
│  │                    └─────┬────┘  └────┬─────┘   │  │
│  │                          │            │         │  │
│  │                    ┌─────▼────────────▼─────┐   │  │
│  │                    │     generate_report     │   │  │
│  │                    └────────────────────────┘   │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │              services/ 业务能力层                 │   │
│  │  loader │ cleaning │ exploration │ visualization │  │
│  │  insights │ finance_metrics │ reporting │ utils  │  │
│  └────────────────────────────────────────────────┘   │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │              adapters/ 数据源适配层               │   │
│  │  base.py → file_adapter.py / sqlite_adapter.py  │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                    数据存储层                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ data/    │  │templates/│  │ samples/ │              │
│  │uploads/  │  │report.   │  │示例数据   │              │
│  │outputs/  │  │html      │  │          │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### 4.2 数据流

```
用户上传文件 → POST /api/analyze
    │
    ▼
[1] load_data        → raw_df, schema, preview_rows
    │
    ▼
[2] clean_data       → clean_df, cleaning_log, quality
    │
    ▼
[3] explore_data     → exploration, finance_metrics
    │                       │
    ├─ numeric_summary       └─ 时间序列检测 → 金融指标计算
    ├─ categorical_summary
    ├─ top_correlations
    └─ date/nav/benchmark 检测
    │
    ▼
[4] visualize        → chart_specs（histogram/bar/correlation/line/area）
    │
    ▼
[5] generate_insights → insights（规则 + LLM 增强）
    │
    ▼
[6] generate_report  → report_path（HTML 文件）
    │
    ▼
返回 JSON payload → 前端渲染结果页面
```

### 4.3 状态模型

`AnalysisState` 是整个系统的核心数据结构，采用 Python `dataclass` 实现：

```python
@dataclass
class AnalysisState:
    # 输入字段（由 API 端点填充）
    job_id: str                          # 12位随机UUID
    original_filename: str               # 用户上传的文件名
    analysis_goal: str                   # 用户输入的分析需求
    upload_path: Path                    # 上传文件存储路径
    output_dir: Path                     # 分析结果输出目录

    # 中间状态（由工作流节点逐步填充）
    raw_df: pd.DataFrame | None          # 原始数据
    clean_df: pd.DataFrame | None        # 清洗后数据
    schema: dict                         # 数据 schema（行数、列数、字段元数据）
    cleaning_log: list                   # 清洗操作日志
    quality: dict                        # 数据质量指标
    exploration: dict                    # 探索分析结果
    chart_specs: list                    # 图表规格（供前端渲染）
    insights: list                       # 洞察列表
    finance_metrics: dict                # 金融指标计算结果
    report_path: Path | None             # HTML 报告路径
    preview_rows: list                   # 预览数据（前25行）
    errors: list                         # 错误信息列表
```

---

## 5. 核心模块详解

### 5.1 工作流编排（workflow.py）

**设计思想**: 确定性图运行器 — 每个节点是独立函数，通过依赖字段定义 DAG 关系。

```
节点执行顺序:
load_data → clean_data → explore_data → visualize → generate_insights → generate_report
```

**关键设计**:

| 特性 | 实现 |
|------|------|
| **关键节点** | `load_data`/`clean_data`/`explore_data` 失败时提前终止 |
| **依赖检查** | 每个节点声明所需字段，运行时检查上游是否就绪 |
| **上游失败检测** | 通过字段→节点映射反向追踪失败源 |
| **异常处理** | 捕获异常记录到 `state.errors`，非关键节点跳过继续 |
| **可演进性** | 服务层代码可直接映射为 LangGraph StateGraph 节点 |

### 5.2 数据加载（loader.py + adapters/）

采用 **Adapter 模式** 解耦数据源类型：

```
DataSourceAdapter (抽象基类)
├── FileDataSourceAdapter   → CSV / XLSX / XLS
└── SQLiteDataSourceAdapter → .db / .sqlite / .sqlite3
```

加载流程：
1. 根据文件后缀自动匹配适配器
2. 读取 DataFrame
3. 清理列名（strip 空白字符）
4. 自动推断 dtype（`convert_dtypes()`）
5. 构建 schema 元数据
6. 提取前 25 行作为预览

**SQLite 安全加固**: 表名白名单校验（仅允许字母/数字/下划线），额外验证表存在于 `sqlite_master` 查询结果中。

### 5.3 数据清洗（cleaning.py）

严格按以下顺序执行：

| 步骤 | 操作 | 策略 |
|------|------|------|
| 1 | 去重 | `drop_duplicates()`，记录删除行数 |
| 2 | 类型标准化 | 日期列（语义 hint + 正则匹配），数值列（去除逗号/百分号） |
| 3 | 缺失值填充 | 数值→中位数，日期→前后填充，字符串→众数 |
| 4 | 异常值检测 | 3-sigma 法则（z-score > 3） |
| 5 | 质量计算 | 完整度 = 1 - (缺失后 / 总单元格数) |

类型转换成功率阈值：日期列 80%，数值列 85%。

### 5.4 探索分析（exploration.py）

| 分析维度 | 内容 | 限制 |
|----------|------|------|
| 数值统计 | 均值、中位数、标准差、min/max、Q1/Q3 | — |
| 分类分布 | value_counts Top 8 | 最多12列 |
| 相关性分析 | Pearson 相关系数上三角矩阵 | **最多20列**（防 O(n²)） |
| 时间序列检测 | 自动识别日期列/净值列/基准列 | 中英文关键词匹配 |
| 金融指标 | 13+ 项专业指标 | 仅在检测到时间序列后执行 |

### 5.5 洞察提取（insights.py）

**双层策略**:

```
规则洞察（确定性）          LLM 增强（可选）
├─ 数据集规模评估           ├─ 调用 OpenAI 兼容 API
├─ 缺失情况总结             ├─ temperature=0.2
├─ 异常检测发现             ├─ 输入 schema/quality/exploration
├─ 最高相关关系             └─ 输出 5 条可执行中文洞察
├─ 偏态检测
└─ 业务建议
```

LLM 完全可选 — 未配置 `OPENAI_API_KEY` 时，规则洞察仍完整可用。

---

## 6. API 端点总览

| 方法 | 路径 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/analyze` | 执行完整分析 | `data_file`(文件) + `analysis_goal`(文本) + `brief_file`(可选) | JSON（分析结果 + 报告URL） |
| GET | `/api/jobs` | 列出所有任务 | — | JSON 数组 |
| GET | `/api/jobs/{job_id}` | 查询单个任务 | — | JSON（完整分析状态） |
| GET | `/api/report/{job_id}` | 下载 HTML 报告 | — | `text/html` 文件 |
| — | `/` | 前端 SPA | — | `index.html` + 静态资源 |

**中间件**: `UploadSizeMiddleware` 拦截 POST 请求，检查 `content-length` 是否超过 50MB。

---

## 7. 数据分析工作流

### 7.1 节点依赖图

```
                    ┌─────────────┐
                    │  load_data  │
                    │  (无依赖)    │
                    └──────┬──────┘
                           │ raw_df
                    ┌──────▼──────┐
                    │ clean_data  │
                    │  [raw_df]   │
                    └──────┬──────┘
                           │ clean_df
                    ┌──────▼──────┐
                    │explore_data │ ← 关键节点
                    │  [clean_df] │
                    └──┬───────┬──┘
                       │        │
          exploration  │        │ exploration
                       │        │
              ┌────────▼┐  ┌────▼────────┐
              │visualize│  │generate_    │
              │         │  │insights     │
              └────┬────┘  └─────┬───────┘
                   │             │ insights
                   │      ┌──────▼──────┐
                   │      │generate_    │
                   │      │report       │
                   │      └─────────────┘
                   │
              chart_specs（前端渲染）
```

### 7.2 错误传播机制

```
关键节点失败 → 终止流程 → 记录错误 → 返回部分结果
非关键节点失败 → 跳过该节点 → 继续执行下游 → 最终报告可能缺失该部分内容
```

---

## 8. 金融指标计算框架

### 8.1 支持的指标

| 指标类别 | 指标名称 | 计算公式 | 业务含义 |
|----------|----------|----------|----------|
| **收益** | 累计收益率 | 期末/期初 - 1 | 总体盈亏幅度 |
| **收益** | 年化收益率 | (期末/期初)^(ann_mult/n) - 1 | 标准化年收益水平 |
| **收益** | 超额收益率 | 组合年化 - 基准年化 | 相对基准的主动管理价值 |
| **收益** | 滚动收益率 | 多窗口 pct_change | 收益趋势的时序分析 |
| **风险** | 年化波动率 | 收益率 std × √ann_mult | 收益波动程度 |
| **风险** | 最大回撤 | min(累计/历史最高 - 1) | 最大亏损幅度 |
| **风险** | 回撤持续时间 | 峰值→谷底→恢复天数 | 回撤的时间特征 |
| **风险调整** | 夏普比率 | (年化收益 - 无风险利率) / 年化波动率 | 单位风险的超额回报 |
| **风险调整** | 索提诺比率 | (年化收益 - 无风险利率) / 下行波动率 | 仅考虑下行风险 |
| **风险调整** | 信息比率 | 平均超额收益 / 跟踪误差 | 主动管理效率 |
| **风险调整** | Calmar 比率 | 年化收益 / |最大回撤| | 收益/回撤比 |
| **统计** | 胜率统计 | 正收益天数/总天数 | 收益分布特征 |
| **统计** | 盈亏比 | 平均盈利 / 平均亏损 | 风险回报不对称性 |

### 8.2 自动频率检测

系统根据每年平均数据点密度自动判断数据频率：

| 频率 | 年数据点范围 | 年化乘数 |
|------|-------------|----------|
| 日频 | 200-260 | 252 |
| 周频 | 40-60 | 52 |
| 月频 | 10-14 | 12 |
| 季度频 | < 10 | 4 |

### 8.3 时间序列自动检测

无需用户指定，系统自动识别：
1. **日期列**: datetime 类型 或 列名含 "date/time/日期/时间" 关键词
2. **净值列**: 数值型、唯一值 >= 3、非日期列
3. **基准列**: 列名含 "benchmark/基准/index/指数/hs300/沪深300" 关键词

---

## 9. 前端架构

### 9.1 设计原则

**零构建工具链** — 不使用 React/Vue/Webpack/npm，纯原生 HTML + CSS + JS。

### 9.2 组件结构

```
frontend/
├── index.html      # 单页面应用
│   ├── 侧边栏导航（3个tab）
│   │   ├── 分析入口（上传表单）
│   │   ├── 结果看板（动态渲染区）
│   │   └── 历史任务（列表）
│   └── 三个 view 区域（CSS .active 切换）
├── styles.css      # 设计系统
│   ├── CSS Custom Properties（Design Tokens）
│   ├── CSS Grid 布局
│   └── 响应式断点 860px
└── app.js          # 应用逻辑（~370行）
    ├── Fetch API 通信
    ├── SVG 图表渲染器
    │   ├── renderLineChart      → 累计收益/滚动收益曲线
    │   ├── renderAreaChart      → 回撤面积图
    │   ├── renderMultiLineChart → 多净值对比
    │   ├── renderBars           → 分类柱状图
    │   └── renderCorrelation    → 相关性热力条
    ├── 金融指标渲染器
    │   └── renderFinanceMetrics → 收益卡片组 + 回撤详情
    └── 安全防护
        └── escapeHtml() → 转义 & < > " '
```

### 9.3 通信协议

```
前端                          后端
 │                             │
 │  POST /api/analyze          │
 ├────────────────────────────>│
 │  multipart/form-data         │
 │  {data_file, analysis_goal}  │
 │                             │
 │  JSON response              │
 │<────────────────────────────┤
 │  {schema, exploration,      │
 │   chart_specs, insights,    │
 │   finance_metrics, errors}  │
 │                             │
 │  renderResult()             │
 │  → 动态渲染 SVG 图表         │
 │  → 填充指标卡片              │
 │  → 显示洞察列表              │
```

---

## 10. 安全机制

| 威胁类型 | 防护措施 | 实现位置 |
|----------|----------|----------|
| **大文件攻击** | Content-Length 检查 + 存储后二次校验 | `main.py` 中间件 + `_save_upload()` |
| **路径遍历** | `Path.name` 截断 + 安全字符白名单 | `_safe_name()` |
| **SQL 注入** | 表名 `isalnum()` 校验 + 存在性验证 | `sqlite_adapter.py` |
| **XSS** | Jinja2 `select_autoescape` + 前端 `escapeHtml()` | `reporting.py` + `app.js` |
| **空文件** | 加载后检查 DataFrame 是否为空 | `loader.py` |
| **内存溢出** | 任务数上限 50 + FIFO 驱逐 | `_evict_old_jobs()` |
| **不安全文件** | 后缀白名单（csv/xlsx/xls/db/sqlite/sqlite3） | `main.py` |

---

## 11. 测试覆盖

### 11.1 金融指标测试（tests/test_finance_metrics.py）

| 测试类 | 用例数 | 覆盖函数 |
|--------|--------|----------|
| TestCalculateReturns | 2 | calculate_returns |
| TestCumulativeReturn | 2 | cumulative_return |
| TestAnnualizedReturn | 2 | annualized_return |
| TestAnnualizedVolatility | 2 | annualized_volatility |
| TestMaxDrawdown | 2 | max_drawdown |
| TestDrawdownDuration | 1 | drawdown_duration |
| TestSharpeRatio | 2 | sharpe_ratio |
| TestSortinoRatio | 2 | sortino_ratio |
| TestWinRateStats | 2 | win_rate_stats |
| TestDetectFrequency | 3 | _detect_frequency |
| TestExcessReturn | 2 | excess_return |
| TestInformationRatio | 2 | information_ratio |
| TestRollingReturns | 2 | rolling_returns |

**总计**: 12 个测试类，26 个测试用例，全部通过。

### 11.2 测试策略

- **边界测试**: 常量净值序列、零波动率、数据点不足等
- **数值精度**: 使用 `pytest.approx` 容差比较浮点数
- **Fixture**: `sample_nav`（100个交易日模拟数据）、`drawdown_nav`（明确涨跌恢复曲线）

### 11.3 待补充测试

以下模块暂无单元测试：
- loader.py / cleaning.py（数据加载与清洗）
- exploration.py / visualization.py（探索分析与可视化）
- insights.py（洞察提取）
- workflow.py（工作流编排）
- reporting.py（报告生成）

---

## 12. 配置管理

全部配置集中在 `app/settings.py`，支持环境变量覆盖：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| MAX_UPLOAD_BYTES | MAX_UPLOAD_BYTES | 50MB | 上传文件大小限制 |
| MAX_JOBS | MAX_JOBS | 50 | 内存中最大任务数 |
| TRADING_DAYS | TRADING_DAYS | 252 | 年交易日数 |
| RISK_FREE_RATE | RISK_FREE_RATE | 0.015 | 无风险利率（1.5%，中国一年期定存利率） |
| ROLLING_WINDOW_3M | ROLLING_WINDOW_3M | 63 | 3个月滚动窗口交易日数 |
| ROLLING_WINDOW_6M | ROLLING_WINDOW_6M | 126 | 6个月滚动窗口交易日数 |
| ROLLING_WINDOW_1Y | ROLLING_WINDOW_1Y | 252 | 1年滚动窗口交易日数 |
| CHART_WIDTH | CHART_WIDTH | 520 | 前端图表宽度（px） |
| CHART_HEIGHT | CHART_HEIGHT | 260 | 前端图表高度（px） |

### LLM 配置（通过系统环境变量）

| 环境变量 | 说明 | 默认 |
|----------|------|------|
| OPENAI_API_KEY | API 密钥 | 无（禁用 LLM） |
| OPENAI_BASE_URL | 自定义 API 端点 | OpenAI 官方 |
| OPENAI_MODEL | 模型名称 | gpt-4o |

---

## 13. 项目演进历程

```
初次提交
    │
    ▼
本地可运行 AI Agent 入门工程
    │
    ▼
修复 OpenAI API 调用
    │
    ▼
自动生成 SQL 功能
    │
    ▼
CrewAI 多智能体全链路研发
    │
    ▼
全局 LLM 绑定 + 安全加固
    │
    ▼
商业数据报告管线
    │
    ▼
AI Data Analyst 独立项目
    │
    ▼
上传安全加固（大小限制/路径遍历/旧任务清理）
    │
    ▼
私募产品分析框架（8项金融指标）
    │
    ▼
全局中文注释规范
    │
    ▼
修复4个bug并新增4项金融指标
    │
    ▼
项目全面优化（当前版本）
    ├── workflow 异常传播
    ├── 配置管理集中化
    ├── 重复代码消除
    ├── SQL 安全加固
    ├── drawdown_duration 边界 bug 修复
    └── 26个金融指标单元测试
```

---

## 14. 未来规划

### 14.1 短期（1-2周）

- [ ] 补充 loader/cleaning/exploration 模块的单元测试
- [ ] 添加 workflow 集成测试
- [ ] 前端响应式优化（移动端适配）
- [ ] Docker 容器化部署

### 14.2 中期（1-2月）

- [ ] 迁移至 LangGraph StateGraph（保持现有服务代码不变）
- [ ] 多文件对比分析（支持同时上传多个净值文件）
- [ ] 自定义指标配置界面
- [ ] 报告导出 PDF 支持
- [ ] CI/CD 管线（GitHub Actions）

### 14.3 长期（3-6月）

- [ ] 企业版：数据库持久化替代内存存储
- [ ] 多用户认证与权限管理
- [ ] 更多数据源适配器（MySQL/PostgreSQL/API 直连）
- [ ] 增量分析（数据更新后仅重算变化部分）
- [ ] 分析模板市场（预设行业分析模板）

---

## 启动方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. （可选）配置 LLM
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://your-api-endpoint"
export OPENAI_MODEL="gpt-4o"

# 3. 启动服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 浏览器访问
open http://127.0.0.1:8000
```

---

*文档版本: v1.0 | 最后更新: 2026-05-28 | 基于 commit 2b3c409*
