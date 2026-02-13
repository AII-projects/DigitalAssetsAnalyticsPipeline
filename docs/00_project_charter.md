# Project Charter — Real-Time Digital Assets Analytics (OSS + PySpark)

## Purpose
Build a real-time analytics platform from scratch:
- ticks -> Kafka -> PySpark Structured Streaming -> TimescaleDB (warm) + Valkey (hot)
- later: dbt marts -> Power BI/Tableau dashboards

## Constraints
- Open-source and free to run locally
- PySpark only (no Java/Scala application code)
- TimescaleDB must run in Apache-only mode (`timescaledb.license=apache`)

## Success criteria (portfolio)
- One-command local startup
- Documented data contracts (tick + candle)
- Repeatable runs + basic correctness tests
- BI-ready mart tables (later milestone)
