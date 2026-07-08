# TianShu-Agent-Runtime-Lab 工程术语表

本文解释本项目当前阶段的常见工程术语。每个术语按九件事说明：

1. **术语名称**：一句话解释
2. **是什么**：用中文说清楚它是什么
3. **解决什么问题**：为什么项目里需要它
4. **在当前项目中的位置**：列出可能相关的目录或文件，如无则写"待实现"
5. **输入是什么**：它接收什么
6. **输出是什么**：它产出什么
7. **出错会导致什么风险**：如果它设计不好，会造成什么问题
8. **简单例子**：结合真实业务场景举例
9. **Owner 审查时应该问什么**：2-3 个项目 Owner 可以用来审查的问题

---

## 1. RuntimeState

**一句话解释**：统一运行状态记录——保存一次 Agent 任务执行到哪一步、已产生什么中间结果、调用了哪些工具。

**是什么**

RuntimeState 是本项目最核心的数据结构。它使用 `@dataclass` 定义，记录 Agent 一次运行的全生命周期状态，包括：运行标识（run_id / thread_id）、用户输入与分类、当前执行步骤、下一步动作、运行状态（init / running / waiting_approval / completed / failed_closed）、中间产物字典、工具调用历史列表、错误记录列表、时间戳。每个 LangGraph 节点只读写 State 中自己关心的字段，不跨字段修改。

**解决什么问题**

普通 LLM 调用是无状态的——每次请求都是独立对话。Agent Runtime 需要有状态才能：记住已经检查过什么、知道下一步该做什么、在中断后能恢复上下文、在失败时能输出完整的执行轨迹。

**在当前项目中的位置**

- `src/runtime_lab/state.py` — RuntimeState dataclass 定义
- `src/runtime_lab/graph.py` — LangGraph 图的 state 泛型参数

**输入是什么**

不适用——RuntimeState 是数据结构定义，由 `graph.py` 初始化为默认值，在节点间传递时逐步填充。

**输出是什么**

每一步执行后的 RuntimeState 实例——序列化为 JSON 写入 `state_history.jsonl`。

**出错会导致什么风险**

如果 State 字段定义不清晰——节点可能读到错误的值或写错字段，导致执行路径混乱。如果 State 没有正确保存中间产物——中断恢复时上下文丢失，Agent 需要重新推理。

**简单例子**

```python
RuntimeState(
    run_id="run_20260708_001",
    user_input="审查 fixtures/sql/unsafe_query.sql",
    demo_type="sql_review",
    status="running",
    current_step="call_tool",
    intermediate={"sql_text": "DELETE FROM trips;"},
    tool_call_history=[{"tool": "detect_dml_or_ddl", "result": {"has_dml": True}}],
)
```

**Owner 审查时应该问什么**

1. "哪些节点读取了哪些 State 字段？是否存在某个节点读取了它不应该触碰的字段？"
2. "State 序列化到 JSON 时，所有字段都能正确处理吗？有没有不能序列化的对象？"

---

## 2. LangGraph 图

**一句话解释**：用 LangGraph 框架定义的有向图——节点是处理函数，边是执行路由，编译后形成一个可调用的 Agent Runtime。

**是什么**

LangGraph 图是本项目 Runtime 的执行骨架。它由 `StateGraph(RuntimeState)` 构建，通过 `add_node()` 注册处理函数，通过 `add_edge()` / `add_conditional_edges()` 定义执行路径，最终 `compile()` 为可调用对象。图可以包含条件分支（如 risk_gate 根据风险等级走 interrupt 或 summarize）、循环（如人工审批后返回到规划节点）。

**解决什么问题**

用图表达 Agent 执行流程比线性的 if-else 链更清晰——每个节点是独立可测试的单元，边显式路由，整个流程可视化。LangGraph 框架内置了 State 的自动传递和 checkpoint 机制。

**在当前项目中的位置**

- `src/runtime_lab/graph.py` — `build_graph()` 函数
- 后续每周：新增节点注册和条件边

**输入是什么**

用户输入文本 + 初始 RuntimeState。

**输出是什么**

完整的执行结果——最终状态（completed / waiting_approval / failed_closed）+ 中间产物 + 追踪记录。

**出错会导致什么风险**

如果图的条件边路由逻辑错误——状态机可能走到未定义的节点，LangGraph 会抛出运行时错误。如果图的循环没有终止条件（如无限返工）——Agent 永远不会完成。

**简单例子**

```python
builder = StateGraph(RuntimeState)
builder.add_node("classify_demo", classify_node)
builder.add_node("summarize", summarize_node)
builder.set_entry_point("classify_demo")
builder.add_conditional_edges("classify_demo", router, {"summarize": "summarize", "__end__": "__end__"})
builder.add_edge("summarize", "__end__")
graph = builder.compile()
result = graph.invoke({"user_input": "greet", "run_id": "run_001"})
```

**Owner 审查时应该问什么**

1. "图的节点是否都无副作用（pure function）？除了写 State，节点是否还改了其他全局状态？"
2. "条件边的路由函数是否有测试覆盖？哪些边界情况没覆盖？"

---

## 3. 节点（Node）

**一句话解释**：LangGraph 图中的每个处理函数——接收 RuntimeState，执行单一职责，返回更新后的 State 字段。

**是什么**

节点是 LangGraph 图的基本执行单元。每个节点是一个 Python 函数，签名 `(state: RuntimeState) -> dict[str, Any]`，返回值是被更新到 State 的字段字典。节点只应该做一件事：分类、规划、执行工具、校验、路由、总结等。节点不应该直接互相调用——图负责编排。

**解决什么问题**

将 Agent 的行为拆分为可独立开发、测试、审查的小单元。每个节点可以单独测试，也可以在图中组合测试。

**在当前项目中的位置**

