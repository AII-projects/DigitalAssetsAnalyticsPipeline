# Architecture

```mermaid
flowchart LR
  Kraken WS v2 trade feed --> K[Kafka (KRaft)]
  K --> S[PySpark Structured Streaming\n1-min OHLC aggregation]
  S --> V[Valkey (Hot Store)\nLatest candle per symbol]
  S --> T[TimescaleDB (Warm Store)\nHistorical candles hypertable]
  T --> BI[Power BI / Tableau\n(Postgres connector)]
  V --> RT[Optional: Streamlit\nRealtime view]
