# Telecom DW Agent Lab

Telecom DW Agent Lab is a local enterprise-style telecom data warehouse project. It is designed for practicing data warehouse modeling, MySQL SQL development, Python ETL, metric governance, FastAPI services, LangGraph agents, and future frontend analytics.

The project is intentionally runnable on a personal computer. It does not target massive production data volume, but it does target realistic telecom warehouse structure, naming, metric logic, and business relationships.

## Current Status

Completed:

- Standardized telecom field dictionary.
- ODS, DWD, DWS, and ADS warehouse layering.
- MySQL database and table DDL.
- Realistic telecom mock data generation.
- Data quality validation report.
- Project structure refactor and archive.
- Knowledge base documents for business context, metrics, data model, system architecture, and project status.

Next phase:

- Metadata reader.
- Read-only SQL execution engine.
- Metric catalog service.
- FastAPI endpoints.
- LangGraph agent workflows.
- Next.js frontend.

## Architecture

```text
Local business field assets
        |
        v
Field standardization and data modeling
        |
        v
Python data generator and ETL
        |
        v
MySQL: ods / dwd / dws / ads
        |
        v
Metric catalog and semantic metadata
        |
        v
FastAPI + LangGraph Agent + Next.js
```

## Tech Stack

- Database: MySQL
- ETL and data generation: Python
- API: FastAPI
- Agent workflow: LangGraph
- LLM application layer: LangChain-compatible design
- Frontend: Next.js
- Config: YAML and `.env`

## Repository Structure

```text
telecom-dw-agent-lab/
├── AGENTS.md
├── README.md
├── README_CN.md
├── config/
│   ├── settings.yaml
│   ├── database.yaml
│   └── agent.yaml
├── data/
│   ├── raw/
│   ├── generated/
│   ├── exports/
│   └── logs/
├── docs/
│   ├── business_context.md
│   ├── data_dictionary.md
│   ├── metric_dictionary.md
│   ├── data_model.md
│   ├── system_architecture.md
│   ├── project_status.md
│   ├── data_warehouse_build_journey.md
│   └── project_structure_guide_CN.md
├── scripts/
│   └── generate_data.py
├── sql/
│   ├── create_dw_tables.sql
│   ├── ods/
│   ├── dwd/
│   ├── dws/
│   ├── ads/
│   └── checks/
├── src/
│   ├── telecom_dw/
│   └── frontend/
└── tests/
```

## Knowledge Base

- `docs/business_context.md`: telecom business concepts and analysis scenarios.
- `docs/data_dictionary.md`: standardized field dictionary and naming rules.
- `docs/metric_dictionary.md`: metric definitions, grain, source tables, and business usage.
- `docs/data_model.md`: ODS, DWD, DWS, ADS model design and relationships.
- `docs/system_architecture.md`: system architecture, service plan, and agent workflow.
- `docs/project_status.md`: current status, constraints, and next tasks.
- `docs/data_warehouse_build_journey.md`: build process summary and lessons learned.
- `docs/project_structure_guide_CN.md`: Chinese guide for the recommended directory structure.

## MySQL Warehouse

The warehouse uses four MySQL schemas as physical layers:

| Layer | Schema | Purpose |
|---|---|---|
| ODS | `ods` | Raw source-like data layer |
| DWD | `dwd` | Clean detail dimension and fact layer |
| DWS | `dws` | Subject-oriented summary layer |
| ADS | `ads` | Metric, reporting, and agent-serving layer |

DDL is stored in:

```text
sql/create_dw_tables.sql
```

## Data Generation

Main entry:

```powershell
python scripts/generate_data.py
```

Generated files are written to:

```text
data/generated/mysql_load/
```

Those generated files are intentionally ignored by Git because they are large and reproducible.

## Git Policy

The following assets remain local and are not pushed to GitHub:

- `docs/telecom_fields.xlsx`
- `docs/telecom_dw_table_design.xlsx`
- `docs/telecom_dw_table_design_cn.xlsx`
- `data/generated/**`
- `data/raw/**`
- `data/exports/**`

The repository keeps source code, SQL, config templates, documentation, and lightweight quality reports.

## Recommended Next Steps

1. Build `src/telecom_dw/metadata` to read MySQL table and column comments.
2. Build `src/telecom_dw/sql_engine` for safe read-only SQL execution.
3. Build `src/telecom_dw/metrics` to load and serve metric definitions.
4. Add FastAPI routes for metadata, metrics, SQL, and agent chat.
5. Add LangGraph workflows for metric lookup, SQL generation, SQL validation, and result explanation.
6. Add tests for data quality, SQL safety, metric definitions, and agent behavior.