- `src/runtime_lab/nodes/` — 所有节点实现（按职责分文件）
  - `classify.py` — 任务分类节点
  - `plan.py` — 规划节点（第 2 周）
  - `validate.py` — 校验节点（第 2 周）
  - `execute_tool.py` — 工具执行节点（第 2 周）
  - `interrupt.py` — 中断节点（第 4 周）
  - `summarize.py` — 总结节点
  - `replay.py` — 回放节点（第 5 周）

**输入是什么**

当前 RuntimeState 实例（只读或部分更新）。

**输出是什么**

要更新的 State 字段字典 `{"status": "completed", "current_step": "summarize"}`。

**出错会导致什么风险**

如果节点的职责不单一（如分类节点同时做工具调用）——节点难以测试和复用。如果节点修改了不属于它职责的 State 字段——图的状态迁移变得不可预测。

**简单例子**

```python
def classify_node(state: RuntimeState) -> dict:
    """根据用户输入判断 Demo 类型"""
    if "sql" in state.user_input.lower():
        return {"demo_type": "sql_review", "current_step": "plan"}
    elif "contract" in state.user_input.lower():
        return {"demo_type": "contract", "current_step": "plan"}
    else:
        return {"demo_type": "greet", "current_step": "summarize"}
```

**Owner 审查时应该问什么**

1. "这个节点改变了多少个 State 字段？这些字段是否都属于它的职责范围？"
2. "节点是否依赖了外部状态（如全局变量、文件系统）？测试时需要 Mock 吗？"

---

## 4. 受控工具（Controlled Tool）

**一句话解释**：Agent 可以调用但 LLM 不能编造结果的工具——输入输出有严格 Schema，失败时写入错误记录。

**是什么**

受控工具是本项目区分"Agent Runtime"和"普通 LLM 调用"的关键设计。每个工具是一个纯函数（或零依赖函数），有明确的 Pydantic 输入 Schema 和输出 Schema。工具执行的结果直接写入 RuntimeState 的 `intermediate` 字段或 `tool_call_history`。LLM 只能决定"调不调用"和"传什么参数"，不能决定结果——事实必须来自工具。

**解决什么问题**

防止 LLM 编造事实。如果 LLM 可以直接回答"这个 SQL 是否安全"，它可能编造检查结果。有了受控工具，LLM 必须调用 `detect_dml_or_ddl()` 才能知道结果，而工具是确定性代码。

**在当前项目中的位置**

- `src/runtime_lab/tools/`
  - `sql_review_tools.py` — SQL 审查工具（第 2 周）
  - `contract_tools.py` — 契约检查工具（第 3 周）
  - `join_tools.py` — Join 证据工具（第 4 周）
  - `datadev_tools.py` — DataDev 工具（第 5 周）

**输入是什么**

工具特定的输入参数（如 SQL 文本、契约文件路径、表名）。

**输出是什么**

结构化的工具结果（Pydantic 模型或字典）——必须在工具内部定义，不允许 LLM 定义输出格式。

**出错会导致什么风险**

如果工具没有错误处理——工具调用失败时 LLM 可能"猜测"结果而不是如实记录失败。如果工具的输入 Schema 不严格——LLM 可能传入非法参数（如用 SQL 注入字符串做文件名）。

**简单例子**

```python
def detect_dml_or_ddl(sql_text: str) -> dict:
    """检测 SQL 是否包含 DDL/DML 操作"""
    forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"}
    tokens = set(sql_text.upper().split())
    found = [kw for kw in forbidden if kw in tokens]
    return {"has_forbidden": len(found) > 0, "found_keywords": found}
```

**Owner 审查时应该问什么**

1. "每个工具是否都有对应的测试？测试是否覆盖了失败路径？"
2. "工具的输出是否直接写入 State？有没有中间层校验工具输出的正确性？"

---

## 5. 结构化输出（Structured Output）

**一句话解释**：LLM 输出必须是 Pydantic 定义的严格结构化对象，不是自由文本——校验失败时进入修复或失败封闭。

**是什么**

结构化输出是限制 LLM 自由度的核心手段。Agent 从 LLM 获得的不应该是"这个 SQL 看起来有风险"这种自由文本，而应该是 `{"risk_level": "HIGH", "findings": [...], "decision": "FAILED_CLOSED"}` 这样的结构化 JSON。本项目用 Pydantic 模型定义输出 Schema，LLM 输出后经过 Schema 校验（包括 extra="forbid"），不合格的输出被拒绝。

**解决什么问题**

自由文本不可编程——下一步节点无法可靠地从"这个 SQL 看起来有风险"中提取风险等级和决策。结构化输出使下游节点可以确定性地消费 LLM 的输出。

**在当前项目中的位置**

- `src/runtime_lab/models/`
  - `common.py` — RiskLevel、Finding、Decision 等通用模型
  - `sql_review.py` — SQLReviewResult（第 2 周）
  - `contracts.py` — ContractQueryResult（第 3 周）
  - `joins.py` — JoinDecision（第 4 周）
  - `datadev_plan.py` — PlanDiff（第 5 周）

**输入是什么**

LLM 原始输出文本（JSON 格式字符串或 Python dict）。

**输出是什么**

经 Pydantic 校验后的结构化模型实例——或校验失败的 ValidationError。

**出错会导致什么风险**

如果结构化模型没有 `extra="forbid"`——LLM 可能输出未定义字段，这些字段绕过 Schema 约束被下游误用。如果校验失败没有正确的 fallback——LLM 输出不合格时静默降级使用自由文本，失去结构化优势。

**简单例子**

```python
class SQLReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    findings: list[Finding]
    decision: Literal["APPROVED", "FAILED_CLOSED", "NEEDS_REVIEW"]
```

**Owner 审查时应该问什么**

