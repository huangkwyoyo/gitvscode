# Architecture

## Pipeline Stages

1. `src/io`: load data from CSV, Excel, or SQL databases.
2. `src/cleaning`: normalize schema, fill missing values, remove duplicates, detect outliers.
3. `src/analysis`: generate descriptive statistics and correlation analysis.
4. `src/visualization`: create reusable chart images.
5. `src/insights`: extract narrative insights with an optional LLM provider.
6. `src/reporting`: render the final report from templates.

## Data Folders

- `data/raw`: source files, never modified by pipeline code.
- `data/interim`: temporary stage outputs.
- `data/processed`: cleaned and analysis-ready datasets.

