import os

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "ticks.raw.crypto.avro.v1")
STARTING_OFFSETS = os.getenv("STARTING_OFFSETS", "latest")

# Streaming semantics
WATERMARK_DELAY = os.getenv("WATERMARK_DELAY", "2 minutes")
WINDOW_DURATION = os.getenv("WINDOW_DURATION", "1 minute")
TRIGGER_INTERVAL = os.getenv("TRIGGER_INTERVAL", "10 seconds")
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "/checkpoints/candles_1m")

# TimescaleDB (Postgres)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "timescaledb")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "stock_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_TABLE = os.getenv("POSTGRES_TABLE", "market_candles_1m")

# Valkey
VALKEY_HOST = os.getenv("VALKEY_HOST", "valkey")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
VALKEY_PREFIX = os.getenv("VALKEY_PREFIX", "latest:candle:1m")

SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://karapace-registry:8081")
SCHEMA_SUBJECT = os.getenv("SCHEMA_SUBJECT", "ticks.raw.crypto.avro.v1-value")