1. "项目中所有的 LLM 输出是否都有对应的 Pydantic Schema 约束？有没有自由文本逃生口？"
2. "校验失败时，系统是重试、降级还是 fail-closed？策略是什么？"

---

## 6. Checkpoint（检查点）

**一句话解释**：把某一步执行后的 State 完整保存下来——用于故障恢复、中断后续和回放分叉。

**是什么**

Checkpoint 是 RuntimeState 在关键节点后的持久化快照。它以 `run_id` + `step_id` 为键，将完整 State 序列化为 JSON 写入 SQLite（或本地文件）。每次 checkpoing 保存后，即使进程崩溃，也可以从最近的 checkpoint 恢复。Checkpoint 是不可变的——一旦写入不能被覆盖，历史 checkpoint 可以用于回放和分叉。

**解决什么问题**

Agent 执行可能因为各种原因中断：进程崩溃、网络超时、等待人工审批。没有 checkpoint，中断后必须从头开始。有 checkpoint，可以从最近的安全节点恢复。

**在当前项目中的位置**

- `src/runtime_lab/storage/checkpoints.py` — checkpoint 保存与读取（第 4 周）
- `src/runtime_lab/storage/artifact_store.py` — 产物 hash 与 lineage（第 5 周）

**输入是什么**

当前 RuntimeState + checkpoint 名称（如 `"post_validate"`、`"pre_interrupt"`）。

**输出是什么**

持久化到存储的 checkpoint 记录——含 run_id、checkpoint_id、state 快照、时间戳、父 checkpoint 引用。

**出错会导致什么风险**

如果 checkpoint 保存过于频繁——IO 开销影响正常执行性能。如果 checkpoint 保存不够频繁——中断时丢失大量已执行的工作。如果 checkpoint 可以被覆盖——回放和审计失去可靠性。

**简单例子**

```python
store.save_checkpoint(
    run_id="run_001",
    step="post_validate",
    state=runtime_state,
)
# 进程崩溃后...
state = store.load_checkpoint("run_001", "post_validate")
# 从该 checkpoint 继续执行
```

**Owner 审查时应该问什么**

1. "哪些节点后保存 checkpoint？是否覆盖了所有关键决策点？"
2. "Checkpoint 被覆盖的保护机制是什么？如何防止意外覆盖？"

---

## 7. 中断与恢复（Interrupt / Resume）

**一句话解释**：Agent 在风险节点主动暂停执行，等待外部信号（如人工审批）后再从断点继续。

**是什么**

Interrupt 是 Agent 在风险评估后主动暂停执行的动作。暂停时 Agent 保存完整的 checkpoint，进入 `waiting_approval` 状态，等待外部输入。Resume 是收到外部输入后，从最近的 checkpoint 恢复执行，不走回头路。中断期间的等待不会消耗 LLM Token，不会超时（或超时时间很长）。

**解决什么问题**

高风险动作（如低置信 Join、执行写操作）不能由 Agent 自主决定——需要人在回路中确认。Interrupt/Resume 机制确保审批流程与 Agent 执行流程无缝衔接。

**在当前项目中的位置**

- `src/runtime_lab/nodes/interrupt.py` — 中断节点（第 4 周）
- `src/runtime_lab/policies/approval_policy.py` — 哪些情况必须触发 interrupt（第 4 周）
- `src/runtime_lab/storage/checkpoints.py` — checkpoint 保存用于 resume

**输入是什么**

Interrupt 触发：当前 RuntimeState + 中断原因。Resume 触发：外部输入（审批结果）+ checkpoint_id。

**输出是什么**

Interrupt：保存 checkpoint，State 状态变为 waiting_approval。Resume：加载 checkpoint，State 从断点字段恢复，继续执行。

**出错会导致什么风险**

如果中断后没有保存 checkpoint——恢复时找不到断点，只能从头开始。如果中断点之前的工具调用结果没有持久化——恢复后需要重新调用工具（可能产生不同结果）。如果审批后的 State 与中断前的 State 不一致——恢复后执行路径异常。

**简单例子**

```
执行到 risk_gate 节点 → 风险等级 MEDIUM → 触发 interrupt
→ 保存 checkpoint("run_001", "pre_approval")
→ 状态变为 waiting_approval
→ 人工审批通过，传入 approval_record
→ 从 checkpoint("run_001", "pre_approval") 恢复
→ 审批结果写入 State.intermediate["approval"]
→ 继续执行到下一节点
```

**Owner 审查时应该问什么**

1. "中断恢复后，哪些操作需要重新执行？哪些可以直接复用中断前的结果？"
2. "如果人工审批拒绝了请求，Agent 的行为是什么？"

---

## 8. 人工审批（Human Approval）

**一句话解释**：对低置信或高风险动作，人必须明确批准或拒绝——审批记录包含完整审计信息。

**是什么**

人工审批是中断恢复机制的上层策略。审批记录必须包含：审批人、审批时间、审批对象、批准或拒绝、批准理由、对应 run_id、对应 checkpoint_id。审批记录持久化到 `approvals.jsonl`，不可篡改。MEDIUM 级别的 Join 不能自动通过——必须等待人工审批。拒绝后 Agent 进入 failed_closed 或 clarification 路径。

**解决什么问题**

防止 Agent 在信息不充分时自主执行高风险操作。保证每次人工决策都有完整的审计轨迹。

**在当前项目中的位置**

- `src/runtime_lab/nodes/interrupt.py` — 审批触发和消费
- `src/runtime_lab/storage/approval_store.py` — 审批记录存储（第 4 周）
- `src/runtime_lab/policies/approval_policy.py` — 审批触发规则（第 4 周）

**输入是什么**

审批人提交的结构化审批决定（approved / rejected）+ 理由。

**输出是什么**

持久化的审批记录 + 更新后的 RuntimeState（继续执行或进入 failed_closed）。

**出错会导致什么风险**

