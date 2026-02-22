# Digital Assets Analytics Pipeline

**Kraken WebSocket → Kafka (Avro) → Spark Structured Streaming (PySpark) → TimescaleDB/Postgres → dbt → Power BI (DirectQuery + Auto Refresh)**

A local-first, open-source streaming analytics pipeline for real-time digital asset market data using the free Kraken WebSocket trade feed. Trades are normalized and serialized using Avro (schema-enforced), streamed through Kafka, aggregated into OHLCV candles with PySpark Structured Streaming, stored in TimescaleDB/Postgres, modeled with dbt, and visualized in Power BI.



This project demonstrates:

* **Real-time ingestion** from a real market feed
* **Schema enforcement** (Avro + Schema Registry)
* **Streaming aggregation** (event-time + watermark + windows)
* **Time-series storage + analytics modeling**
* **BI dashboard** that refreshes like a live terminal

## Table of Contents

* [Architecture](#architecture)
* [How the Data Flows](#how-the-data-flows)
* [Tech Stack](#tech-stack)
* [Prerequisites](#prerequisites)
* [Installation and Running the Project](#installation-and-running-the-project)
    * [1) Start infrastructure](#1-start-infrastructure)
    * [2) Create Kafka topic](#2-create-kafka-topic)
    * [3) Verify Schema Registry and REST Proxy](#3-verify-schema-registry-and-rest-proxy)
    * [4) Register the Avro schema](#4-register-the-avro-schema)
    * [5) Start Spark processor](#5-start-spark-processor)
    * [6) Start Kraken producer](#6-start-kraken-producer)
    * [7) Verify end-to-end](#7-verify-end-to-end)
    * [8) Build analytics models with dbt](#8-build-analytics-models-with-dbt)
    * [9) Power BI dashboard setup](#9-power-bi-dashboard-setup)
* [Data Contract: Avro, Schema Registry, and the “-value” subject](#data-contract-avro-schema-registry-and-the--value-subject)
* [Storage Model](#storage-model)
* [Common Pitfalls and Fixes](#common-pitfalls-and-fixes)
* [Stop and Cleanup](#stop-and-cleanup)
* [Roadmap Upgrades](#roadmap-upgrades)
* [Disclaimer](#disclaimer)

## Architecture

Kraken WebSocket (Trade Feed)
        |
        v
Python Producer
  - subscribe to Kraken trade channel
  - normalize fields into a stable internal event schema
  - Avro encode using Schema Registry (Confluent wire format)
        |
        v
Kafka Topic: ticks.raw.crypto.avro.v1  (3 partitions)
        |
        v
Spark Structured Streaming (PySpark)
  - read from Kafka
  - decode Avro via Schema Registry
  - event-time watermark
  - 1-minute window aggregation (OHLCV)
  - write to Postgres/Timescale
        |
        v
TimescaleDB/Postgres (raw candles)
  - market_candles_1m
        |
        v
dbt models (analytics schema)
  - dim + fact + marts (BI-ready)
        |
        v
Power BI Desktop (DirectQuery + Auto Page Refresh)
  - trading terminal 

## How the Data Flows

### 1. Obtain Data (Kraken WebSocket)
We subscribed to Kraken’s WebSocket v2 trade channel for selected symbols (e.g., **BTC/USD**, **ETH/USD**, **SOL/USD**) and receive real-time trades. Trades include price, size (qty), side, timestamp, and other relevant metadata.

### 2. Normalize & Serialize to Avro (Producer)
Kraken payloads are parsed and immediately normalized into a stable, internal event schema serialized into **Avro** format, bypassing fragile JSON entirely. This enforces a strict data contract from the very start. The schema is registered in the **Schema Registry** so downstream consumers can always decode it reliably.

**Avro Schema (`CryptoTick`):**
```json
{
  "type": "record",
  "name": "CryptoTick",
  "namespace": "digital_assets.analytics",
  "fields": [
    { "name": "event_id", "type": "string" },
    { "name": "ts", "type": "string" },
    { "name": "symbol", "type": "string" },
    { "name": "price", "type": "double" },
    { "name": "volume", "type": "double" },
    { "name": "side", "type": ["null", "string"], "default": null },
    { "name": "venue", "type": "string", "default": "kraken" },
    { "name": "asset_class", "type": "string", "default": "crypto" },
    { "name": "schema_version", "type": "int", "default": 1 },
    { "name": "source", "type": "string", "default": "kraken_ws_v2_trade" }
  ]
}
```

**Confluent Avro wire format:**
* **1 byte:** magic byte (`0x00`)
* **4 bytes:** schema id
* **remaining bytes:** Avro record payload

### 3. Stream (Kafka)
The producer publishes encoded events to the Kafka topic:
* `ticks.raw.crypto.avro.v1` (3 partitions)

### 4. Transform (Spark Structured Streaming)
Spark reads from Kafka and aggregates trades into 1-minute candles per symbol using:
* event-time windowing
* watermarking (tolerate late events)
* micro-batch trigger interval

**Candle fields:**
* `open`, `high`, `low`, `close`, `volume`

> **Note:** Candle volume is per-minute volume (sum of trade sizes inside that minute), not cumulative. It can vary drastically minute-to-minute.

### 5. Store (TimescaleDB/Postgres)
Spark writes candles to Postgres/TimescaleDB (`market_candles_1m`).

### 6. Model (dbt)
dbt builds BI-friendly analytics objects in the analytics schema:
* `analytics.dim_symbol`
* `analytics.fct_candles_1m`
* `analytics.fct_candles_5m`

### 7. Visualize (Power BI)
Power BI uses DirectQuery so it can auto-refresh and reflect new candles as they arrive.

## Tech Stack

* **Kraken WebSocket API:** Free real-time market data
* **Kafka:** Event streaming
* **Karapace:** Schema Registry + REST Proxy
* **Avro:** Schema enforcement + serialization
* **PySpark Structured Streaming:** Windowed aggregation
* **TimescaleDB / Postgres:** Time-series storage
* **Valkey:** Optional Redis-compatible cache patterns
* **dbt:** Analytics modeling + data tests
* **Power BI Desktop:** Dashboard visualization

## Prerequisites

**Required:**
* **Docker Desktop**
* **Git**
* **Python 3.10+** (for the producer and schema registration tooling)

**Optional:**
* **Power BI Desktop** (to build and view the dashboard)

## Installation and Running the Project

**Important order:** infra → topic → schema → Spark → producer → dbt → Power BI

### 1. Start Infrastructure
From the repo root:
```bash
cd infra
docker compose up -d
docker compose ps
```
**Local Endpoints:**
* **Kafka UI (Kafbat):** `http://localhost:8080`
* **Schema Registry (Karapace):** `http://localhost:8081/subjects`
* **REST Proxy (Karapace):** `http://localhost:8082/topics`
* **Postgres/TimescaleDB:** `localhost:5432`
* **Valkey:** `localhost:6379`
* **Kafka (host):** `localhost:9092`

> **Note:** Inside Docker, services may use internal addresses like `kafka:9093`. From your host machine, use `localhost:9092`.

### 2. Create Kafka Topic
Create the Avro topic (Spark consumes this):
```bash
docker exec -it kafka bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --create --if-not-exists --topic ticks.raw.crypto.avro.v1 --partitions 3 --replication-factor 1"
```
Verify the topic:
```bash
docker exec -it kafka bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --describe --topic ticks.raw.crypto.avro.v1"
```

If the topic was accidentally created with fewer partitions (common in local dev), enforce 3:
```bash
docker exec -it kafka bash -lc "/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9093 --alter --topic ticks.raw.crypto.avro.v1 --partitions 3"
```

### 3. Verify Schema Registry and REST Proxy
**Linux/macOS Shell:**
```bash
curl [http://127.0.0.1:8081/subjects](http://127.0.0.1:8081/subjects)
curl [http://127.0.0.1:8082/topics](http://127.0.0.1:8082/topics)
```

**Windows PowerShell:**
```powershell
curl.exe [http://127.0.0.1:8081/subjects](http://127.0.0.1:8081/subjects)
curl.exe [http://127.0.0.1:8082/topics](http://127.0.0.1:8082/topics)
```

**Expected:**
* `/subjects` returns `[]` initially (before schema registration).
* `/topics` includes `_schemas`, `__consumer_offsets`, and your created topics.

### 4. Register the Avro Schema
From the repo root:
```bash
python tools/schema_registry/register_avro.py
```

Confirm the subject exists:
**Linux/macOS:**
```bash
curl [http://127.0.0.1:8081/subjects](http://127.0.0.1:8081/subjects)
```

**Windows PowerShell:**
```powershell
curl.exe [http://127.0.0.1:8081/subjects](http://127.0.0.1:8081/subjects)
```

**Expected:**
`["ticks.raw.crypto.avro.v1-value"]`

### 5. Start Spark Processor
From the `infra/` directory:
```bash
docker compose up -d --build spark-processor
docker compose logs -f spark-processor
```
**Spark will:**
* Subscribe to `ticks.raw.crypto.avro.v1`
* Decode Avro via Schema Registry
* Aggregate trades into 1-minute candles
* Write to TimescaleDB/Postgres

### 6. Start Kraken Producer
From the repo root:
```bash
python producer_kraken/main.py
```
**Key Config Expectations:**
* **Topic:** `ticks.raw.crypto.avro.v1`
* **Bootstrap servers:**
  * Host-run producer: `localhost:9092`
  * Container-run producer: `kafka:9093`

### 7. Verify End-to-End
**7.1 Kafka offsets are increasing:**
```bash
docker exec -it kafka bash -lc "/opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9093 --topic ticks.raw.crypto.avro.v1 --time -1"
```

**7.2 Candles exist in Postgres:**
```bash
docker exec -it timescaledb psql -U postgres -d stock_db -c "SELECT * FROM market_candles_1m ORDER BY time DESC LIMIT 10;"
```
*If you see rows for BTC/ETH/SOL, the pipeline is working.*

### 8. Build Analytics Models with dbt
From the `infra/` directory:
```bash
docker compose run --rm dbt build
```
Verify analytics objects exist (dbt often creates views; use `\dv` to list views):
```bash
docker exec -it timescaledb psql -U postgres -d stock_db -c "\dv analytics.*"
```
**You should see:**
* `analytics.dim_symbol`
* `analytics.fct_candles_1m`
* `analytics.fct_candles_5m`

### 9. Power BI Dashboard Setup

**9.1 Connect to Postgres (DirectQuery)**
* Open Power BI Desktop → Get Data → PostgreSQL database
* **Server:** `localhost`
* **Database:** `stock_db`
* **Data connectivity mode:** DirectQuery
* **Username/Password:** `postgres` / `postgres`

**9.2 Load Analytics Objects**
Load the following tables/views:
* `analytics.dim_symbol`
* `analytics.fct_candles_1m`
* `analytics.fct_candles_5m`

**9.3 Relationships (Model view)**
Create the following relationships:
* `dim_symbol[symbol_key]` → `fct_candles_1m[symbol_key]` (1:* single direction)
* `dim_symbol[symbol_key]` → `fct_candles_5m[symbol_key]` (1:* single direction)

**9.4 Suggested Pages**
* **Overview:** Latest price, 1h/24h change, high/low, volume, latency + price/volume charts.
* **Candlestick:** Deneb candlestick + OHLC stats panel.
* **Volatility:** Returns line + rolling volatility + return histogram.

**9.5 Auto Refresh (Desktop)**
Navigate to **Format → Page refresh → On**.
*Suggested intervals:*
* **Overview:** 60s
* **Candlestick:** 60–120s

---

## Data Contract: Avro & Schema Registry

Schema Registry stores schemas using the convention: `<topic>-value` (schema for Kafka message value). Your schema subject is `ticks.raw.crypto.avro.v1-value`.

If Spark crashes with malformed records, the most common causes are:
* Producer accidentally sending JSON (magic byte `0x7b`).
* Schema mismatch between producer and consumer.

---

## Storage Model

* **Raw candles (written by Spark):** `market_candles_1m` includes `time` (UTC minute bucket), `symbol`, `open`, `high`, `low`, `close`, `volume`.
* **Analytics layer (dbt):** `analytics.*` includes dim/fact/marts for BI reporting.

---

## Common Pitfalls and Fixes

* **“Kafka has thousands of messages but DB has only ~70 rows”:** This is correct. Kafka carries individual trades/ticks; the DB stores aggregated minute candles.
* **Spark error - offsets changed / partitions gone:** Happens if Kafka topic state changes while the Spark checkpoint points to old offsets. Keep partitions stable (3) and don't delete Kafka volumes without resetting Spark checkpoints.
* **Candlestick looks “flat”:** Usually caused by multiple symbols selected at once (e.g., BTC dominates the scale) or the y-axis includes 0. Enforce a single select symbol and set the Vega-Lite scale `zero:false`.
* **Schema registry endpoints not working:** Check logs using `docker compose ps`, `docker compose logs karapace-registry`, and `docker compose logs karapace-rest`.

---

## Stop and Cleanup

**Stop containers (keep volumes):**
```bash
docker compose down --remove-orphans
```

**Full reset (deletes volumes, wipes topics, schema state, and DB data):**
```bash
docker compose down -v --remove-orphans
```

---

## Roadmap Upgrades

* Add a **bronze layer**: store raw ticks to Postgres or Parquet for audit/backfills.
* Add candle fields: `trade_count`, `vwap`.
* Add completeness checks (missing minutes per symbol).
* Add CI to run dbt tests automatically.
* Add a lightweight API layer (FastAPI) to serve analytics endpoints.

---

> **Disclaimer:** This project is for learning and portfolio demonstration. It is not financial advice.
