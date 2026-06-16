# Verification Report

Review Package 路径：generated\review_packages\trip_daily_report_m2
总体状态：WARN

## 状态摘要

- SQL 静态检查状态：PASS
- SQL sample run 状态：SKIPPED
- Spark 静态检查状态：PASS
- Spark sample run 状态：SKIPPED

## PENDING / SKIPPED 原因
- SQL sample run: SKIPPED，未提供开发库或 sample 数据源。
- Spark sample run: SKIPPED: Spark 环境不可用，Spark sample run 跳过；Spark 执行尚未实现。

## 静态检查明细
- SQL 只读语句: PASS，SQL 以 SELECT 开始
- SQL 禁止关键字: PASS，未检测到 DDL/DML/危险操作
- SQL lineage 字段引用: PASS，SQL 字段来自 lineage
- Spark 禁止写入动作: PASS，未检测到 Spark 写入动作
- Spark lineage 字段引用: PASS，Spark 字段来自 lineage

## WARN / FAIL 明细
- WARN: SQL sample run 状态为 SKIPPED
- WARN: Spark sample run 状态为 SKIPPED
- WARN: 交叉验证状态为 PENDING: 没有 SQL/Spark 执行结果，交叉验证未尝试。

## 人审提示

- SQL/Spark 均为草案。
- 未经人审不得上线。
- Agent 不写生产库，不自动上线，不替代人工审批。