如果审批记录不完整（缺少审批人或时间）——审计时无法追溯是谁批准的风险操作。如果"拒绝"后 Agent 没有正确 fail-closed——Agent 可能绕过拒绝继续执行。如果审批没有绑定 checkpoint_id——无法确认审批针对的是哪个执行状态。

**简单例子**

```python
ApprovalRecord(
    approval_id="appr_001",
    run_id="run_001",
    checkpoint_id="cp_pre_join",
    approver="zhangsan",
    approved_at="2026-07-08T14:30:00",
    target="join: orders.customer_id → customers.id",
    decision="approved",
    reason="通过字段名和文档确认，customer_id 是外键引用 customers.id",
)
```

**Owner 审查时应该问什么**

1. "人工审批的记录存储在哪里？是否防篡改？"
2. "如果审批人长时间未响应，Agent 的行为是什么？超时策略是什么？"

---

## 9. 失败封闭（Fail-Closed）

**一句话解释**：遇到安全基础设施缺失、校验失败或事实不明时，停止执行——而不是猜测、降级或继续。

**是什么**

Fail-Closed 是安全优先的执行策略。当 Agent 遇到以下情况时，进入 `failed_closed` 终止状态：契约文件不存在、指标未注册、Join 无白名单、SQL 含 DDL/DML、工具调用失败且无法恢复、LLM 输出结构不合格。Fail-Closed 状态下 Agent 不继续执行任何后续动作，错误原因写入 `errors.jsonl` 和 `run_report.md`。

**解决什么问题**

企业场景中，错误的 SQL 执行比不执行更危险——删除生产表比"无法回答"严重得多。Fail-Closed 确保 Agent 在不确定时不作为，而不是猜测一个可能错误的答案。

**在当前项目中的位置**

- `src/runtime_lab/policies/fail_closed.py` — 失败封闭策略（第 2 周）
- `src/runtime_lab/nodes/validate.py` — 校验失败时触发 fail-closed（第 2 周）
- `src/runtime_lab/policies/risk_policy.py` — 不可恢复风险触发 fail-closed（第 2 周）

**输入是什么**

触发 fail-closed 的异常或校验失败信息。

**输出是什么**

RuntimeState.status = "failed_closed" + errors 列表 + 已保存的 trace。

**出错会导致什么风险**

如果 fail-closed 判定太宽松——本应阻断的执行被放行（fail-open），产生不可控后果。如果判定太严格——过多合法请求被阻断，影响自动化率。`approval_policy.py` 负责平衡安全性和自动化率。

**简单例子**

```python
def risk_gate(state: RuntimeState) -> dict:
    """风险门禁——不可恢复风险直接 fail-closed"""
    findings = state.intermediate.get("findings", [])
    blocking = [f for f in findings if f.severity == "BLOCKING"]
    if blocking:
        return {
            "status": "failed_closed",
            "errors": [{"reason": "存在阻断性风险", "details": [b.dict() for b in blocking]}],
        }
    return {"status": "running", "next_action": "summarize"}
```

**Owner 审查时应该问什么**

1. "当前哪些条件下触发 fail-closed？是否有应该触发但尚未实现的场景？"
2. "Fail-closed 和 waiting_approval 的判定边界是什么？什么情况下用哪个？"

---

## 10. 回放与分叉（Replay / Fork）

**一句话解释**：从历史运行记录中重放一次执行（Replay），或从历史 checkpoint 派生一条全新的执行分支（Fork）。

**是什么**

Replay 是指从 history 中取出一个已有的 run，重新运行一遍——可以验证原结果是否可复现。Fork 是指从某个历史 checkpoint 创建一条新的执行分支，使用不同的输入或参数，不覆盖原始运行。Fork 产生新的 run_id，原始运行保持不变。两组运行可以对比 plan_diff。

**解决什么问题**

故障排查时，回放可以确认问题是偶发的还是确定性的。方案对比时，从同一断点分叉出两个不同方案，可以比较它们的 Plan 差异——不需要重新执行前半段相同的逻辑。

**在当前项目中的位置**

- `src/runtime_lab/nodes/replay.py` — 回放和分叉节点（第 5 周）
- `src/runtime_lab/storage/checkpoints.py` — 历史 checkpoint 读取
- `src/runtime_lab/reports/plan_diff.py` — Plan 差异报告生成（第 5 周）

**输入是什么**

Replay：run_id。Fork：原 run_id + checkpoint_id + 新输入参数。

**输出是什么**

Replay：一个新的运行结果（带新的 run_id，但可追溯到原 run_id）。Fork：新 run_id 的执行结果 + plan_diff.md（与原运行对比）。

**出错会导致什么风险**

如果 Replay 不是确定性的——相同输入产生不同结果，无法判断是修复有效还是随机波动。如果 Fork 写入了原始运行的目录——破坏原始运行的审计完整性。

**简单例子**

```bash
# 回放历史运行
python -m runtime_lab replay run_20260708_001

# 从历史 checkpoint 分叉
python -m runtime_lab fork run_20260708_001 --checkpoint cp_pre_join --input fixtures/datadev/developer_spec_valid.md
```

**Owner 审查时应该问什么**

1. "Replay 是否完全使用原始输入？还是允许微调？"
2. "Fork 生成的新 run 的 trace 中是否包含父 run 的引用？如何追溯？"

---

## 11. 追踪（Trace / Audit）

**一句话解释**：记录 Agent 每一步做了什么——包括 State 变化、工具调用、LLM 输出、审批记录、错误信息。

**是什么**

Trace 是 Agent 运行的完整审计记录，持久化到 `runs/{run_id}/` 目录下。包含以下文件：
- `state_history.jsonl`：每一步 State 变化的增量记录
- `tool_calls.jsonl`：每次工具调用的输入和输出
- `approvals.jsonl`：每次人工审批的记录
- `errors.jsonl`：每个错误和失败封闭的原因
- `reports/run_report.md`：人可读的运行总结

