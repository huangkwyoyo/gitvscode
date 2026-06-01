# Telecom Data Warehouse Agent Lab

## Project Goal

Build a telecom enterprise data warehouse simulation that runs on a personal computer.

The project is designed for:

- Data warehouse practice
- BI and metrics development
- AI Agent development
- SQL generation
- Business analysis
- LangGraph workflow development

The goal is realism of architecture and business logic, not big data scale.

------

## Technology Stack

Backend:

- Python 3.12+
- MySql
- FastAPI
- LangGraph
- LangChain

Frontend:

- Next.js
- TypeScript

------

## Data Source

Primary source:

docs/telecom_fields.xlsx

This file contains real telecom business fields.

Do not invent field meanings without analysis.

If assumptions are required:

- explicitly state assumptions
- mark generated fields as synthetic

------

## Development Workflow

Before coding:

1. Read relevant files
2. Explain implementation plan
3. Confirm assumptions

During coding:

1. Make minimal changes
2. Keep modules focused
3. Follow existing architecture

After coding:

1. Run verification
2. Report actual results
3. Explain changes

------

## Data Warehouse Standards

Layers:

ODS
DWD
DWS
ADS

Naming:

ods_xxx
dwd_xxx
dws_xxx
ads_xxx

Prefer star schema.

Dimension tables:

dim_xxx

Fact tables:

fact_xxx

------

## Agent Architecture

Agent workflows must use LangGraph.

Requirements:

- explicit state
- explicit routing
- retry handling
- timeout handling
- logging

Avoid hidden logic.

------

## FastAPI Standards

Keep API layer thin.

Business logic belongs in services.

Use Pydantic schemas.

Validate all inputs.

------

## SQL Standards

Prefer readable SQL.

Avoid nested queries when joins are clearer.

Document business metric logic.

------

## Verification

Before completion:

- run tests
- run lint
- run type checks

Never claim success without verification.