# SQL — Credit Risk Analytics

Job-relevant, production-style SQL for credit-risk reporting and monitoring.
These queries express the same concepts as the Python models in
[`../src/credit_risk/`](../src/credit_risk) — PD, LGD, ECL, IFRS 9 staging,
concentration, and early warning — in the language a risk analyst actually uses
day to day against a data warehouse.

> **Synthetic & self-contained.** All data is illustrative. The queries target
> **PostgreSQL 12+** (also readable as ANSI SQL) and **do not require a live
> database to review** — `schema.sql` includes DDL plus a tiny seed so every
> file parses and runs standalone.

## What each file demonstrates

| File | Analytics technique | Why employers care |
|------|--------------------|--------------------|
| `schema.sql` | Star-style data model (`dim_loan`, `fact_loan_monthly`, `fact_ecl`, `dim_scenario`) + seed | Data modelling; understands a servicing/warehouse layout |
| `01_vintage_analysis.sql` | Vintage curves by origination cohort & age; sticky cumulative bad-rate | Spots deteriorating underwriting before it hits P&L |
| `02_delinquency_roll_rates.sql` | Bucket-to-bucket roll-rate matrix; forward-roll & cure rates | Core of flow-based loss forecasting & collections KPIs |
| `03_cohort_default_rates.sql` | Default rates by vintage × score band; sector risk index | Validates risk-based pricing / underwriting |
| `04_chargeoff_loss_curves.sql` | Monthly NCO rate; cumulative net-loss curves; realised LGD | Empirical backbone of CECL / lifetime-loss estimation |
| `05_utilization_trends.sql` | Portfolio & per-loan utilisation trend, moving average, jump flags | Leading indicator of borrower stress |
| `06_exposure_concentration.sql` | Exposure share, HHI by dimension, single-name top-10 | Concentration risk is a top committee concern |
| `07_stage_migration.sql` | IFRS 9 stage transition matrix; net drift; coverage by stage | Regulator-expected staging monitoring |
| `08_watchlist_extraction.sql` | Behavioural watch score + expected-loss-at-risk ranking; rollups | Prioritises intervention before charge-off |
| `09_ecl_aggregation.sql` | Allowance by stage/sector; scenario reconciliation; top contributors | Feeds financial statements & the risk committee memo |

## SQL techniques on display

Window functions (`LAG`, `ROW_NUMBER`, running/partitioned aggregates,
`DISTINCT ON`), CTEs, `GROUPING SETS` / `ROLLUP` subtotals, self-joins for
transition matrices, ratio-to-total shares, and cumulative curves — with clear
comments explaining the *business* meaning of every metric.

## How to run

```bash
# Option A — review only: read the .sql files (fully commented).

# Option B — run against a local Postgres with the built-in seed:
createdb credit_demo
psql credit_demo -f sql/schema.sql
psql credit_demo -f sql/01_vintage_analysis.sql      # ...and 02-09

# Option C — run on the full 12,000-loan synthetic portfolio:
python run_pipeline.py                                # writes data/processed/*.csv
# then COPY the CSVs into the matching tables, e.g.:
#   \copy dim_loan  FROM 'data/processed/portfolio.csv'      CSV HEADER
#   \copy fact_ecl  FROM 'data/processed/ecl_loan_level.csv' CSV HEADER
# (column names in schema.sql mirror the pipeline output.)
```

The `fact_loan_monthly` grain (loan × month) is the monthly performance panel
that vintage, roll-rate, loss-curve, and migration analysis require. The Python
pipeline summarises this same behavioural history into features; here it is kept
at monthly grain so the time-series SQL patterns are explicit.