**解决什么问题**

Agent 执行不是"黑盒"——审查者需要能追溯每次运行的完整过程。审计轨迹用于合规审查、故障排查、性能分析和成本核算。

**在当前项目中的位置**

- `src/runtime_lab/storage/trace_store.py` — trace 写入和读取（第 1 周）
- `src/runtime_lab/reports/run_report.py` — run_report.md 生成（第 2 周）

**输入是什么**

运行过程中的事件（State 变更、工具调用、审批、错误）。

**输出是什么**

持久化到文件系统的 JSONL 文件和 Markdown 报告。

**出错会导致什么风险**

如果 trace 记录不完整——审查者无法确认 Agent 是否在某个步骤做了未记录的操作。如果 trace 文件过大（包含完整中间结果而非引用）——存储成本高，清理策略缺失。

**简单例子**

```
runs/run_001/
├── state_history.jsonl    # {"step": "classify", "status": "running", ...}
│                           # {"step": "call_tool", "tool": "detect_dml_or_ddl", ...}
├── tool_calls.jsonl       # {"tool": "detect_dml_or_ddl", "input": {"sql_text": "..."}, "output": {...}}
├── errors.jsonl           # {"step": "validate", "error": "LLM 输出结构不合格", ...}
├── approvals.jsonl        # {"run_id": "run_001", "decision": "approved", ...}
└── reports/
    └── run_report.md      # 人可读的运行总结
```

**Owner 审查时应该问什么**

1. "Trace 中记录的是完整 State 还是 State 变化增量？文件大小如何控制？"
2. "Trace 文件是否有 TTL 自动清理策略？还是需要手动清理？"

---

## 12. 风险门（RiskGate）

**一句话解释**：风险判断的条件路由节点——根据校验结果决定 Agent 下一步是继续、中断等待审批、还是失败封闭。

**是什么**

RiskGate 是 LangGraph 图中的条件边节点。它接收当前 State 中的风险判定结果（来自 `risk_policy.py`），输出三种路由：自动继续（风险低）、中断等待审批（风险中等）、失败封闭（风险高不可恢复）。RiskGate 本身不判断风险——它只路由。风险判断由 `risk_policy.py` 的确定性规则完成。

**解决什么问题**

将"风险判断"和"风险路由"分离——`risk_policy.py` 决定风险等级，RiskGate 根据等级决定图的走向。这使得风险策略可以独立于图结构修改和测试。

**在当前项目中的位置**

- `src/runtime_lab/graph.py` — RiskGate 条件边（第 2 周开始）
- `src/runtime_lab/policies/risk_policy.py` — 风险等级判定规则（第 2 周）

**输入是什么**

当前的 RuntimeState（含 intermediate 中的校验结果和风险等级）。

**输出是什么**

路由指令：`"continue"`、`"interrupt"`、`"failed_closed"`——对应图中的不同下游节点。

**出错会导致什么风险**

如果 RiskGate 的路由逻辑与 `risk_policy.py` 的等级定义不一致——MEDIUM 风险可能被误路由到 continue 而非 interrupt。如果 RiskGate 没有处理未知风险等级——条件边的 fallback 行为不确定。

**简单例子**

```python
def risk_gate_router(state: RuntimeState) -> str:
    """根据风险等级决定下一步走向"""
    risk = state.intermediate.get("risk_level", "UNKNOWN")

    if risk in ("LOW",):
        return "continue"        # 自动继续
    elif risk in ("MEDIUM",):
        return "interrupt"       # 等待人工审批
    elif risk in ("HIGH", "CRITICAL", "UNKNOWN"):
        return "failed_closed"   # 失败封闭
```

**Owner 审查时应该问什么**

1. "RiskGate 的路由分支是否都有测试覆盖？包括 UNKNOWN 这个 fallback？"
2. "风险等级的定义和路由策略是否会因为 Demo 不同而变化？如果是，如何处理？"

---

## 13. 证据等级（EvidenceLevel）

**一句话解释**：Join 关系的置信度分级——STRONG 自动通过，MEDIUM 需人工审批，WEAK/NONE 直接拒绝。

**是什么**

EvidenceLevel 是 Join 审批 Demo（Demo 3）的核心概念。它对每对候选的 Join 关系进行四级定级：
- **STRONG**：契约显式声明 Join 或外键明确，且字段类型一致 → 自动继续
- **MEDIUM**：字段名归一化后匹配，类型兼容，无显式声明 → 中断等待人工审批
- **WEAK**：只有字段名相似，无类型/契约/唯一性证据 → failed_closed
- **NONE**：字段名、类型、契约都无法支持 Join → failed_closed

**解决什么问题**

企业环境中不能把低置信的 Join 自动放行——错误的 Join 导致语义错误的结果，且难以排查。四级定级提供了明确的自动化边界。

**在当前项目中的位置**

- `src/runtime_lab/tools/join_tools.py` — 证据收集和等级判定（第 4 周）
- `src/runtime_lab/models/joins.py` — EvidenceLevel 枚举和 JoinCandidate 模型（第 4 周）
- `src/runtime_lab/policies/approval_policy.py` — 各等级对应的审批策略（第 4 周）

**输入是什么**

两表之间的 Join 候选项 + 字段类型信息 + 契约声明。

**输出是什么**

EvidenceLevel 枚举值 + 定级理由（支撑证据列表）。

**出错会导致什么风险**

如果 WEAK Join 被错误定级为 MEDIUM——不可靠的 Join 进入人工审批流程，审查者可能因为信息不充分而误批准。如果 STRONG 被降级为 MEDIUM——增加了不必要的人工审查工作量，影响自动化率。

**简单例子**

