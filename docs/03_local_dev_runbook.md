# Local Dev Runbook

## Start infra
cd infra
docker compose up -d

## Verify Kafka
Open Kafka UI: http://localhost:8080

## Verify Karapace
Schema Registry (should respond): http://localhost:8081/subjects
REST Proxy (should respond): http://localhost:8082

## Verify TimescaleDB schema
docker exec -it timescaledb psql -U postgres -d stock_db -c "\dt"
Expect: market_candles_1m exists

## Verify Valkey
docker exec -it valkey valkey-cli ping
Expect: PONG

## Decision
Use:
- Topic: ticks.raw.v1
- Partitions: 3
- Message key: symbol

## Why
- The ".v1" suffix makes schema evolution explicit.
- Partitioning by symbol allows scaling while preserving per-symbol ordering.
- Kafka uses the record key to deterministically map messages to partitions.