```python
class EvidenceLevel(str, Enum):
    STRONG = "STRONG"   # 契约声明 + 类型一致 → 自动放行
    MEDIUM = "MEDIUM"   # 列名匹配 + 类型兼容 → 人工审批
    WEAK = "WEAK"       # 列名相似 → 拒绝
    NONE = "NONE"       # 无证据 → 拒绝
```

**Owner 审查时应该问什么**

1. "STRONG 和 MEDIUM 的判断阈值在代码中如何定义？是硬编码还是可配置？"
2. "如果同一个 Join 有多条证据指向不同等级——最终定级是什么？规则是什么？"

---

## 14. 运行报告（Run Report）

**一句话解释**：每次运行的标准化总结文档——包含状态、风险、工具调用、审批、错误和产物清单。

**是什么**

Run Report 是每次 Agent 运行完成后生成的 Markdown 报告文件，位于 `runs/{run_id}/reports/run_report.md`。它包含：Summary（本次运行做了什么）、Final Status（completed / waiting_approval / failed_closed）、Risk Classification（风险等级和原因）、Tool Calls（调用了哪些工具）、Interrupts / Approvals（是否中断、谁审批）、Errors（错误和失败封闭原因）、Artifacts（产物和 hash）、Replay Command（如何回放本次运行）。

**解决什么问题**

让审查者在不查看 JSONL 文件的情况下，快速理解一次运行的全貌。同时提供回放命令，方便复现和对比。

**在当前项目中的位置**

- `src/runtime_lab/reports/run_report.py` — 报告生成器（第 2 周）

**输入是什么**

最终的 RuntimeState + tool_call_history + errors + approvals。

**输出是什么**

`run_report.md` 文件——写入 `runs/{run_id}/reports/`。

**出错会导致什么风险**

如果报告中包含敏感信息（如本地文件路径、完整 SQL 文本）——报告分享给他人时可能泄露敏感信息。如果报告生成失败——trace 目录中缺少关键文件，审查者不得不查看原始 JSONL。

**简单例子**

```markdown
# Run Report

## Summary
审查 SQL 文件 fixtures/sql/unsafe_query.sql。

## Final Status
failed_closed

## Risk Classification
风险等级：HIGH。检测到 DDL/DML 操作（DELETE）。

## Tool Calls
1. parse_sql: 成功
2. detect_dml_or_ddl: 发现 DELETE 语句
3. risk_gate: 触发失败封闭

## Replay Command
python -m runtime_lab replay run_20260708_001
```

**Owner 审查时应该问什么**

1. "报告中是否包含不应暴露的信息（如绝对路径、Token 用量）？是否有隐私过滤？"
2. "报告中的 Tool Calls 部分记录了完整输入输出还是摘要信息？"

---

## 15. Fixture

**一句话解释**：与生产环境完全隔离的学习用假数据——手写的 SQL、YAML 契约和 Markdown 规约文件。

**是什么**

Fixture 是项目中所有测试数据和 Demo 输入文件的统称。它们全部存放在 `fixtures/` 目录下，全部是手写的静态文件，不连接任何真实数据库。包括：SQL 文件（安全/不安全 SQL 示例）、YAML 契约文件（语义契约和指标契约）、Markdown 规约文件（DeveloperSpec 示例）。所有工具只做文本解析和规则匹配，不做数据库查询。

**解决什么问题**

学习项目不能依赖外部基础设施——如果项目需要连接真实数仓才能运行，新学习者配置环境就需要几天时间。手写 fixture 使项目可以在任何安装 Python 3.11+ 的机器上运行。

**在当前项目中的位置**

- `fixtures/contracts/` — 契约文件（semantic_contract.yml, metric_contract.yml, sql_safety_policy.yml）
- `fixtures/sql/` — SQL 文件（safe_query.sql, unsafe_query.sql, missing_partition.sql, ambiguous_join.sql）
- `fixtures/datadev/` — DeveloperSpec 规约（developer_spec_valid.md, developer_spec_missing_join.md）

**输入是什么**

不适用——Fixture 是静态文件，由工具读取。

**输出是什么**

文件内容——被工具解析为 Python 结构（dict / str / YAML 对象）。

**出错会导致什么风险**

如果 fixture 数据与真实场景差距太大——学习效果下降，学员可能无法将所学迁移到真实环境。如果 fixture 文件被错误修改——测试可能误判（假 PASS 或假 FAIL）。

**简单例子**

```sql
-- fixtures/sql/unsafe_query.sql
DELETE FROM trips WHERE trip_date < '2023-01-01';
```

```yaml
# fixtures/contracts/semantic_contract.yml
tables:
  - name: trips
    columns: [trip_id, fare, date, borough]
    partitions: [date]
```

**Owner 审查时应该问什么**

1. "当前 fixture 覆盖了哪些场景？哪些学习场景还没有 fixture 覆盖？"
2. "Fixture 文件的命名是否有规范？新增 fixture 需要遵循什么规则？"

---

## 16. CLI 入口（Typer CLI）

**一句话解释**：命令行界面——通过 `python -m runtime_lab <command>` 启动 Demo 运行，是项目的主要交互入口。

**是什么**

CLI 入口是项目的主要交互方式。使用 Typer 框架实现，通过 `app.py` 中的命令子函数，支持 `greet`（骨架验证）、`sql-review`（Demo 1）、`contract`（Demo 2）、`join`（Demo 3）、`datadev`（Demo 4）、`replay`（回放）、`fork`（分叉）等命令。每个命令对应一个 LangGraph 图的调用。

**解决什么问题**

学习项目不需要 Web UI——CLI 是最直接的交互方式，也最适合展示执行流程和观察输出。

**在当前项目中的位置**

- `src/runtime_lab/app.py` — Typer 应用定义和命令注册

**输入是什么**

命令行参数（Demo 类型 + 输入文件路径或参数）。

**输出是什么**

终端输出（状态摘要）+ 写入 `runs/{run_id}/` 的文件产物。

**出错会导致什么风险**

如果命令行参数校验不严格——用户输入非法路径时程序崩溃而非给出友好提示。如果命令与 Demo 不匹配——用户无法直观理解哪个命令对应哪个学习目标。

**简单例子**

```bash
python -m runtime_lab sql-review fixtures/sql/unsafe_query.sql
# → Runtime started: run_20260708_001
# → Final Status: failed_closed
# → Reason: SQL contains forbidden operation
# → Report: runs/run_20260708_001/reports/run_report.md
```

**Owner 审查时应该问什么**

1. "CLI 是否支持 `--help` 查看所有命令和参数？每个命令是否有清晰的使用说明？"
2. "CLI 的输出是否包含结构化信息（如 run_id、文件路径）以便用户后续操作？"

---

## 17. 策略层（Policy）

**一句话解释**：封装风险判断、失败封闭和审批触发等业务规则——与图结构和节点逻辑分离。

**是什么**

Policy 层是项目的可配置规则集合。它将"什么情况下算高风险"、"什么情况下必须审批"、"什么情况下失败封闭"等决策逻辑从节点代码中抽离出来，放在 `policies/` 目录下。策略是确定性的 Python 函数，不依赖 LLM。修改策略不需要修改图结构或节点逻辑。

**解决什么问题**

策略和节点耦合时——修改风险阈值需要改节点代码，测试和审查都变得更困难。策略分离后，规则可以独立修改、测试和版本管理。

**在当前项目中的位置**

- `src/runtime_lab/policies/risk_policy.py` — 风险等级判断规则（第 2 周）
- `src/runtime_lab/policies/fail_closed.py` — 失败封闭触发规则（第 2 周）
- `src/runtime_lab/policies/approval_policy.py` — 审批触发规则（第 4 周）

**输入是什么**

当前 RuntimeState 的相关字段（如 findings、evidence_level、error 列表）。

**输出是什么**

策略的判定结果（风险等级、是否 fail-closed、是否需要审批）。

**出错会导致什么风险**

如果策略之间存在冲突（如 risk_policy 说"高风险"但 approval_policy 说"不需要审批"）——Agent 行为矛盾。如果策略不易测试——规则变更时缺乏验证，容易出现意外副作用。

**简单例子**

```python
def should_require_approval(evidence_level: EvidenceLevel, **kwargs) -> bool:
    """MEDIUM 级别及以上需要人工审批"""
    return evidence_level in (EvidenceLevel.MEDIUM,)

def should_fail_closed(findings: list[Finding]) -> bool:
    """存在 blocking 级别的问题时失败封闭"""
    return any(f.severity == "BLOCKING" for f in findings)
```

**Owner 审查时应该问什么**

1. "策略函数的输入是否都是确定性的（不依赖外部状态）？测试时可以纯函数方式验证吗？"
2. "如果有新的合规要求（如所有 Join 都必须审批），需要改哪个文件？"

---

## 18. 存储层（Storage）

**一句话解释**：持久化组件——负责 State、checkpoint、trace、审批记录和产物的本地存储。

**是什么**

Storage 层是一组数据持久化组件，全部使用本地存储（文件系统 + SQLite）。不依赖外部数据库服务。包括：TraceStore（写入 state_history.jsonl / tool_calls.jsonl）、CheckpointStore（保存和读取 checkpoint）、ApprovalStore（持久化审批记录）、ArtifactStore（计算和保存产物 hash）。

**解决什么问题**

Agent Runtime 需要持久化才能支持故障恢复、审计追溯和回放分叉。使用本地存储而不是外部数据库，保证了项目在任何环境都能运行，无需额外基础设施。

**在当前项目中的位置**

- `src/runtime_lab/storage/trace_store.py` — trace 存储（第 1 周）
- `src/runtime_lab/storage/checkpoints.py` — checkpoint 存储（第 4 周）
- `src/runtime_lab/storage/approval_store.py` — 审批记录存储（第 4 周）
- `src/runtime_lab/storage/artifact_store.py` — 产物 hash 存储（第 5 周）

**输入是什么**

要持久化的数据（RuntimeState / tool call / approval record / artifact）。

**输出是什么**

写入本地文件系统或 SQLite 的持久化记录。

**出错会导致什么风险**

如果存储层写入失败没有被正确处理——Agent 可能继续执行但丢失了审计记录。如果并发写入同一个文件（罕见但可能）——数据损坏。如果存储路径配置错误——产物写入到错误位置，难以查找。

**简单例子**

```python
store = TraceStore(run_dir="runs/run_001")
store.save_state_change(state)
# → 写入 runs/run_001/state_history.jsonl
store.save_tool_call(tool_name="detect_dml_or_ddl", input={...}, output={...})
# → 写入 runs/run_001/tool_calls.jsonl
```

**Owner 审查时应该问什么**

1. "存储操作失败时，Agent 是否能正确处理？写入失败是否应该触发 fail-closed？"
2. "存储层的实现是否方便替换（如从文件系统切换到 SQLite）？接口抽象了吗？"

---

## 19. Demo 流程

**一句话解释**：四个学习场景——每个场景侧重一两个 Runtime 核心概念，从工具调用到 Replay/Fork 递进学习。

**是什么**

Demo 是项目的学习单元，每个 Demo 是一个端到端的 Agent 执行场景：
- **Demo 1 SQL Review**：SQL 静态审查 + 工具调用 + 风险判断 + fail-closed
- **Demo 2 Contract Inspector**：契约作为事实源 + answer / clarification / refusal
- **Demo 3 Join Approval**：人工审批 HITL + interrupt / resume
- **Demo 4 DataDev Plan Replay**：checkpoint / replay / fork + artifact lineage

四个 Demo 共享同一套 Runtime 框架（State + Graph + Storage + Policies），差别只在于 nodes 和 tools 的具体实现。

**解决什么问题**

从简单到复杂递进学习——先学工具调用和 fail-closed，再学契约作为事实源，最后学人机交互和回放分叉。每个 Demo 只引入 1-2 个新概念，降低认知负担。

**在当前项目中的位置**

- `src/runtime_lab/app.py` — 每个 Demo 对应一个 CLI 命令
- `src/runtime_lab/nodes/validate.py`、`execute_tool.py` — Demo 1-2 共用节点
- `src/runtime_lab/nodes/interrupt.py` — Demo 3 新增中断节点
- `src/runtime_lab/nodes/replay.py` — Demo 4 新增回放节点
- `tests/` — 每个 Demo 对应独立的测试文件

**输入是什么**

用户通过 CLI 输入的 Demo 类型和参数。

**输出是什么**

运行报告 + trace 文件 + 结构化结果。

**出错会导致什么风险**

如果 Demo 之间的知识依赖没有设计好——学员在执行 Demo 3 时发现需要 Demo 1 的知识但没掌握。如果 Demo 的 fixture 不够典型——学员学会了框架但不知道如何应用到真实场景。

**简单例子**

```bash
# Demo 1：SQL 审查（工具调用 + fail-closed）
python -m runtime_lab sql-review fixtures/sql/unsafe_query.sql

# Demo 2：契约检查（契约作为事实源）
python -m runtime_lab contract "指标 trip_count 能不能按 borough 查询？"

# Demo 3：Join 审批（人机交互）
python -m runtime_lab join "orders.customer_id 和 customers.id 是否可以 Join？"

# Demo 4：回放分叉（checkpoint + replay + fork）
python -m runtime_lab datadev fixtures/datadev/developer_spec_missing_join.md
```

**Owner 审查时应该问什么**

1. "四个 Demo 是否覆盖了方案书中列出的所有学习目标？是否有遗漏？"
2. "Demo 之间是否存在不必要的依赖？学员可以跳过前一个 Demo 直接做后一个吗？"

---

## 20. 条件边（Conditional Edge）

**一句话解释**：LangGraph 中根据当前 State 决定执行路径的分支机制——替代 if-else 的状态机实现。

**是什么**

Conditional Edge 是 LangGraph 提供的一种边类型。它不是固定从一个节点到另一个节点，而是通过一个路由函数（router），根据当前 RuntimeState 的字段值，动态返回下一个节点的名称。路由函数返回的字符串必须在已注册的节点名称中，否则 LangGraph 会在运行时抛出错误。

**解决什么问题**

Agent 的执行路径不是线性的——根据风险等级、审批结果、错误情况等条件，需要走不同的分支。Conditional Edge 以显式的路由函数表达这种分支逻辑，比隐式的 if-else 链更容易理解和测试。

**在当前项目中的位置**

- `src/runtime_lab/graph.py` — add_conditional_edges() 调用
- `src/runtime_lab/nodes/classify.py` — 分类节点的条件边（第 1 周）
- `src/runtime_lab/nodes/validate.py` — 风险门禁的条件边（第 2 周）

**输入是什么**

当前的 RuntimeState（路由函数从中读取决策字段）。

**输出是什么**

下一步节点名称字符串（如 `"summarize"`、`"interrupt"`、`"__end__"`）。

**出错会导致什么风险**

如果路由函数返回了未注册的节点名称——LangGraph 运行时抛出异常，中断执行。如果路由函数没有覆盖所有可能的分支条件——某些边界情况无对应路由，抛出异常。

**简单例子**

```python
def router(state: RuntimeState) -> str:
    """根据状态路由到下一个节点"""
    if state.status == "failed_closed":
        return "__end__"
    elif state.status == "waiting_approval":
        return "interrupt"
    else:
        return "summarize"

# 在 graph.py 中注册
graph.add_conditional_edges("risk_gate", router, {
    "__end__": "__end__",
    "interrupt": "interrupt",
    "summarize": "summarize",
})
```

**Owner 审查时应该问什么**

1. "条件边的路由函数是否有对应的单元测试？是否覆盖了所有路由分支？"
2. "路由函数中是否可能抛出异常？异常发生时 LangGraph 的行为是什么？"

---

## 21. 缩写速查

| 缩写 | 全称 | 含义 |
|------|------|------|
| **RS** | RuntimeState | 统一运行状态 |
| **LG** | LangGraph | 图编排框架 |
| **CT** | Controlled Tool | 受控工具 |
| **SO** | Structured Output | 结构化输出 |
| **CP** | Checkpoint | 检查点快照 |
| **IR** | Interrupt/Resume | 中断与恢复 |
| **HA** | Human Approval | 人工审批 |
| **FC** | Fail-Closed | 失败封闭 |
| **RF** | Replay/Fork | 回放与分叉 |
| **TR** | Trace/Audit | 追踪与审计 |
| **RG** | RiskGate | 风险门禁 |
| **EL** | EvidenceLevel | 证据等级 |
| **RR** | Run Report | 运行报告 |
| **FX** | Fixture | 学习用假数据 |
| **CE** | Conditional Edge | 条件边 |
| **RP** | Risk Policy | 风险策略 |
| **AP** | Approval Policy | 审批策略 |
| **TS** | TraceStore | 追踪存储 |
| **CS** | CheckpointStore | 检查点存储 |
| **AS** | ApprovalStore | 审批存储 |

---

> 本文基于 TianShu-Agent-Runtime-Lab 项目设计文档（2026-07-08），覆盖 20 个核心工程术语 + 缩写速查表。
> 每个术语遵循"九件事"说明格式：名称→是什么→解决什么问题→项目位置→输入→输出→风险→例子→审查问题。
> 参考：[2026-07-08-tianshu-agent-runtime-lab-design.md]
